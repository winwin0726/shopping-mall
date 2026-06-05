import os
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "super-secret-key-change-this"

# 데이터베이스 경로 (절대 경로로 보장하여 PythonAnywhere 동작 안정성 확보)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "users.db")

def get_db():
    # 타임아웃을 주어 파일 잠금(lock) 에러 방지
    conn = sqlite3.connect(DATABASE, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with app.app_context():
        db = get_db()
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                expire_date TIMESTAMP,
                hwid TEXT
            )
        ''')
        
        # 모바일 원격 관제탑용 컬럼 안정적인 독립 마이그레이션
        columns_to_add = [
            ("pc_status", "'오프라인'"),
            ("pc_log_msg", "''"),
            ("pending_command", "''"),
            ("last_sync", "''"),
            # 모바일 관제탑 v2 확장 컬럼
            ("crawler_tabs_status", "'{}'"),
            ("crawl_results_preview", "'[]'"),
            ("notifications", "'[]'")
        ]
        
        for col_name, default_val in columns_to_add:
            try:
                db.execute(f"ALTER TABLE users ADD COLUMN {col_name} TEXT DEFAULT {default_val}")
            except sqlite3.OperationalError:
                pass # 이미 컬럼이 존재하면 넘어감
        # 기본 관리자(admin) 계정 생성
        cur = db.cursor()
        cur.execute("SELECT * FROM users WHERE username='admin'")
        if not cur.fetchone():
            hashed_pw = generate_password_hash("admin1234")
            db.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                       ("admin", hashed_pw, "admin"))
        db.commit()
        db.close()

# 최초 앱 구동 시 DB 초기화
init_db()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/mobile")
def mobile():
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    db.close()
    return render_template("mobile.html", user=user)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        db.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))
        else:
            error = "아이디 또는 비밀번호가 올바르지 않습니다."
            
    return render_template("login.html", error=error)

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    success = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        
        db = get_db()
        existing = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            error = "이미 존재하는 아이디입니다."
        elif len(username) < 3 or len(password) < 4:
            error = "아이디는 3자 이상, 비밀번호는 4자 이상이어야 합니다."
        else:
            # 기본 가입 시 7일 기간을 갖는 'trial' (테스트) 등급 부여
            hashed_pw = generate_password_hash(password)
            expire_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
            
            db.execute("INSERT INTO users (username, password, role, expire_date) VALUES (?, ?, ?, ?)",
                       (username, hashed_pw, "trial", expire_date))
            db.commit()
            success = "회원가입이 완료되었습니다! 7일 체험 권한이 발급되었습니다."
        db.close()
            
    return render_template("register.html", error=error, success=success)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
        
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    
    users_list = []
    # 권한이 admin인 경우 사이트 내의 전체 회원 정보 조회 가능
    if user["role"] == "admin":
        users_list = db.execute("SELECT * FROM users").fetchall()
        
    db.close()
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template("dashboard.html", user=user, users_list=users_list, current_time=current_time)

# =========================================================================
# 데스크톱 프로그램 (winwin60.py) 에서 호출할 API 엔드포인트!
# =========================================================================
@app.route("/api/v1/auth", methods=["POST"])
def api_auth():
    data = request.json
    if not data:
        return jsonify({"ok": False, "msg": "요청 형식이 잘못되었습니다."}), 400
        
    username = data.get("username")
    password = data.get("password")
    hwid = data.get("hwid")  # PC의 고유 MAC 주소나 시리얼 넘버
    
    if not username or not password or not hwid:
        return jsonify({"ok": False, "msg": "요청 데이터(아이디/비밀번호/기기고유값)가 누락되었습니다."}), 400
        
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    
    if not user or not check_password_hash(user["password"], password):
        db.close()
        return jsonify({"ok": False, "msg": "아이디 또는 비밀번호가 틀렸습니다."})
        
    role = user["role"]
    
    # 만료일 검증 (가족/관리자는 무제한)
    if role not in ["family", "admin"]:
        if user["expire_date"]:
            exp_time = datetime.strptime(user["expire_date"], "%Y-%m-%d %H:%M:%S")
            if datetime.now() > exp_time:
                db.close()
                return jsonify({"ok": False, "msg": f"이용 기한이 만료되었습니다. ({exp_time.strftime('%Y-%m-%d %H:%M')}) 관리자에게 연장을 문의하세요."})
        else:
            db.close()
            return jsonify({"ok": False, "msg": "만료일이 설정되지 않은 유효하지 않은 계정입니다."})
            
    # PC 기기 잠금 검증 (HWID Locking)
    if role not in ["family", "admin"]:
        current_hwid = user["hwid"]
        # 최초 로그인 한정, 기기 등록을 자동으로 허용함
        if not current_hwid:
            db.execute("UPDATE users SET hwid = ? WHERE id = ?", (hwid, user["id"]))
            db.commit()
        # 다른 PC에서 로그인 시도시 차단
        elif current_hwid != hwid:
            db.close()
            return jsonify({
                "ok": False, 
                "msg": "다른 PC에 귀속된 계정입니다! 한 계정은 1대의 PC에서만 사용 가능합니다.\n(기기 변경은 관리자에게 문의바랍니다)"
            })
            
    db.close()
    # 최종 승인: 남은 기간 등 주요 데이터 반환
    return jsonify({
        "ok": True, 
        "role": role,
        "expire_date": user["expire_date"]
    })

# =========================================================================
# 모바일 관제탑용 실시간 동기화/제어 API
# =========================================================================
@app.route("/api/v1/sync", methods=["POST"])
def api_sync():
    """PC 데스크톱 프로그램이 3초마다 지속적으로 호출하며 상태를 보고하고, 쌓인 명령이 있는지 폴링(Polling)합니다."""
    data = request.json
    if not data: return jsonify({"ok": False})
    
    username = data.get("username")
    hwid = data.get("hwid")
    status = data.get("status", "온라인")
    log_msg = data.get("log_msg", "")
    tabs_status = data.get("tabs_status", "{}")
    results_preview = data.get("results_preview", "[]")
    notifications = data.get("notifications", "[]")
    
    db = get_db()
    user = db.execute("SELECT id, hwid, pending_command FROM users WHERE username = ?", (username,)).fetchone()
    
    if not user or (user["hwid"] and user["hwid"] != hwid):
        db.close()
        return jsonify({"ok": False})
        
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute("""
        UPDATE users 
        SET pc_status = ?, pc_log_msg = ?, last_sync = ?,
            crawler_tabs_status = ?, crawl_results_preview = ?, notifications = ?
        WHERE id = ?
    """, (status, log_msg, current_time, tabs_status, results_preview, notifications, user["id"]))
    
    # 펜딩된(대기 중인) 모바일 유저의 명령이 있는지 확인
    cmd = user["pending_command"]
    if cmd:
        # 명령을 전달했으므로 DB에서 클리어
        db.execute("UPDATE users SET pending_command = '' WHERE id = ?", (user["id"],))
        
    db.commit()
    db.close()
    
    return jsonify({"ok": True, "command": cmd})

@app.route("/api/v1/dashboard/control", methods=["POST"])
def dashboard_control():
    """모바일 대시보드에서 '실행', '정지' 버튼 클릭 시 호출됩니다."""
    if "user_id" not in session:
        return jsonify({"ok": False, "msg": "로그인이 필요합니다."})
        
    data = request.json
    command = data.get("command")
    
    db = get_db()
    # PC가 나중에 /api/v1/sync 로드를 할 때 읽어가도록 트랜잭션 기록
    db.execute("UPDATE users SET pending_command = ? WHERE id = ?", (command, session["user_id"]))
    db.commit()
    db.close()
    
    return jsonify({"ok": True})

@app.route("/api/v1/dashboard/status")
def dashboard_status():
    """모바일 대시보드가 2초마다 호출하며 화면에 그릴 최신 PC 상태를 가져옵니다."""
    if "user_id" not in session:
        return jsonify({"ok": False})
        
    db = get_db()
    user = db.execute("SELECT pc_status, pc_log_msg, last_sync FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    db.close()
    
    # 10초 이상 PC 응답이 없으면 오프라인(종료) 처리
    is_online = False
    if user["last_sync"]:
        try:
            last = datetime.strptime(user["last_sync"], "%Y-%m-%d %H:%M:%S")
            if (datetime.now() - last).total_seconds() < 10:
                is_online = True
        except:
            pass
            
    final_status = user["pc_status"] if is_online else "프로그램 종료됨 (오프라인)"
    
    return jsonify({
        "ok": True,
        "is_online": is_online,
        "status": final_status,
        "log_msg": user["pc_log_msg"] if is_online else "PC와 연결이 끊어졌습니다.",
        "last_sync": user["last_sync"]
    })

@app.route("/api/v1/dashboard/detail")
def dashboard_detail():
    """모바일 관제탑 전용 — 탭별 상세 상태 + 크롤링 결과 미리보기 + 알림 반환"""
    if "user_id" not in session:
        return jsonify({"ok": False})
    
    db = get_db()
    user = db.execute("""
        SELECT pc_status, pc_log_msg, last_sync,
               crawler_tabs_status, crawl_results_preview, notifications
        FROM users WHERE id = ?
    """, (session["user_id"],)).fetchone()
    db.close()
    
    is_online = False
    if user["last_sync"]:
        try:
            last = datetime.strptime(user["last_sync"], "%Y-%m-%d %H:%M:%S")
            if (datetime.now() - last).total_seconds() < 10:
                is_online = True
        except:
            pass
    
    import json
    try:
        tabs = json.loads(user["crawler_tabs_status"] or "{}")
    except:
        tabs = {}
    try:
        results = json.loads(user["crawl_results_preview"] or "[]")
    except:
        results = []
    try:
        notifs = json.loads(user["notifications"] or "[]")
    except:
        notifs = []
    
    return jsonify({
        "ok": True,
        "is_online": is_online,
        "status": user["pc_status"] if is_online else "프로그램 종료됨 (오프라인)",
        "log_msg": user["pc_log_msg"] if is_online else "PC와 연결이 끊어졌습니다.",
        "last_sync": user["last_sync"],
        "tabs": tabs,
        "results": results,
        "notifications": notifs
    })

if __name__ == "__main__":
    # 0.0.0.0 주소 오픈을 통해 어떤 스마트폰에서도 접근 가능하게 설정 (단시간 테스트용)
    app.run(host="0.0.0.0", port=5000, debug=True)
