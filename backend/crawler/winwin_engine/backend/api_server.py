import os
import re
import json
import datetime
import mimetypes

from dotenv import load_dotenv
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

# Windows 환경에서 .js가 text/plain으로 로드되는 버그 방지
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('text/css', '.css')

import uvicorn
from fastapi import FastAPI, BackgroundTasks, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import threading
import time
from typing import Any, List, Optional

app = FastAPI(title="Winwin Crawler 3.3 API", description="Core engine API for crawler auto-tasks")

# 프론트엔드 React가 연동될 때 CORS 문제 방지. 로컬 앱/개발 서버만 허용한다.
_LOCAL_CORS_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://127.0.0.1:8001",
    "http://localhost:8001",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_LOCAL_CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_PUBLIC_API_PREFIXES = (
    "/api/license/",
    "/api/status",
    "/api/ping",
    "/api/shutdown",
)


@app.middleware("http")
async def require_local_license(request: Request, call_next):
    """Block automation APIs until the local license gate has passed."""
    path = request.url.path
    if request.method == "OPTIONS":
        return await call_next(request)
    if path.startswith("/api/") and not path.startswith(_PUBLIC_API_PREFIXES):
        try:
            from backend.license_manager import check_license_status
            if not check_license_status().get("is_valid"):
                return JSONResponse(
                    {"status": "unauthorized", "message": "라이선스 인증이 필요합니다."},
                    status_code=401,
                )
        except Exception:
            return JSONResponse(
                {"status": "unauthorized", "message": "라이선스 상태를 확인할 수 없습니다."},
                status_code=401,
            )
    return await call_next(request)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

ws_manager = ConnectionManager()

main_loop = None
_start_post_lock = threading.Lock()
_last_start_post_at = 0.0
_last_ping_time = time.time()

@app.on_event("startup")
async def startup_event():
    global main_loop
    main_loop = asyncio.get_running_loop()

    engine = get_engine()
    # 앱 시작 시 DB 데이터를 비우지 않고 그대로 유지합니다. (수집 데이터 보존)

    # --- 큐 매니저 연동 ---
    from backend.queue_manager import get_queue_manager
    qm = get_queue_manager()
    qm.rollback_running_jobs()
    qm.register_handler("POST", engine.run_posting_job)
    qm.start_worker()

    # 텔레그램 비서 모듈 로드 (자동으로 config_json에 저장된 설정으로 부팅됨)
    try:
        from backend.telegram_assistant import get_telegram_assistant
        assistant = get_telegram_assistant()
    except Exception as e:
        print(f"텔레그램 비서 시작 실패: {e}")

    # 하트비트 핑(Heartbeat Ping) 감시 스레드 기동
    def monitor_heartbeat():
        global _last_ping_time
        print("💓 [Heartbeat] 백엔드 셀프 킬 모니터링 데몬이 시작되었습니다.")
        # 초기 앱 로딩 시 브라우저가 뜨는 시간을 15초 동안 대기 보장
        time.sleep(15.0)
        
        # 순환 참조 방지 및 안전한 로드를 위해 로컬에서 큐 매니저 모듈 로드
        from backend.queue_manager import get_queue_manager

        while True:
            # 1. 크롤링 진행 여부 확인
            engine_active = False
            try:
                engine = get_engine()
                if engine.crawling_thread and engine.crawling_thread.is_alive():
                    engine_active = True
            except Exception:
                pass

            # 2. 작업 큐 진행 여부 확인
            queue_active = False
            try:
                qm = get_queue_manager()
                status = qm.get_queue_status()
                # PENDING 상태나 RUNNING 상태인 작업이 큐에 존재하면 백그라운드 활성 상태로 간주
                if status.get("pending", 0) > 0 or status.get("running", 0) > 0:
                    queue_active = True
            except Exception:
                pass

            # 크롤링이나 백그라운드 큐가 동작 중일 때는 자폭을 유예하기 위해 ping 수신 시간을 강제로 갱신합니다.
            if engine_active or queue_active:
                _last_ping_time = time.time()

            # 60초 이상 Ping 신호가 없으면 브라우저 강제 종료로 간주하고 백엔드를 자동 자폭시킴
            if time.time() - _last_ping_time > 60.0:
                print(f"🛑 [Heartbeat] 클라이언트의 Ping이 60초 이상 누락되었습니다. (최종 수신: {time.time() - _last_ping_time:.1f}초 전)")
                print("🛑 [Heartbeat] 프론트엔드 종료 감지. 백엔드 프로세스를 강제 자동 종료합니다.")
                import os
                import signal
                os.kill(os.getpid(), signal.SIGTERM)
                time.sleep(1.0)
                os._exit(0)
            time.sleep(5.0)

    threading.Thread(target=monitor_heartbeat, daemon=True).start()

    def on_engine_update():
        if main_loop and not main_loop.is_closed():
            # 다른 일반 스레드에서 호출되어도 메인 이벤트 루프로 안전하게 전달
            asyncio.run_coroutine_threadsafe(ws_manager.broadcast("UPDATE"), main_loop)

    engine.on_state_change = on_engine_update

    # 앱 구동 시 스케줄 동기화 실행
    try:
        from backend.scheduler_manager import sync_active_scheduler_tasks
        sync_active_scheduler_tasks()
        print("⏰ [스케줄러] 앱 시작 시 활성 스케줄링 예약 장착 완료!")
    except Exception as es:
        print(f"⏰ [스케줄러] 앱 시작 시 스케줄 장착 실패: {es}")

# React 빌드 정적파일 경로 (web-ui/dist)
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DIST_DIR = os.path.join(_BASE_DIR, "web-ui", "dist")

# 백엔드 엔진 연동
try:
    from backend.crawler_engine import get_engine
except ImportError:
    from crawler_engine import get_engine

try:
    from backend.endpoints.ai_pricing_learner import router as ai_pricing_router
except ImportError:
    from endpoints.ai_pricing_learner import router as ai_pricing_router
app.include_router(ai_pricing_router, prefix="/api")

# 💓 [Heartbeat] 프론트엔드 핑 수신 엔드포인트
@app.post("/api/ping")
def ping():
    global _last_ping_time
    _last_ping_time = time.time()
    return {"status": "pong"}

# 🛑 [Shutdown] 프론트엔드 종료 즉시 자폭 엔드포인트
@app.post("/api/shutdown")
def shutdown():
    print("🛑 [Shutdown] 프론트엔드로부터 즉시 종료 요청을 수신했습니다. 1초 후 프로세스를 강제 종료합니다.")
    def kill_self():
        time.sleep(1.0)
        import os, signal
        os.kill(os.getpid(), signal.SIGTERM)
        time.sleep(1.0)
        os._exit(0)
    threading.Thread(target=kill_self, daemon=True).start()
    return {"status": "success", "message": "shutting down..."}

# 기본 상태 테스트 (루트)
@app.get("/api/status")
def read_status():
    engine = get_engine()
    thread = engine.crawling_thread
    is_running = False
    if thread is not None:
        if hasattr(thread, 'isRunning'):
            is_running = thread.isRunning()
        elif hasattr(thread, 'is_alive'):
            is_running = thread.is_alive()
    return {
        "status": "ok",
        "crawling_running": is_running,
        "progress": engine.progress
    }

@app.get("/api/logs")
def get_logs(offset: int = None, limit: int = 1000, all: bool = False, category: str = "all"):
    engine = get_engine()

    # 카테고리 필터링
    if category and category != "all":
        logs_list = [l for l in engine.logs if l.get("category") == category]
    else:
        logs_list = engine.logs

    total_logs = len(logs_list)

    # all=true: 전체 복사용. 화면 표시 제한과 분리합니다.
    if all:
        selected_logs = logs_list[:]
    elif offset is not None:
        # offset 기반 증분 조회: 대시보드/WebSocket 갱신용
        if offset > total_logs:
            offset = total_logs
        if offset < 0:
            offset = 0
        selected_logs = logs_list[offset:]
    else:
        # 보조 로그창 기본 표시: 너무 길어지지 않게 최근 로그만 표시
        limit = max(1, min(limit, 5000))
        selected_logs = logs_list[-limit:]

    return {
        "status": "success",
        "count": len(selected_logs),
        "total": total_logs,
        "logs": selected_logs,
        "next_offset": total_logs
    }

class LoginRequest(BaseModel):
    platform: str
    profile_index: int = -1  # -1이면 수동 로그인
    ghost_mode: bool = False  # 유령 창 모드: 브라우저를 화면 밖으로 이동

class SystemSettingsSchema(BaseModel):
    forbidden_words: Optional[list] = None
    min_image_width: Optional[int] = None
    min_image_height: Optional[int] = None
    use_dynamic_ai_rules: Optional[bool] = None
    ai_budget_mode: Optional[str] = None
    ai_translate_during_crawl: Optional[bool] = None
    ai_use_vision_during_crawl: Optional[bool] = None
    ai_use_critic_review: Optional[bool] = None
    ai_use_image_ordering: Optional[bool] = None
    ai_analysis_product_limit: Optional[int] = None
    ai_analysis_telemetry_limit: Optional[int] = None
    crawl_operation_mode: Optional[str] = None
    prefer_api_image_urls: Optional[bool] = None
    save_crawl_snapshots: Optional[bool] = None
    max_item_retries: Optional[int] = None
    download_fail_skip_threshold: Optional[int] = None
    registration_guard_level: Optional[str] = None
    auto_load_last_products_on_start: Optional[bool] = None
    translation_engine: Optional[str] = None
    deepl_api_key: Optional[str] = None
    enable_auto_recovery: Optional[bool] = None
    auto_recovery_retry_limit: Optional[int] = None
    sqlite_timeout_seconds: Optional[float] = None
    session_heartbeat_check: Optional[bool] = None

class BandDiagnoseRequest(BaseModel):
    use_ai: bool = False

from backend.database import get_system_settings, save_system_settings
from backend.secret_store import get_secret, secret_status, set_many


def _bounded_int(value, default: int, min_value: int, max_value: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return max(min_value, min(max_value, parsed))


_CRAWL_OPERATION_PRESETS = {
    "minimum_cost": {
        "ai_budget_mode": "minimum",
        "ai_translate_during_crawl": False,
        "ai_use_vision_during_crawl": False,
        "ai_use_critic_review": False,
        "ai_use_image_ordering": False,
        "prefer_api_image_urls": True,
        "save_crawl_snapshots": False,
        "max_item_retries": 1,
        "download_fail_skip_threshold": 2,
        "registration_guard_level": "normal",
        "ai_analysis_product_limit": 10,
        "ai_analysis_telemetry_limit": 40,
    },
    "bulk_safe": {
        "ai_budget_mode": "economy",
        "ai_translate_during_crawl": False,
        "ai_use_vision_during_crawl": False,
        "ai_use_critic_review": False,
        "ai_use_image_ordering": False,
        "prefer_api_image_urls": True,
        "save_crawl_snapshots": False,
        "max_item_retries": 1,
        "download_fail_skip_threshold": 2,
        "registration_guard_level": "normal",
        "ai_analysis_product_limit": 20,
        "ai_analysis_telemetry_limit": 80,
    },
    "balanced": {
        "ai_budget_mode": "economy",
        "ai_translate_during_crawl": False,
        "ai_use_vision_during_crawl": False,
        "ai_use_critic_review": False,
        "ai_use_image_ordering": False,
        "prefer_api_image_urls": True,
        "save_crawl_snapshots": True,
        "max_item_retries": 2,
        "download_fail_skip_threshold": 3,
        "registration_guard_level": "normal",
        "ai_analysis_product_limit": 30,
        "ai_analysis_telemetry_limit": 120,
    },
    "precision": {
        "ai_budget_mode": "balanced",
        "ai_translate_during_crawl": True,
        "ai_use_vision_during_crawl": False,
        "ai_use_critic_review": False,
        "ai_use_image_ordering": False,
        "prefer_api_image_urls": True,
        "save_crawl_snapshots": True,
        "max_item_retries": 3,
        "download_fail_skip_threshold": 4,
        "registration_guard_level": "strict",
        "ai_analysis_product_limit": 60,
        "ai_analysis_telemetry_limit": 240,
    },
    "diagnostic": {
        "ai_budget_mode": "minimum",
        "ai_translate_during_crawl": False,
        "ai_use_vision_during_crawl": False,
        "ai_use_critic_review": False,
        "ai_use_image_ordering": False,
        "prefer_api_image_urls": True,
        "save_crawl_snapshots": True,
        "max_item_retries": 3,
        "download_fail_skip_threshold": 5,
        "registration_guard_level": "strict",
        "ai_analysis_product_limit": 80,
        "ai_analysis_telemetry_limit": 300,
    },
}


def _apply_ai_budget_policy(settings: dict, req: "StartCrawlRequest") -> dict:
    """환경설정의 AI 예산 모드를 크롤링 실행 설정으로 컴파일한다."""
    mode = str(settings.get("ai_budget_mode") or "economy").strip().lower()
    if mode not in {"minimum", "economy", "balanced", "quality"}:
        mode = "economy"

    user_requested_translate = bool(req.transOptions and req.transOptions.enable)
    translate_during_crawl = bool(settings.get("ai_translate_during_crawl", False)) and user_requested_translate
    use_vision = bool(settings.get("ai_use_vision_during_crawl", False))
    use_critic = bool(settings.get("ai_use_critic_review", False))
    use_image_ordering = bool(settings.get("ai_use_image_ordering", False))

    if mode == "minimum":
        translate_during_crawl = False
        use_vision = False
        use_critic = False
        use_image_ordering = False
    elif mode == "economy":
        use_vision = False
        use_critic = False
        use_image_ordering = False
    elif mode == "quality":
        translate_during_crawl = user_requested_translate
        use_vision = True
        use_critic = use_critic or bool(req.use_critic)
        use_image_ordering = True

    req.skip_vision = not use_vision
    req.use_critic = bool(use_critic)
    if req.transOptions:
        has_api_key = bool((req.transOptions.api_key or "").strip())
        req.transOptions.enable = bool(has_api_key and translate_during_crawl)

    return {
        "ai_budget_mode": mode,
        "ai_translate_during_crawl": translate_during_crawl,
        "ai_use_vision_during_crawl": use_vision,
        "ai_use_critic_review": req.use_critic,
        "ai_use_image_ordering": use_image_ordering,
        "ai_analysis_product_limit": _bounded_int(settings.get("ai_analysis_product_limit"), 30, 5, 200),
        "ai_analysis_telemetry_limit": _bounded_int(settings.get("ai_analysis_telemetry_limit"), 120, 20, 1000),
    }


def _apply_crawl_operation_policy(settings: dict) -> dict:
    """간단한 운영 프리셋과 세부 안정화 옵션을 실제 크롤러 설정으로 정규화한다."""
    mode = str(settings.get("crawl_operation_mode") or "balanced").strip().lower()
    if mode not in _CRAWL_OPERATION_PRESETS:
        mode = "balanced"

    guard_level = str(settings.get("registration_guard_level") or "normal").strip().lower()
    if guard_level not in {"off", "normal", "strict"}:
        guard_level = "normal"

    return {
        "crawl_operation_mode": mode,
        "prefer_api_image_urls": bool(settings.get("prefer_api_image_urls", True)),
        "save_crawl_snapshots": bool(settings.get("save_crawl_snapshots", True)),
        "max_item_retries": _bounded_int(settings.get("max_item_retries"), 2, 0, 5),
        "download_fail_skip_threshold": _bounded_int(settings.get("download_fail_skip_threshold"), 3, 1, 8),
        "registration_guard_level": guard_level,
        "block_resources": bool(settings.get("block_resources", True)),
    }


def _get_gemini_key(fallback: str = "") -> str:
    fallback = (fallback or "").strip()
    if fallback:
        return fallback
    secret_key = get_secret("gemini_api_key")
    if secret_key:
        return secret_key

    # 1. 환경변수 확인
    env_key = os.getenv("GEMINI_API_KEY", "")
    if env_key:
        return env_key

    return ""


def _get_telegram_credentials(token: str = "", chat_id: str = "") -> tuple[str, str]:
    return (
        (token or "").strip() or get_secret("telegram_bot_token"),
        (chat_id or "").strip() or get_secret("telegram_chat_id"),
    )

@app.post("/api/band/diagnose")
def diagnose_band_page(req: BandDiagnoseRequest = BandDiagnoseRequest()):
    engine = get_engine()
    return engine.diagnose_band_page(use_ai=req.use_ai)

class TelegramTestRequest(BaseModel):
    token: str
    chat_id: str
    gemini_key: str = None


class SecretSettingsRequest(BaseModel):
    gemini_key: Optional[str] = None
    telegram_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

@app.post("/api/test_telegram")
def test_telegram(req: TelegramTestRequest):
    import requests
    token, chat_id = _get_telegram_credentials(req.token, req.chat_id)
    gemini_key = _get_gemini_key(req.gemini_key)
    if not token or not chat_id:
        return {"status": "error", "message": "토큰과 Chat ID를 모두 입력해주세요."}

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": "🎉 <b>Winwin 크롤러 알림</b>\n\n안티그래비티와 텔레그램 연동 테스트가 성공적으로 완료되었습니다! 🚀",
        "parse_mode": "HTML"
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        data = resp.json()
        if data.get("ok"):
            set_many({
                "telegram_bot_token": token,
                "telegram_chat_id": chat_id,
                "gemini_api_key": gemini_key,
            })
            try:
                from backend.telegram_assistant import get_telegram_assistant
                get_telegram_assistant().start(token, chat_id, gemini_key)
            except Exception as e:
                print("비서 시작 에러:", e)
            return {"status": "success", "message": "테스트 메시지가 성공적으로 발송되었습니다. (수신 모드 활성화 됨)"}
        else:
            return {"status": "error", "message": f"발송 실패: {data.get('description', '알 수 없는 오류')}"}
    except Exception as e:
        return {"status": "error", "message": f"네트워크 오류: {str(e)}"}

@app.get("/api/vendor_history")
def api_get_vendor_history():
    from backend.database import get_db
    try:
        data = get_db().get_all_vendor_crawl_history()
        return {"status": "success", "data": data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/system_settings")
def api_get_system_settings():
    return get_system_settings()

@app.post("/api/system_settings")
def api_post_system_settings(settings: SystemSettingsSchema):
    incoming = settings.model_dump(exclude_none=True) if hasattr(settings, 'model_dump') else settings.dict(exclude_none=True)
    current = get_system_settings()
    requested_mode = str(incoming.get("crawl_operation_mode") or "").strip().lower()
    if requested_mode in _CRAWL_OPERATION_PRESETS:
        current.update(_CRAWL_OPERATION_PRESETS[requested_mode])
    current.update(incoming)
    current["ai_budget_mode"] = str(current.get("ai_budget_mode") or "economy").lower()
    if current["ai_budget_mode"] not in {"minimum", "economy", "balanced", "quality"}:
        current["ai_budget_mode"] = "economy"
    current["ai_analysis_product_limit"] = _bounded_int(current.get("ai_analysis_product_limit"), 30, 5, 200)
    current["ai_analysis_telemetry_limit"] = _bounded_int(current.get("ai_analysis_telemetry_limit"), 120, 20, 1000)
    crawl_policy = _apply_crawl_operation_policy(current)
    current.update(crawl_policy)
    save_system_settings(current)
    return {"status": "success"}


def _sync_secrets_to_env(secrets: dict[str, str | None]) -> None:
    env_path = os.path.join(_PROJECT_ROOT, ".env")
    
    mapping = {
        "gemini_api_key": "GEMINI_API_KEY",
        "telegram_bot_token": "TELEGRAM_BOT_TOKEN",
        "telegram_chat_id": "TELEGRAM_CHAT_ID"
    }
    
    lines = []
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            print(f"Error reading .env file: {e}")
            
    updated_env_vars = {}
    for sec_key, env_var in mapping.items():
        if sec_key in secrets and secrets[sec_key] is not None:
            updated_env_vars[env_var] = secrets[sec_key]
            
    new_lines = []
    found_vars = set()
    
    for line in lines:
        stripped = line.strip()
        matched = False
        for env_var, value in updated_env_vars.items():
            if stripped.startswith(f"{env_var}="):
                new_lines.append(f"{env_var}={value}\n")
                found_vars.add(env_var)
                matched = True
                break
        if not matched:
            new_lines.append(line)
            
    for env_var, value in updated_env_vars.items():
        if env_var not in found_vars:
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines[-1] += "\n"
            new_lines.append(f"{env_var}={value}\n")
            
    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except Exception as e:
        print(f"Error writing to .env file: {e}")


@app.get("/api/secrets/status")
def api_get_secret_status():
    status = secret_status(["gemini_api_key", "telegram_bot_token", "telegram_chat_id"])
    return {
        "status": "success",
        "gemini": status["gemini_api_key"],
        "telegram_token": status["telegram_bot_token"],
        "telegram_chat_id": status["telegram_chat_id"],
    }


@app.post("/api/secrets")
def api_save_secrets(req: SecretSettingsRequest):
    secrets_to_save = {
        "gemini_api_key": req.gemini_key,
        "telegram_bot_token": req.telegram_token,
        "telegram_chat_id": req.telegram_chat_id,
    }
    
    set_many(secrets_to_save)
    _sync_secrets_to_env(secrets_to_save)
    
    if req.gemini_key is not None:
        os.environ["GEMINI_API_KEY"] = req.gemini_key
    if req.telegram_token is not None:
        os.environ["TELEGRAM_BOT_TOKEN"] = req.telegram_token
    if req.telegram_chat_id is not None:
        os.environ["TELEGRAM_CHAT_ID"] = req.telegram_chat_id
        
    return api_get_secret_status()

@app.post("/api/login")
def login(req: LoginRequest):
    engine = get_engine()

    # 프로필이 선택된 경우 자격 증명 조회
    credentials = None
    if req.profile_index >= 0:
        from backend.profile_manager import get_credentials
        platform_key = "kakao" if "카카오" in req.platform else "band"
        credentials = get_credentials(platform_key, req.profile_index)
        if credentials:
            engine.add_log(f"🔌 [{req.platform}] 프로필 '{credentials['name']}' 로 자동 로그인 요청", "INFO", False)
        else:
            engine.add_log(f"🔌 [{req.platform}] 프로필 조회 실패 → 수동 로그인으로 전환", "INFO", False)
    else:
        engine.add_log(f"🔌 [{req.platform}] 브라우저 열기 요청 수신 (수동 로그인)", "INFO", False)

    import threading
    ghost_mode = req.ghost_mode
    if ghost_mode:
        engine.add_log(f"\U0001f47b 유령 창(Ghost) 모드 활성화 — 브라우저가 화면 밖에서 실행됩니다.", "INFO", False)
    t = threading.Thread(target=engine.open_browser, args=(req.platform, credentials, ghost_mode), daemon=True)
    t.start()
    return {"status": "success"}

# ── 라이선스(계정) 관리 API ──────────────────────────────────────────────────────

from backend.license_manager import check_license_status, register_license, unregister_license

@app.get("/api/license/status")
def get_license_status():
    return check_license_status()

class LicenseVerifyRequest(BaseModel):
    license_key: str

@app.post("/api/license/verify")
def verify_license_api(req: LicenseVerifyRequest):
    return register_license(req.license_key)

@app.post("/api/license/logout")
def logout_license_api():
    return unregister_license()

# ── 프로필 관리 API ──────────────────────────────────────────────────────

class ProfileCreateRequest(BaseModel):
    platform: str   # "kakao" 또는 "band"
    name: str
    login_id: str
    login_pw: str

class ProfileUpdateRequest(BaseModel):
    platform: str
    index: int
    name: str = None
    login_id: str = None
    login_pw: str = None

@app.get("/api/profiles")
def get_profiles(platform: str = None):
    from backend.profile_manager import list_profiles
    data = list_profiles(platform)
    return {"status": "success", "profiles": data}

@app.post("/api/profiles")
def create_profile(req: ProfileCreateRequest):
    from backend.profile_manager import add_profile
    result = add_profile(req.platform, req.name, req.login_id, req.login_pw)
    return result

@app.put("/api/profiles")
def update_profile_api(req: ProfileUpdateRequest):
    from backend.profile_manager import update_profile
    result = update_profile(req.platform, req.index, req.name, req.login_id, req.login_pw)
    return result

@app.delete("/api/profiles/{platform}/{index}")
def delete_profile_api(platform: str, index: int):
    from backend.profile_manager import delete_profile
    result = delete_profile(platform, index)
    return result

class LearnStyleRequest(BaseModel):
    url: str
    category: str = "공통"

@app.post("/api/learn-style")
def learn_style(req: LearnStyleRequest):
    engine = get_engine()
    engine.add_log(f"🧠 카카오스토리 AI 딥러닝 스타일 학습 요청 수신: {req.url}", "INFO", False)

    def run_learning():
        try:
            import asyncio
            from backend.kakaostory_crawler import KakaoStoryCrawler
            from backend.style_profiler import StyleProfiler

            # --- 보호 코드 추가: 마스터 프롬프트 덮어쓰기 방지 ---
            engine.add_log("⚠️ 수동으로 최적화된 마스터 프롬프트 보호 모드가 작동 중입니다. (AI 자동 덮어쓰기 차단됨)", "WARNING", False)
            engine.add_log(f"  🎉 사장님의 [{req.category}] 스타일 딥러닝 기능은 현재 마스터 템플릿 유지 관리를 위해 비활성화 되었습니다.", "SUCCESS", False)

        except Exception as e:
            engine.add_log(f"  ❌ AI 딥러닝 파이프라인 에러: {str(e)}", "ERROR", False)

    import threading
    t = threading.Thread(target=run_learning, daemon=True)
    t.start()
    return {"status": "success"}

class LearnStyleFromProductsRequest(BaseModel):
    api_key: str = ""
    category: str = "공통"
    platform: str = "네이버 밴드"
    limit: int = 1000

@app.post("/api/learn-style-from-products")
def learn_style_from_products(req: LearnStyleFromProductsRequest):
    """현재 크롤링 리스트를 사용해 실제 운영 글쓰기 기준서를 생성한다."""
    engine = get_engine()
    try:
        from backend.style_context import build_post_history_from_products
        from backend.style_profiler import StyleProfiler
    except ImportError:
        from style_context import build_post_history_from_products
        from style_profiler import StyleProfiler

    limit = max(1, min(int(req.limit or 1000), 1000))
    posts = build_post_history_from_products(engine.crawled_products, limit=limit)
    if not posts:
        return {"status": "error", "message": "분석할 크롤링 글이 없습니다. 먼저 밴드에서 글을 수집해주세요."}

    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_file_name = "user_post_history_밴드.json"
    data_path = os.path.join(base_dir, data_file_name)
    with open(data_path, "w", encoding="utf-8") as f:
        import json
        json.dump(posts, f, ensure_ascii=False, indent=2)

    def run_learning():
        try:
            # --- 보호 코드 추가: 마스터 프롬프트 덮어쓰기 방지 ---
            engine.add_log("⚠️ 수동으로 최적화된 마스터 프롬프트 보호 모드가 작동 중입니다. (AI 자동 덮어쓰기 차단됨)", "WARNING", False)
            engine.add_log("✅ 밴드 1000건 기준서 딥러닝 기능은 현재 마스터 템플릿 유지 관리를 위해 비활성화 되었습니다.", "SUCCESS", False)
        except Exception as e:
            engine.add_log(f"❌ 밴드 기준서 생성 중 오류: {e}", "ERROR", False)

    t = threading.Thread(target=run_learning, daemon=True)
    t.start()
    return {"status": "started", "count": len(posts), "message": f"마스터 프롬프트 보호 모드가 작동 중입니다. (덮어쓰기 차단됨)"}

@app.get("/api/style-prompt/{category}")
def get_style_prompt(category: str):
    import os
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, f"my_style_prompt_{category}.txt")
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return {"status": "success", "content": content}
    else:
        return {"status": "error", "message": f"아직 '{category}' 카테고리에 대한 딥러닝 분석 자료가 존재하지 않습니다.\n먼저 [AI 추출 시작] 버튼을 눌러 분석을 완료해주세요."}

@app.get("/api/style-analysis/{category}")
def get_style_analysis(category: str):
    """기존 스타일 프롬프트 텍스트를 Gemini에 보내 구조화된 시각 분석 데이터를 생성"""
    import os, json
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, f"my_style_prompt_{category}.txt")

    # 캐시 파일 (매번 AI 호출을 피하기 위해)
    cache_path = os.path.join(base_dir, f"style_analysis_cache_{category}.json")

    if not os.path.exists(file_path):
        return {"status": "error", "message": f"아직 '{category}' 카테고리에 대한 딥러닝 분석 자료가 존재하지 않습니다.\n먼저 [AI 추출 시작] 버튼을 눌러 분석을 완료해주세요."}

    with open(file_path, 'r', encoding='utf-8') as f:
        raw_text = f.read()

    # 원본 텍스트의 수정 시간 확인 (캐시가 최신인지 체크)
    txt_mtime = os.path.getmtime(file_path)

    if os.path.exists(cache_path):
        cache_mtime = os.path.getmtime(cache_path)
        if cache_mtime >= txt_mtime:
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cached = json.load(f)
                cached["raw_text"] = raw_text
                return {"status": "success", "analysis": cached}
            except:
                pass  # 캐시 손상 시 재생성

    # Gemini AI를 통해 구조화 분석
    api_key = _get_gemini_key()
    if not api_key:
        env_path = os.path.join(os.path.dirname(base_dir), ".env")
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GEMINI_API_KEY="):
                        api_key = line.split("=", 1)[1].strip()
                        break

    if not api_key:
        # API 키가 없으면 텍스트 기반 간이 분석 리턴
        return {"status": "success", "analysis": {
            "summary": f"[{category}] 카테고리의 스타일 분석 결과",
            "tone": {"style": "분석 불가", "formality": "API 키 필요", "description": "Gemini API 키가 설정되지 않아 상세 분석을 수행할 수 없습니다."},
            "symbols": [],
            "layout": {"order": ["제목", "설명", "컬러", "사이즈", "배송", "코드"], "description": "기본 레이아웃 구조"},
            "forbidden": [],
            "characteristics": {"friendliness": 50, "professionalism": 50, "conciseness": 50, "info_density": 50, "brand_feel": 50},
            "key_patterns": [],
            "raw_text": raw_text
        }}

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        analysis_prompt = f"""아래는 한국 B2B 패션 도매 판매자의 카카오스토리 포스팅에서 AI가 추출한 '스타일 지침서' 원문입니다.
이 지침서를 분석하여 아래 JSON 구조로 정확하게 변환해주세요.

[스타일 지침서 원문]
{raw_text}

[출력 JSON 구조 설명]
1. summary: 이 판매자의 스타일을 한 문장으로 요약 (한국어)
2. tone: 톤앤매너 분석
   - style: 핵심 톤 (예: "친근한 B2B 도매체", "시크한 프리미엄체")
   - formality: 격식 수준 (예: "반말+존댓말 혼용", "존댓말 위주")
   - description: 톤에 대한 2~3줄 설명
3. symbols: 자주 사용하는 기호/이모지 배열 (최대 10개, 각 항목은 symbol과 usage 포함)
4. layout: 글 구조 분석
   - order: 섹션 순서 배열 (예: ["제목", "구분선", "설명", "컬러", "사이즈", "배송", "코드"])
   - description: 레이아웃 특징 설명
5. forbidden: 금지 표현 배열 (최대 8개, 각 항목은 expression과 reason 포함)
6. characteristics: 0~100 수치 (레이더 차트용)
   - friendliness: 친근함 점수
   - professionalism: 전문성 점수
   - conciseness: 간결성 점수
   - info_density: 정보밀도 점수
   - brand_feel: 브랜드감 점수
7. key_patterns: 핵심 패턴 키워드 배열 (최대 6개, 이 판매자만의 특징적 패턴)"""

        res = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[analysis_prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "summary": {"type": "STRING"},
                        "tone": {"type": "OBJECT", "properties": {
                            "style": {"type": "STRING"},
                            "formality": {"type": "STRING"},
                            "description": {"type": "STRING"}
                        }},
                        "symbols": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
                            "symbol": {"type": "STRING"},
                            "usage": {"type": "STRING"}
                        }}},

                        "layout": {"type": "OBJECT", "properties": {

                            "order": {"type": "ARRAY", "items": {"type": "STRING"}},

                            "description": {"type": "STRING"}

                        }},

                        "forbidden": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {

                            "expression": {"type": "STRING"},

                            "reason": {"type": "STRING"}

                        }}},

                        "characteristics": {"type": "OBJECT", "properties": {

                            "friendliness": {"type": "INTEGER"},

                            "professionalism": {"type": "INTEGER"},

                            "conciseness": {"type": "INTEGER"},

                            "info_density": {"type": "INTEGER"},

                            "brand_feel": {"type": "INTEGER"}

                        }},

                        "key_patterns": {"type": "ARRAY", "items": {"type": "STRING"}}

                    },

                    "required": ["summary", "tone", "symbols", "layout", "forbidden", "characteristics", "key_patterns"]

                },

                temperature=0.1,

            )
        )

        if res and res.text:
            analysis_data = json.loads(res.text)
            # 캐시 저장
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(analysis_data, f, ensure_ascii=False, indent=2)

            analysis_data["raw_text"] = raw_text
            return {"status": "success", "analysis": analysis_data}
        else:
            return {"status": "error", "message": "AI 분석 응답이 비어있습니다."}

    except Exception as e:
        # AI 호출 실패 시에도 원본 텍스트와 함께 기본 데이터는 반환
        return {"status": "success", "analysis": {
            "summary": f"[{category}] 카테고리 스타일 지침서 (AI 분석 실패: {str(e)[:50]})",
            "tone": {"style": "분석 실패", "formality": "-", "description": f"AI 호출 오류: {str(e)[:100]}"},
            "symbols": [],
            "layout": {"order": ["제목", "설명", "컬러", "사이즈", "배송", "코드"], "description": "기본 레이아웃"},
            "forbidden": [],
            "characteristics": {"friendliness": 50, "professionalism": 50, "conciseness": 50, "info_density": 50, "brand_feel": 50},
            "key_patterns": [],
            "raw_text": raw_text
        }}

class TransOptions(BaseModel):
    enable: bool = False
    naver_fx: float = 195.0
    prefix: str = "AUTO"
    category: str = "남성의류"
    api_key: str = ""
    rules_text: str = ""

class StartCrawlRequest(BaseModel):
    platform: str
    count: int
    startDate: str
    endDate: str
    crawlAllDates: bool = True
    append: bool = False
    vendorUrl: Optional[str] = None
    headless: bool = False
    ghost_mode: bool = False
    skip_vision: bool = False
    disable_grouping: bool = False
    grouping_mode: str = "merge_color_options"
    telegramToken: Optional[str] = None
    telegramChatId: Optional[str] = None
    require_price: bool = False

    use_critic: bool = False

    transOptions: Optional[TransOptions] = None



def get_realtime_naver_fx(default_fx=195.0) -> float:

    import urllib.request

    import re

    url = 'https://m.search.naver.com/search.naver?query=%EC%A4%91%EA%B5%AD%ED%99%98%EC%9C%A8'

    try:

        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})

        html = urllib.request.urlopen(req, timeout=5).read().decode('utf-8')

        match = re.search(r'<strong class="price">([\\d\\.,]+)<\\/strong>', html)

        if not match:

            match = re.search(r'([\\d\\.,]+)\\s*<span class="sptxt">원<\\/span>', html)

        if match:

            return float(match.group(1).replace(',', ''))

    except Exception as e:

        print(f"네이버 환율 크롤링 실패: {e}")

    return default_fx



@app.post("/api/start_crawl")
def start_crawl(req: StartCrawlRequest):
    import traceback
    try:
        engine = get_engine()
        system_ai_settings = get_system_settings()
        resolved_telegram_token, resolved_telegram_chat_id = _get_telegram_credentials(req.telegramToken, req.telegramChatId)
        if req.transOptions and not (req.transOptions.api_key or "").strip():
            req.transOptions.api_key = _get_gemini_key()
        ai_policy = _apply_ai_budget_policy(system_ai_settings, req)
        crawl_policy = _apply_crawl_operation_policy(system_ai_settings)
        if req.transOptions and req.transOptions.naver_fx:
            real_fx = req.transOptions.naver_fx
        else:
            real_fx = 200.0 # 기본값

        engine.add_log(f"💱 최초 크롤링 시작: 프론트엔드 환경설정 환율 적용 완료 ({real_fx}원). [※ 품목 무관 일괄 적용]", "INFO", False)
        engine.add_log(
            "🧮 AI 예산 모드 적용: "
            f"{ai_policy['ai_budget_mode']} | 번역:{'ON' if ai_policy['ai_translate_during_crawl'] else 'OFF'} "
            f"| 비전:{'ON' if ai_policy['ai_use_vision_during_crawl'] else 'OFF'} "
            f"| 자가검열:{'ON' if ai_policy['ai_use_critic_review'] else 'OFF'} "
            f"| 사진AI정렬:{'ON' if ai_policy['ai_use_image_ordering'] else 'OFF'}",
            "INFO",
            False,
        )
        engine.add_log(
            "🎚️ 크롤링 운영 프리셋 적용: "
            f"{crawl_policy['crawl_operation_mode']} | API이미지:{'ON' if crawl_policy['prefer_api_image_urls'] else 'OFF'} "
            f"| 스냅샷:{'ON' if crawl_policy['save_crawl_snapshots'] else 'OFF'} "
            f"| 재시도:{crawl_policy['max_item_retries']} "
            f"| 다운로드실패스킵:{crawl_policy['download_fail_skip_threshold']} "
            f"| 등록가드:{crawl_policy['registration_guard_level']}",
            "INFO",
            False,
        )

        if req.transOptions:
            clean_rules_text = req.transOptions.rules_text
            if clean_rules_text:
                legacy_keywords = ["업데이트 프로젝트 지침", "시스템 내장 지침이 자동으로 적용됩니다", "웨이신 모멘트", "설명은 2줄~4줄", "선택한 스타일 지침"]
                for kw in legacy_keywords:
                    if kw in clean_rules_text:
                        clean_rules_text = ""
                        break
            req.transOptions.rules_text = clean_rules_text

        settings = {
            "platform": req.platform,
            "count": req.count,
            "startDate": req.startDate,
            "endDate": req.endDate,
            "crawlAllDates": req.crawlAllDates,
            "append": req.append,
            "headless": req.headless,
            "ghost_mode": req.ghost_mode,
            "skip_vision": req.skip_vision,
            "use_critic": req.use_critic,
            "require_price": req.require_price,
            "use_dynamic_ai_rules": bool(system_ai_settings.get("use_dynamic_ai_rules", False)),
            "ai_budget_mode": ai_policy["ai_budget_mode"],
            "ai_translate_during_crawl": ai_policy["ai_translate_during_crawl"],
            "ai_use_vision_during_crawl": ai_policy["ai_use_vision_during_crawl"],
            "ai_use_critic_review": ai_policy["ai_use_critic_review"],
            "ai_use_image_ordering": ai_policy["ai_use_image_ordering"],
            "ai_analysis_product_limit": ai_policy["ai_analysis_product_limit"],
            "ai_analysis_telemetry_limit": ai_policy["ai_analysis_telemetry_limit"],
            "crawl_operation_mode": crawl_policy["crawl_operation_mode"],
            "prefer_api_image_urls": crawl_policy["prefer_api_image_urls"],
            "save_crawl_snapshots": crawl_policy["save_crawl_snapshots"],
            "max_item_retries": crawl_policy["max_item_retries"],
            "download_fail_skip_threshold": crawl_policy["download_fail_skip_threshold"],
            "registration_guard_level": crawl_policy["registration_guard_level"],
            "block_resources": crawl_policy.get("block_resources", True),
            "disable_grouping": req.disable_grouping,
            "grouping_mode": req.grouping_mode,
            "vendorUrl": req.vendorUrl,
            "transOptions": req.transOptions.dict() if req.transOptions else None,
            "telegramToken": resolved_telegram_token,
            "telegramChatId": resolved_telegram_chat_id
        }

        if resolved_telegram_token and resolved_telegram_chat_id:
            engine.telegram_token = resolved_telegram_token
            engine.telegram_chat_id = resolved_telegram_chat_id
            try:
                from backend.telegram_assistant import get_telegram_assistant
                gemini_key = req.transOptions.api_key if req.transOptions else None
                get_telegram_assistant().start(resolved_telegram_token, resolved_telegram_chat_id, gemini_key)
            except Exception:
                pass

        # 텔레그램 재시작을 위해 설정 저장
        engine.last_crawl_settings = settings
        engine.start_crawling(settings)
        return {"status": "started"}
    except Exception as e:
        error_msg = traceback.format_exc()
        engine = get_engine()
        engine.add_log(f"❌ 크롤링 시작 중 오류: {str(e)}\n{error_msg}", "ERROR", False)
        return {"status": "error", "message": str(e)}

class AnalyzeResultRequest(BaseModel):
    products: list
    api_key: str = None
    analysis_payload: Optional[dict[str, Any]] = None

class RuleSimulationRequest(BaseModel):
    products: list = []
    telemetry_limit: int = 300

def _build_crawling_diagnostic_report_html(products: list, telemetry_events: list | None = None):
    """상품 리스트와 크롤링 telemetry를 계산형 대시보드 HTML로 만든다."""
    import html as html_mod
    import json
    import re
    from collections import Counter, defaultdict

    telemetry_events = telemetry_events or []
    total = len(products)

    def esc(value):
        return html_mod.escape(str(value if value is not None else ""))

    def short(value, limit=90):
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        return esc(text[:limit] + ("..." if len(text) > limit else ""))

    def as_list(value):
        if isinstance(value, list):
            return value
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                return [v for v in value.split(",") if v.strip()]
        return []

    def image_count(product):
        for key in ("image_files", "local_image_paths", "image_urls", "image_server_urls"):
            values = as_list(product.get(key))
            if values:
                return len(values)
        return 0

    def price_value(product):
        return str(product.get("price_input", product.get("price", "")) or "").strip()

    def price_ok(product):
        return price_value(product) not in ("", "0", "-", "단가미상", "None", "none")

    def sale_ok(product):
        sale = str(product.get("sale_price", "") or "").strip()
        return sale not in ("", "0", "-", "None", "none")

    def code_ok(product):
        code = str(product.get("product_code", "") or "").strip().upper()
        return bool(code and code != "AUTO")

    def translated_ok(product):
        title = str(product.get("title", "") or "").strip()
        desc = str(product.get("raw_description", product.get("description", "")) or "").strip()
        vendor = str(product.get("vendor_name", "") or "").strip()
        generic_title = not title or title.lower() in ("item", "unknown") or (vendor and title == f"{vendor} 상품")
        return bool(desc and not generic_title)

    price_success = sum(1 for p in products if price_ok(p))
    sale_success = sum(1 for p in products if sale_ok(p))
    code_success = sum(1 for p in products if code_ok(p))
    image_success = sum(1 for p in products if image_count(p) > 0)
    trans_success = sum(1 for p in products if translated_ok(p))

    def pct(value):
        return round(value / max(total, 1) * 100, 1)

    vendor_counter = Counter(p.get("vendor_name") or p.get("vendor_id") or "Unknown" for p in products)
    category_counter = Counter(p.get("vendor_category") or p.get("category") or "미분류" for p in products)
    image_counts = [image_count(p) for p in products]
    avg_images = round(sum(image_counts) / max(len(image_counts), 1), 1)
    img_buckets = Counter(
        "0장" if c == 0 else "1-3장" if c <= 3 else "4-7장" if c <= 7 else "8-10장" if c <= 10 else "11장+"
        for c in image_counts
    )
    telemetry_counter = Counter(ev.get("event_type", "") for ev in telemetry_events)
    telemetry_reason_counter = Counter(ev.get("reason", "") for ev in telemetry_events if ev.get("reason"))

    issue_rows = []
    code_groups = defaultdict(list)
    title_groups = defaultdict(list)
    for idx, p in enumerate(products, start=1):
        code = str(p.get("product_code", "") or "").strip()
        title = str(p.get("title", "") or "").strip()
        if code and code.upper() != "AUTO":
            code_groups[code].append(idx)
        normalized_title = re.sub(r"\s+", "", title)[:16]
        if normalized_title:
            title_groups[normalized_title].append(idx)

    repeated_codes = {code: rows for code, rows in code_groups.items() if len(rows) >= 2}
    repeated_titles = {title: rows for title, rows in title_groups.items() if len(rows) >= 2}

    for idx, p in enumerate(products, start=1):
        reasons = []
        raw_text = str(p.get("original_chinese", "") or "")
        code = str(p.get("product_code", "") or "")
        title = str(p.get("title", "") or "")
        img_count = image_count(p)
        price = price_value(p)
        if not price_ok(p):
            reasons.append("단가 미감지")
        if not sale_ok(p):
            reasons.append("판매가 0")
        if not code_ok(p):
            reasons.append("상품코드 AUTO")
        if img_count <= 1:
            reasons.append("이미지 부족")
        if len(raw_text) < 45:
            reasons.append("보충컷/사이즈표 의심")
        if code in repeated_codes:
            reasons.append("동일 코드 반복")
        norm_title = re.sub(r"\s+", "", title)[:16]
        if norm_title in repeated_titles:
            reasons.append("유사 제목 반복")
        if re.search(r"(搜索码|货号)\s*[：:]\s*\d+", raw_text) and price_ok(p):
            reasons.append("검색코드 단가 오인 가능")
        if reasons:
            issue_rows.append({
                "idx": idx,
                "title": title,
                "code": code,
                "price": price,
                "sale": p.get("sale_price", ""),
                "images": img_count,
                "reasons": reasons[:4],
                "raw": raw_text,
            })

    failed_price_rows = [row for row in issue_rows if "단가 미감지" in row["reasons"] or "상품코드 AUTO" in row["reasons"]]
    risky_price_rows = [row for row in issue_rows if "검색코드 단가 오인 가능" in row["reasons"]]

    def metric_card(label, value, sub, color):
        return f"""
        <div class="ww-card">
          <div class="ww-label">{label}</div>
          <div class="ww-value" style="color:{color};">{value}</div>
          <div class="ww-sub">{sub}</div>
        </div>"""

    def bar(label, value, color, count_text=""):
        value = max(0, min(100, float(value)))
        return f"""
        <div class="ww-bar-row">
          <div class="ww-bar-head"><span>{label}</span><b>{value:.1f}% {count_text}</b></div>
          <div class="ww-bar-track"><div class="ww-bar-fill" style="width:{value:.1f}%;background:{color};"></div></div>
        </div>"""

    def bucket_rows(counter):
        max_count = max(counter.values()) if counter else 1
        rows = []
        for label in ["0장", "1-3장", "4-7장", "8-10장", "11장+"]:
            count = counter.get(label, 0)
            width = round(count / max(max_count, 1) * 100, 1)
            rows.append(f"""
              <div class="ww-bucket">
                <span>{label}</span>
                <div class="ww-mini-track"><div class="ww-mini-fill" style="width:{width}%;"></div></div>
                <b>{count}</b>
              </div>""")
        return "".join(rows)

    def top_list(counter, limit=6):
        if not counter:
            return '<div class="ww-empty">데이터 없음</div>'
        max_count = max(counter.values())
        rows = []
        for label, count in counter.most_common(limit):
            width = round(count / max(max_count, 1) * 100, 1)
            rows.append(f"""
              <div class="ww-top-row">
                <span title="{esc(label)}">{short(label, 28)}</span>
                <div class="ww-mini-track"><div class="ww-mini-fill purple" style="width:{width}%;"></div></div>
                <b>{count}</b>
              </div>""")
        return "".join(rows)

    def issue_table(rows, limit=12):
        if not rows:
            return '<div class="ww-empty">현재 조건에서 표시할 위험 항목이 없습니다.</div>'
        trs = []
        for row in rows[:limit]:
            badges = "".join(f'<span class="ww-badge warn">{esc(reason)}</span>' for reason in row["reasons"])
            trs.append(f"""
              <tr>
                <td>{row['idx']}</td>
                <td><b>{short(row['title'], 34)}</b><div class="ww-muted">{short(row['raw'], 72)}</div></td>
                <td><code>{esc(row['code'] or '-')}</code></td>
                <td>{esc(row['price'] or '-')}</td>
                <td>{esc(row['sale'] or '-')}</td>
                <td>{row['images']}장</td>
                <td>{badges}</td>
              </tr>""")
        return f"""
        <div class="ww-table-wrap">
          <table class="ww-table">
            <thead><tr><th>#</th><th>상품/원문</th><th>코드</th><th>원가</th><th>판매가</th><th>이미지</th><th>진단</th></tr></thead>
            <tbody>{''.join(trs)}</tbody>
          </table>
        </div>"""

    telemetry_rows = []
    for ev in telemetry_events[:16]:
        meta = ev.get("metadata", {}) if isinstance(ev.get("metadata"), dict) else {}
        telemetry_rows.append(f"""
          <tr>
            <td><span class="ww-badge">{esc(ev.get('event_type', '-'))}</span></td>
            <td>{esc(ev.get('reason', '-'))}</td>
            <td>{short(ev.get('vendor_name') or ev.get('vendor_id') or '-')}</td>
            <td>{short(ev.get('raw_text') or '', 80)}</td>
            <td>{short(json.dumps(meta, ensure_ascii=False), 80)}</td>
          </tr>""")
    telemetry_table = f"""
      <div class="ww-table-wrap">
        <table class="ww-table compact">
          <thead><tr><th>이벤트</th><th>사유</th><th>업체</th><th>원문</th><th>메타</th></tr></thead>
          <tbody>{''.join(telemetry_rows) if telemetry_rows else '<tr><td colspan="5" class="ww-empty">telemetry 이벤트 없음</td></tr>'}</tbody>
        </table>
      </div>"""

    recommended_regex = r"(?:P|p|W|w|Q|q|¥|元|批|💰|🌟)\s*(\d{2,4})(?!\d)"
    guard_regex = r"(?:搜索码|搜素码|货号|款号|编号|SKU)\s*[：:]\s*\d+"
    critical_summary = []
    if pct(price_success) < 70:
        critical_summary.append("가격 파싱률이 낮습니다. `搜索码/货号` 숫자를 단가로 오인하지 않도록 guard 규칙이 필요합니다.")
    if failed_price_rows:
        critical_summary.append(f"단가/코드 실패 후보 {len(failed_price_rows)}건이 학습 적용 우선 대상입니다.")
    if telemetry_reason_counter:
        reason, count = telemetry_reason_counter.most_common(1)[0]
        critical_summary.append(f"크롤링 단계 telemetry 최다 사유는 `{esc(reason)}` {count}건입니다.")
    if not critical_summary:
        critical_summary.append("현재 표본에서는 치명 오류보다 품질 고도화 이슈가 중심입니다.")

    css = """
    <style>
      .ww-report{font-family:Inter,'Segoe UI',Arial,sans-serif;color:#e5edf8;background:#07111f;border:1px solid #1d3b63;border-radius:14px;overflow:hidden}
      .ww-hero{padding:22px 24px;background:linear-gradient(135deg,#0d2a4f,#1e3a8a 48%,#4c1d95);border-bottom:1px solid #2b4c7a}
      .ww-hero h2{margin:0;color:white;font-size:22px}.ww-hero p{margin:6px 0 0;color:#b8cef5;font-size:13px}
      .ww-section{padding:18px 20px;border-bottom:1px solid #17263b}.ww-section h3{margin:0 0 12px;color:#dbeafe;font-size:16px}
      .ww-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.ww-grid.two{grid-template-columns:1.1fr .9fr}
      .ww-card{background:#0d1b2e;border:1px solid #203856;border-radius:10px;padding:14px;min-height:86px}.ww-label{color:#8aa4c7;font-size:12px}.ww-value{font-size:26px;font-weight:850;margin-top:6px}.ww-sub{color:#64748b;font-size:12px;margin-top:4px}
      .ww-bar-row{margin:11px 0}.ww-bar-head{display:flex;justify-content:space-between;color:#cbd5e1;font-size:13px;margin-bottom:6px}.ww-bar-head b{color:#f8fafc}
      .ww-bar-track,.ww-mini-track{height:10px;background:#111827;border:1px solid #233752;border-radius:99px;overflow:hidden}.ww-bar-fill{height:100%;border-radius:99px}.ww-mini-track{height:8px;flex:1}.ww-mini-fill{height:100%;background:#38bdf8;border-radius:99px}.ww-mini-fill.purple{background:#a78bfa}
      .ww-bucket,.ww-top-row{display:flex;align-items:center;gap:10px;margin:9px 0;color:#cbd5e1;font-size:12px}.ww-bucket span{width:52px}.ww-top-row span{width:180px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ww-bucket b,.ww-top-row b{width:34px;text-align:right;color:#f8fafc}
      .ww-flow{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;align-items:stretch}.ww-node{background:#0d1b2e;border:1px solid #27496d;border-radius:10px;padding:14px;text-align:center;position:relative}.ww-node b{display:block;font-size:22px;color:#fff}.ww-node span{display:block;color:#8aa4c7;font-size:12px;margin-top:4px}
      .ww-node:after{content:'→';position:absolute;right:-13px;top:38%;color:#60a5fa;font-weight:900}.ww-node:last-child:after{content:''}
      .ww-callout{background:#0b2a3a;border:1px solid #1d78a6;border-radius:10px;padding:13px;color:#d9f2ff;margin:8px 0}.ww-callout.warn{background:#3a240b;border-color:#b7791f;color:#ffe7b5}
      .ww-table-wrap{overflow:auto;border:1px solid #233752;border-radius:10px}.ww-table{width:100%;border-collapse:collapse;background:#0b1424;font-size:12px}.ww-table th{position:sticky;top:0;background:#13243b;color:#93c5fd;text-align:left;padding:9px;border-bottom:1px solid #29415f}.ww-table td{padding:9px;border-bottom:1px solid #17263b;color:#dbeafe;vertical-align:top}.ww-table.compact td,.ww-table.compact th{padding:7px}
      .ww-muted{color:#7f93b2;font-size:11px;margin-top:4px}.ww-badge{display:inline-block;background:#1e3a5f;color:#93c5fd;border:1px solid #315985;border-radius:999px;padding:2px 7px;font-size:11px;margin:1px}.ww-badge.warn{background:#4a2515;color:#fdba74;border-color:#9a4d1f}
      .ww-empty{color:#64748b;text-align:center;padding:18px}.ww-code{background:#020617;border:1px solid #1e293b;color:#bef264;border-radius:8px;padding:12px;white-space:pre-wrap;font-size:12px}
      details.ww-details{background:#0d1b2e;border:1px solid #203856;border-radius:10px;margin-top:12px}details.ww-details summary{cursor:pointer;padding:12px 14px;color:#bfdbfe;font-weight:700}details.ww-details>div{padding:0 14px 14px}
      @media(max-width:900px){.ww-grid,.ww-grid.two,.ww-flow{grid-template-columns:1fr}.ww-node:after{content:''}}
    </style>
    """

    html = f"""
    {css}
    <div class="ww-report">
      <div class="ww-hero">
        <h2>AI 크롤링 데이터 정밀 진단 대시보드</h2>
        <p>총 {total}건 기준 · 가격/이미지/번역/코드/telemetry를 학습 적용 관점으로 재구성했습니다.</p>
      </div>
      <div class="ww-section">
        <div class="ww-grid">
          {metric_card("전체 상품", total, f"업체 {len(vendor_counter)}개 / 카테고리 {len(category_counter)}개", "#60a5fa")}
          {metric_card("가격 파싱률", f"{pct(price_success)}%", f"{price_success}/{total}건", "#fbbf24")}
          {metric_card("상품코드 성공률", f"{pct(code_success)}%", f"{code_success}/{total}건 AUTO 탈출", "#34d399")}
          {metric_card("평균 이미지", f"{avg_images}장", f"최소 {min(image_counts) if image_counts else 0}장 / 최대 {max(image_counts) if image_counts else 0}장", "#a78bfa")}
        </div>
      </div>
      <div class="ww-section">
        <h3>처리 파이프라인</h3>
        <div class="ww-flow">
          <div class="ww-node"><b>{telemetry_counter.get('candidate_soft_pass', 0) + total}</b><span>후보 유지/등록</span></div>
          <div class="ww-node"><b>{image_success}</b><span>이미지 확보</span></div>
          <div class="ww-node"><b>{price_success}</b><span>원가 파싱</span></div>
          <div class="ww-node"><b>{trans_success}</b><span>번역/제목 생성</span></div>
          <div class="ww-node"><b>{code_success}</b><span>판매 가능 코드</span></div>
        </div>
      </div>
      <div class="ww-section">
        <h3>동일상품 병합/사진 배치 기준</h3>
        <div class="ww-flow">
          <div class="ww-node"><b>1</b><span>货号/搜索码 추출</span></div>
          <div class="ww-node"><b>2</b><span>색상·품목 핵심어 비교</span></div>
          <div class="ww-node"><b>3</b><span>디테일/사이즈표 병합</span></div>
          <div class="ww-node"><b>4</b><span>대표 20장 압축</span></div>
          <div class="ww-node"><b>5</b><span>사이즈표 마지막</span></div>
        </div>
        <div class="ww-callout" style="margin-top:12px;">
          현지 웨이상 판매글은 메인 상품글 뒤에 `细节`, `无滤镜实拍`, `商品属性`, `货号/搜索码`, `尺码表/尺寸表` 포스팅이 이어지는 경우가 많습니다. 이 숫자들은 우선 상품 식별번호로 보고, 같은 품목·핵심어·코드 흐름이면 한 상품으로 묶은 뒤 색상별 앞/뒤 대표컷 → 대표색상 디테일 → 사이즈표 순서로 배치하는 것이 안전합니다.
        </div>
      </div>
      <div class="ww-section">
        <h3>핵심 진단</h3>
        {''.join(f'<div class="ww-callout warn">{item}</div>' for item in critical_summary)}
        <div class="ww-grid two" style="margin-top:12px;">
          <div class="ww-card">
            <h3>품질 지표</h3>
            {bar("가격 파싱", pct(price_success), "#f59e0b", f"({price_success}/{total})")}
            {bar("판매가 계산", pct(sale_success), "#22c55e", f"({sale_success}/{total})")}
            {bar("상품코드 생성", pct(code_success), "#38bdf8", f"({code_success}/{total})")}
            {bar("번역/제목", pct(trans_success), "#a78bfa", f"({trans_success}/{total})")}
          </div>
          <div class="ww-card">
            <h3>이미지 분포</h3>
            {bucket_rows(img_buckets)}
          </div>
        </div>
      </div>
      <div class="ww-section">
        <div class="ww-grid two">
          <div class="ww-card">
            <h3>업체 분포</h3>
            {top_list(vendor_counter)}
          </div>
          <div class="ww-card">
            <h3>카테고리 분포</h3>
            {top_list(category_counter)}
          </div>
        </div>
      </div>
      <div class="ww-section">
        <h3>문제 상품/학습 후보</h3>
        {issue_table(issue_rows)}
        <details class="ww-details" open>
          <summary>가격 실패/오인 가능 항목만 보기 ({len(failed_price_rows) + len(risky_price_rows)}건)</summary>
          <div>{issue_table(failed_price_rows + risky_price_rows, 16)}</div>
        </details>
      </div>
      <div class="ww-section">
        <h3>크롤링 telemetry</h3>
        <div class="ww-grid two">
          <div class="ww-card">
            <h3>이벤트 분포</h3>
            {top_list(telemetry_counter)}
          </div>
          <div class="ww-card">
            <h3>사유 분포</h3>
            {top_list(telemetry_reason_counter)}
          </div>
        </div>
        <details class="ww-details">
          <summary>최근 telemetry 원문 펼치기</summary>
          <div>{telemetry_table}</div>
        </details>
      </div>
      <div class="ww-section">
        <h3>바로 적용할 파서 개선안</h3>
        <div class="ww-callout">현재 톰브라운 표본에서는 `搜索码`/`货号` 숫자가 단가처럼 보이는 위험이 큽니다. 가격은 P/¥/元/批/💰/🌟 주변 숫자만 우선 인정하고, 검색코드/품번 주변 숫자는 guard로 제외하는 편이 안전합니다.</div>
        <div class="ww-code">price_regex = r"{esc(recommended_regex)}"
guard_regex = r"{esc(guard_regex)}"

if re.search(guard_regex, context) and not re.search(price_regex, context):
    price = "-"
else:
    price = re.search(price_regex, text).group(1)</div>
      </div>
    </div>
    """
    return html


def _compact_products_for_ai_analysis(products: list, limit: int = 80) -> list:
    def _compact_evidence(evidence: dict) -> dict:
        if not isinstance(evidence, dict):
            return {}
        return {
            "version": evidence.get("version", ""),
            "role": evidence.get("role", ""),
            "decision_stage": evidence.get("decision_stage", ""),
            "candidate_score": evidence.get("candidate_score"),
            "candidate_reasons": evidence.get("candidate_reasons", []),
            "identity": evidence.get("identity", {}),
            "price_candidates": (evidence.get("price_candidates") or [])[:5],
            "image_candidates": [
                {
                    "rank": c.get("rank"),
                    "source": c.get("source"),
                    "fingerprint": c.get("fingerprint"),
                    "confidence": c.get("confidence"),
                    "is_local": c.get("is_local"),
                }
                for c in (evidence.get("image_candidates") or [])[:10]
                if isinstance(c, dict)
            ],
            "raw_text_preview": evidence.get("raw_text_preview", ""),
        }

    compact = []
    for idx, product in enumerate((products or [])[:limit], start=1):
        image_count = len(product.get("image_files", []) or product.get("local_image_paths", []) or product.get("image_urls", []))
        source_posts = []
        for post in (product.get("source_posts") or [])[:8]:
            if not isinstance(post, dict):
                continue
            post_evidence = _compact_evidence(post.get("evidence", {}))
            source_posts.append({
                "item_key": post.get("item_key", ""),
                "goods_id": post.get("goods_id", ""),
                "shop_id": post.get("shop_id", ""),
                "role": post.get("role", ""),
                "decision": post.get("decision", ""),
                "codes": post.get("codes", []),
                "image_count": post.get("image_count", 0),
                "api_match": post.get("api_match", {}),
                "identity": post.get("identity", {}) or post_evidence.get("identity", {}),
                "price_candidates": post.get("price_candidates", []) or post_evidence.get("price_candidates", []),
                "image_candidate_sources": sorted({
                    c.get("source")
                    for c in (post.get("image_candidates", []) or post_evidence.get("image_candidates", []))
                    if isinstance(c, dict) and c.get("source")
                }),
                "evidence": post_evidence,
                "raw_text_preview": post.get("raw_text_preview", "") or (post.get("raw_text", "")[:180]),
            })
        decision_trace = []
        for trace in (product.get("decision_trace") or [])[:12]:
            if isinstance(trace, dict):
                decision_trace.append(trace)
            elif isinstance(trace, str) and trace.strip():
                decision_trace.append(trace[:500])
        compact.append({
            "idx": idx,
            "vendor_id": product.get("vendor_id", ""),
            "vendor_name": product.get("vendor_name", ""),
            "vendor_url": product.get("vendor_url", ""),
            "goods_id": product.get("goods_id", ""),
            "shop_id": product.get("shop_id", ""),
            "title": product.get("title", ""),
            "product_code": product.get("product_code", ""),
            "price_input": product.get("price_input", ""),
            "price_source": product.get("price_source", ""),
            "sale_price": product.get("sale_price", ""),
            "image_count": image_count,
            "created_at": product.get("created_at", ""),
            "identity_summary": product.get("identity_summary", {}),
            "evidence_items": [_compact_evidence(e) for e in (product.get("evidence_items") or [])[:6] if isinstance(e, dict)],
            "price_ocr_candidates": product.get("price_ocr_candidates", {}),
            "source_posts": source_posts,
            "decision_trace": decision_trace,
            "raw_text": (product.get("original_chinese") or product.get("raw_description") or "")[:1200],
        })
    return compact


def _build_ai_learning_analysis_html(ai_payload: dict, diagnostic_html: str = "") -> str:
    import html as html_mod
    import json

    def esc(value):
        return html_mod.escape(str(value if value is not None else ""))

    findings = ai_payload.get("vendor_findings", []) if isinstance(ai_payload, dict) else []
    rules = ai_payload.get("recommended_rule_updates", []) if isinstance(ai_payload, dict) else []
    risks = ai_payload.get("risk_cases", []) if isinstance(ai_payload, dict) else []

    finding_cards = []
    for finding in findings[:8]:
        finding_cards.append(f"""
          <div class="ai-card">
            <div class="ai-card-title">{esc(finding.get('vendor_name') or finding.get('vendor_id') or '업체 미상')}</div>
            <div class="ai-muted">신뢰도 {esc(finding.get('confidence', '-'))}</div>
            <p>{esc(finding.get('summary', ''))}</p>
            <div class="ai-tags">
              {''.join(f'<span>{esc(tag)}</span>' for tag in finding.get('key_patterns', [])[:6])}
            </div>
          </div>
        """)

    rule_rows = []
    for rule in rules[:16]:
        rule_rows.append(f"""
          <tr>
            <td>{esc(rule.get('vendor_id') or '-')}</td>
            <td>{esc(rule.get('target') or '-')}</td>
            <td>{esc(rule.get('suggestion') or '-')}</td>
            <td>{esc(rule.get('reason') or '-')}</td>
          </tr>
        """)

    risk_rows = []
    for risk in risks[:16]:
        risk_rows.append(f"""
          <tr>
            <td>{esc(risk.get('idx') or '-')}</td>
            <td>{esc(risk.get('type') or '-')}</td>
            <td>{esc(risk.get('evidence') or '-')}</td>
            <td>{esc(risk.get('fix') or '-')}</td>
          </tr>
        """)

    css = """
    <style>
      .ai-analysis{font-family:Inter,'Segoe UI',Arial,sans-serif;color:#e5edf8;background:#07111f;border:1px solid #1d3b63;border-radius:14px;overflow:hidden}
      .ai-hero{padding:22px 24px;background:linear-gradient(135deg,#312e81,#1e3a8a 45%,#0f766e);border-bottom:1px solid #2b4c7a}
      .ai-hero h2{margin:0;color:white;font-size:22px}.ai-hero p{margin:6px 0 0;color:#c7d2fe;font-size:13px}
      .ai-section{padding:18px 20px;border-bottom:1px solid #17263b}.ai-section h3{margin:0 0 12px;color:#dbeafe;font-size:16px}
      .ai-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.ai-card{background:#0d1b2e;border:1px solid #203856;border-radius:10px;padding:14px}.ai-card-title{font-weight:800;color:white;margin-bottom:4px}.ai-muted{color:#8aa4c7;font-size:12px}.ai-card p{color:#cbd5e1;font-size:13px;line-height:1.55}
      .ai-tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}.ai-tags span{background:#1e3a5f;color:#bfdbfe;border:1px solid #315985;border-radius:999px;padding:3px 8px;font-size:11px}
      .ai-callout{background:#0b2a3a;border:1px solid #1d78a6;border-radius:10px;padding:13px;color:#d9f2ff;margin:8px 0}.ai-callout.warn{background:#3a240b;border-color:#b7791f;color:#ffe7b5}
      .ai-table-wrap{overflow:auto;border:1px solid #233752;border-radius:10px}.ai-table{width:100%;border-collapse:collapse;background:#0b1424;font-size:12px}.ai-table th{background:#13243b;color:#93c5fd;text-align:left;padding:9px;border-bottom:1px solid #29415f}.ai-table td{padding:9px;border-bottom:1px solid #17263b;color:#dbeafe;vertical-align:top}
      .ai-code{white-space:pre-wrap;background:#020617;border:1px solid #1e293b;border-radius:10px;padding:12px;color:#c4b5fd;font-size:12px;max-height:420px;overflow:auto}
      @media(max-width:900px){.ai-grid{grid-template-columns:1fr}}
    </style>
    """

    diagnostic_block = f"""
      <details class="ai-section">
        <summary style="cursor:pointer;color:#bfdbfe;font-weight:800;">계산형 보조 진단 대시보드 펼치기</summary>
        <div style="margin-top:12px;">{diagnostic_html}</div>
      </details>
    """ if diagnostic_html else ""

    return f"""
    {css}
    <div class="ai-analysis">
      <div class="ai-hero">
        <h2>AI 딥러닝 적용용 분석자료</h2>
        <p>수집 원본과 파싱 결과를 AI가 읽고, 다음 단계의 규칙 강화에 사용할 분석자료로 정리했습니다.</p>
      </div>
      <div class="ai-section">
        <h3>AI 종합 판단</h3>
        <div class="ai-callout">{esc(ai_payload.get('executive_summary', 'AI 분석 요약이 없습니다.'))}</div>
        <div class="ai-callout warn">{esc(ai_payload.get('primary_learning_goal', '우선 학습 목표가 비어 있습니다.'))}</div>
      </div>
      <div class="ai-section">
        <h3>업체/패턴별 분석</h3>
        <div class="ai-grid">{''.join(finding_cards) if finding_cards else '<div class="ai-muted">업체 분석 없음</div>'}</div>
      </div>
      <div class="ai-section">
        <h3>딥러닝 적용 후보 규칙</h3>
        <div class="ai-table-wrap">
          <table class="ai-table">
            <thead><tr><th>업체</th><th>대상</th><th>제안 규칙</th><th>근거</th></tr></thead>
            <tbody>{''.join(rule_rows) if rule_rows else '<tr><td colspan="4">추천 규칙 없음</td></tr>'}</tbody>
          </table>
        </div>
      </div>
      <div class="ai-section">
        <h3>오판/오류 학습 후보</h3>
        <div class="ai-table-wrap">
          <table class="ai-table">
            <thead><tr><th>#</th><th>유형</th><th>근거</th><th>수정 방향</th></tr></thead>
            <tbody>{''.join(risk_rows) if risk_rows else '<tr><td colspan="4">위험 후보 없음</td></tr>'}</tbody>
          </table>
        </div>
      </div>
      <div class="ai-section">
        <h3>분석자료 JSON</h3>
        <div class="ai-code">{esc(json.dumps(ai_payload, ensure_ascii=False, indent=2))}</div>
      </div>
      {diagnostic_block}
    </div>
    """


def _generate_ai_learning_analysis_payload(products: list, telemetry_events: list, api_key: str, product_limit: int = 80, telemetry_limit: int = 100) -> dict:
    import json
    from google import genai

    client = genai.Client(api_key=api_key)
    compact_products = _compact_products_for_ai_analysis(products, limit=product_limit)
    compact_telemetry = []
    for event in (telemetry_events or [])[:telemetry_limit]:
        compact_telemetry.append({
            "event_type": event.get("event_type", ""),
            "vendor_id": event.get("vendor_id", ""),
            "vendor_name": event.get("vendor_name", ""),
            "reason": event.get("reason", ""),
            "raw_text": (event.get("raw_text") or "")[:600],
            "metadata": event.get("metadata", {}),
        })

    prompt = f"""
너는 웨이상(Szwego) 크롤링 결과를 분석해서, 이후 AI 규칙 강화 단계에 넣을 '딥러닝 적용용 분석자료'를 만드는 전문가다.

목표:
- 단순 현황 요약이 아니라, 다음 단계의 AI 분석 기준/키워드/패턴/점수/추천 기준에 반영할 수 있는 구조화 자료를 만든다.
- 특히 같은 제품 포스팅 병합 기준, 货号/搜索码와 가격 오인 방지, 색상별 앞뒤/디테일/사이즈표 사진 배치 규칙을 분석한다.
- 상품별 source_posts/decision_trace가 있으면 실제 크롤러가 왜 묶었고 왜 나눴는지의 근거로 보고, 업체별 포스팅 규칙으로 컴파일한다.
- source_posts.evidence / identity / price_candidates / image_candidates는 크롤러가 남긴 판단 증거다. 원문 감상보다 이 증거의 신뢰도와 후보 출처를 우선해서 규칙을 제안한다.
- identity confidence가 낮은 포스팅은 중복 확정/상품 병합 규칙을 강하게 만들지 말고, API/goods_id/image fingerprint 보강 규칙을 먼저 제안한다.
- 실제 규칙 파일 저장은 하지 않는다. 지금은 적용 전 분석자료만 만든다.

반드시 JSON 객체만 출력해라. 마크다운 금지.

출력 스키마:
{{
  "executive_summary": "전체 분석 요약",
  "primary_learning_goal": "이번 자료로 AI 기준에 가장 먼저 반영해야 할 목표",
  "vendor_findings": [
    {{
      "vendor_id": "업체 ID",
      "vendor_name": "업체명",
      "summary": "업체별 포스팅/가격/병합 패턴 요약",
      "key_patterns": ["패턴1", "패턴2"],
      "confidence": 0.0
    }}
  ],
  "recommended_rule_updates": [
    {{
      "vendor_id": "업체 ID 또는 global",
      "target": "price_regex|price_guard|grouping_rules|matching_rules|image_order_rules|skip_conditions",
      "suggestion": "적용 후보 규칙",
      "reason": "이 규칙이 필요한 근거"
    }}
  ],
  "risk_cases": [
    {{
      "idx": 1,
      "type": "price_misread|wrong_split|wrong_merge|image_order|missing_price|auto_code",
      "evidence": "원문/결과 근거",
      "fix": "학습 적용 방향"
    }}
  ],
  "same_product_criteria": {{
    "text_rules": ["같은 상품으로 묶는 텍스트 기준"],
    "image_rules": ["같은 상품으로 묶는 사진 기준"],
    "boundary_rules": ["새 상품으로 끊는 기준"]
  }},
  "image_order_policy": {{
    "max_images": 20,
    "order": ["색상별 앞면", "색상별 뒷면", "대표색상 디테일", "사이즈표 마지막"],
    "fallback": "AI가 확신하지 못할 때 적용할 순서"
  }},
  "compiled_vendor_rules": [
    {{
      "vendor_id": "업체 ID 또는 global",
      "vendor_name": "업체명",
      "posting_type": "single|split|mixed",
      "identity_keys": ["货号", "款号", "搜索码", "商品编号"],
        "price_policy": {{
        "explicit_patterns": ["P\\\\s*(\\\\d+)", "¥\\\\s*(\\\\d+)"],
        "guard_keywords": ["货号", "款号", "规格", "码数", "尺码", "搜索码"],
        "missing_price_behavior": "reject|allow_but_mark_missing|use_vendor_default",
        "long_number_price_rule": "none|last_3_digits|identifier_tail_3",
        "identifier_tail_price": false,
        "identifier_tail_digits": 3
      }},
      "boundary_policy": {{
        "new_product_signals": ["新款", "上新", "主图"],
        "supplement_signals": ["细节", "实拍", "尺码表", "尺寸表", "商品属性"],
        "same_product_priority": ["same_identity_key", "same_title_terms", "vision_similarity"],
        "split_when_multiple_identity_keys": true
      }},
      "image_policy": {{
        "max_images": 20,
        "order": ["color_front_back", "representative_detail", "size_chart_last"]
      }},
      "scoring_policy": {{
        "candidate_keep_threshold": 4,
        "duplicate_keep_threshold": 4,
        "new_product_threshold": 5,
        "supplement_threshold": -4,
        "min_images_override": 0,
        "weights": {{
          "candidate_identity_code": 4,
          "candidate_price_signal": 3,
          "candidate_image_count_4_plus": 3,
          "candidate_product_context": 2,
          "boundary_code_signal": 3,
          "boundary_price_signal": 2,
          "boundary_new_product_signal": 2,
          "boundary_supplement_signal": -3,
          "boundary_role_detail": -2,
          "boundary_role_spec": -2,
          "boundary_role_size": -2
        }}
      }},
      "confidence": 0.0,
      "change_reason": "이 실행 규칙이 필요한 이유"
    }}
  ],
  "application_notes": "다음 'AI 분석자료 딥러닝 적용' 단계에서 참고할 설명"
}}

[수집 상품/파싱 결과]
{json.dumps(compact_products, ensure_ascii=False)}

[크롤링 telemetry]
{json.dumps(compact_telemetry, ensure_ascii=False)}
"""

    res = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config={"temperature": 0.15}
    )
    text = (getattr(res, "text", "") or "").strip()
    if text.startswith("```json"):
        text = text[7:].strip()
    if text.startswith("```"):
        text = text[3:].strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    return json.loads(text)


@app.post("/api/analyze_crawling_result")
def analyze_crawling_result(req: AnalyzeResultRequest):
    try:
        # AI 분석 전 자동 백업 생성
        try:
            from backend.database import get_db
            db = get_db()
            db_count = db.count_all_products()
            if db_count > 0:
                db.backup_current_products(custom_name=f"AI 분석 시점 백업 ({db_count}건)")
        except Exception as e:
            print(f"[AI 분석 백업 실패] {e}")
            pass

        ai_settings = get_system_settings()
        telemetry_limit = _bounded_int(ai_settings.get("ai_analysis_telemetry_limit"), 120, 20, 1000)
        product_limit = _bounded_int(ai_settings.get("ai_analysis_product_limit"), 30, 5, 200)
        telemetry_events = []
        try:
            from backend.database import get_db
            telemetry_events = get_db().get_recent_crawl_events(
                platform="weishang",
                event_types=[
                    "candidate_rejected",
                    "candidate_soft_pass",
                    "price_parse_failed",
                    "download_empty",
                    "product_download_empty",
                    "product_discarded",
                    "duplicate_skipped",
                    "candidate_retry",
                    "candidate_retry_exhausted",
                    "boundary_decision",
                    "candidate_snapshot",
                    "api_packet_hit",
                ],
                limit=telemetry_limit,
            )
        except Exception:
            telemetry_events = []

        api_key = _get_gemini_key(req.api_key)
        if not api_key:
            return {"status": "error", "message": "AI 딥러닝 적용용 분석자료를 만들려면 Gemini API 키가 필요합니다."}

        diagnostic_html = _build_crawling_diagnostic_report_html(req.products or [], telemetry_events)
        analysis_payload = _generate_ai_learning_analysis_payload(
            req.products or [],
            telemetry_events,
            api_key,
            product_limit=product_limit,
            telemetry_limit=min(telemetry_limit, 300),
        )
        html_content = _build_ai_learning_analysis_html(analysis_payload, diagnostic_html)
        
        # 분석 히스토리 로컬 저장
        from backend.analysis_history import save_analysis_history
        prod_count = len(req.products) if req.products else 0
        summary_text = "업체 크롤링 AI 분석"
        file_id = save_analysis_history(prod_count, html_content, summary_text, analysis_payload)
        
        return {"status": "success", "html": html_content, "analysis_payload": analysis_payload, "file_id": file_id}

    except Exception as e:
        return {"status": "error", "message": f"AI 분석자료 생성 중 오류 발생: {str(e)}"}


@app.get("/api/analysis_history")
def get_history_list():
    from backend.analysis_history import get_analysis_list
    return {"status": "success", "history": get_analysis_list()}

@app.get("/api/analysis_history/{file_id}")
def get_history_detail(file_id: str):
    from backend.analysis_history import get_analysis_detail
    data = get_analysis_detail(file_id)
    if data:
        return {"status": "success", "detail": data}
    return {"status": "error", "message": "해당 분석 자료를 찾을 수 없습니다."}


@app.get("/api/weishang/snapshots")
def get_weishang_snapshots(limit: int = 80):
    """저장된 웨이상 HTML/API 스냅샷 목록."""
    try:
        from backend.weishang_diagnostics import list_weishang_snapshots
        return {"status": "success", "snapshots": list_weishang_snapshots(limit)}
    except Exception as e:
        return {"status": "error", "message": f"웨이상 스냅샷 목록 조회 실패: {str(e)}"}


@app.get("/api/weishang/snapshots/{snapshot_id}")
def get_weishang_snapshot(snapshot_id: str, include_html: bool = False, include_api: bool = True):
    """특정 스냅샷 상세. 기본은 HTML 본문을 제외해 응답을 가볍게 유지한다."""
    try:
        from backend.weishang_diagnostics import load_weishang_snapshot
        snapshot = load_weishang_snapshot(snapshot_id, include_html=include_html, include_api=include_api)
        if not snapshot:
            return {"status": "error", "message": "스냅샷을 찾을 수 없습니다."}
        return {"status": "success", "snapshot": snapshot}
    except Exception as e:
        return {"status": "error", "message": f"웨이상 스냅샷 조회 실패: {str(e)}"}


@app.get("/api/weishang/snapshots/{snapshot_id}/replay")
def replay_weishang_snapshot(snapshot_id: str):
    """실제 웨이상 접속 없이 저장된 스냅샷으로 역할/goods_id/API 매칭 상태를 재현."""
    try:
        from backend.weishang_diagnostics import replay_snapshot
        return replay_snapshot(snapshot_id)
    except Exception as e:
        return {"status": "error", "message": f"웨이상 스냅샷 리플레이 실패: {str(e)}"}


@app.get("/api/weishang/goods_id_stats")
def get_weishang_goods_id_stats(limit: int = 500):
    """업체별 goods_id/API/텍스트/이미지 fingerprint 식별 비율."""
    try:
        from backend.database import get_db
        from backend.weishang_diagnostics import summarize_identity_stats
        events = get_db().get_recent_crawl_events(
            platform="weishang",
            event_types=[
                "candidate_snapshot",
                "api_packet_hit",
                "duplicate_skipped",
                "boundary_decision",
                "candidate_retry",
                "candidate_retry_exhausted",
                "download_empty",
                "product_download_empty",
            ],
            limit=max(1, min(int(limit or 500), 3000)),
        )
        return {"status": "success", "stats": summarize_identity_stats(events)}
    except Exception as e:
        return {"status": "error", "message": f"goods_id 식별 통계 조회 실패: {str(e)}"}


@app.post("/api/weishang/rule_simulator")
def simulate_weishang_rules(req: RuleSimulationRequest):
    """source_posts/decision_trace 기준으로 규칙 적용 전 영향도를 미리 계산."""
    try:
        from backend.database import get_db
        from backend.weishang_diagnostics import simulate_decision_trace, summarize_identity_stats
        products = req.products or get_engine().crawled_products
        events = get_db().get_recent_crawl_events(
            platform="weishang",
            event_types=[
                "candidate_snapshot",
                "api_packet_hit",
                "duplicate_skipped",
                "boundary_decision",
                "candidate_retry",
                "candidate_retry_exhausted",
            ],
            limit=max(1, min(int(req.telemetry_limit or 300), 3000)),
        )
        return {
            "status": "success",
            "simulation": simulate_decision_trace(products or []),
            "identity_stats": summarize_identity_stats(events),
        }
    except Exception as e:
        return {"status": "error", "message": f"규칙 시뮬레이터 실행 실패: {str(e)}"}


@app.get("/api/ai_dynamic_overrides/summary")
def get_ai_dynamic_overrides_summary():
    """현재 저장되어 다음 크롤링에 적용될 AI 동적 분석 기준 요약."""
    import json
    try:
        override_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_dynamic_overrides.json")
        if not os.path.exists(override_file):
            try:
                current_settings = get_system_settings()
            except Exception:
                current_settings = {}
            return {
                "status": "success",
                "configured": False,
                "enabled": bool(current_settings.get("use_dynamic_ai_rules", False)),
                "applied_on_next_crawl": False,
                "file": override_file,
                "message": "저장된 AI 동적 분석 기준이 없습니다.",
            }

        with open(override_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        try:
            current_settings = get_system_settings()
        except Exception:
            current_settings = {}

        meta = data.get("_meta", {}) if isinstance(data, dict) else {}
        vendor_rules = {k: v for k, v in data.items() if k != "_meta" and isinstance(v, dict)}
        preview = {}
        for vendor_id, rule in list(vendor_rules.items())[:10]:
            preview[vendor_id] = {
                key: rule.get(key)
                for key in [
                    "name",
                    "category",
                    "posting_pattern",
                    "pricing_pattern",
                    "price_regex",
                    "grouping_rules",
                    "matching_rules",
                    "change_reason",
                    "generation",
                ]
                if rule.get(key) not in (None, "")
            }

        return {
            "status": "success",
            "configured": True,
            "enabled": bool(current_settings.get("use_dynamic_ai_rules", False)),
            "applied_on_next_crawl": bool(current_settings.get("use_dynamic_ai_rules", False)) and len(vendor_rules) > 0,
            "file": override_file,
            "meta": meta,
            "vendor_count": len(vendor_rules),
            "preview": preview,
        }
    except Exception as e:
        return {"status": "error", "message": f"AI 동적 분석 기준 요약 조회 실패: {str(e)}"}

def _build_learning_report_html(generation, total_products, total_success, total_failed,
                                 updated_count, new_count, merged_overrides, vendor_groups):
    """학습 결과를 시각적 HTML 리포트로 생성"""
    import html as html_mod

    fail_rate = round(total_failed / max(total_products, 1) * 100, 1)
    success_rate = round(total_success / max(total_products, 1) * 100, 1)

    # ── 세대간 성능 비교(Delta) 계산 ──
    history = merged_overrides.get("_meta", {}).get("history", [])
    prev_metrics = None
    curr_metrics = history[-1].get("metrics", {}) if history else {}
    if len(history) >= 2:
        prev_metrics = history[-2].get("metrics", {})

    def _delta_html(curr_val, prev_val, unit="%"):
        """이전 세대 대비 변화량을 화살표+색상으로 표시"""
        if prev_val is None:
            return '<span style="color:#64748b;font-size:11px;">— (최초)</span>'
        diff = round(curr_val - prev_val, 1)
        if diff > 0:
            return f'<span style="color:#34d399;font-size:12px;font-weight:700;">↑{diff}{unit}</span>'
        elif diff < 0:
            return f'<span style="color:#f87171;font-size:12px;font-weight:700;">↓{abs(diff)}{unit}</span>'
        else:
            return f'<span style="color:#64748b;font-size:12px;">→ 변화없음</span>'

    # 세대간 비교 카드 HTML 생성
    delta_section = ""
    if curr_metrics:
        c_price = curr_metrics.get("price_parse_rate", 0)
        c_trans = curr_metrics.get("translation_rate", 0)
        c_img = curr_metrics.get("image_rate", 0)
        c_overall = curr_metrics.get("overall_success_rate", 0)
        p_price = prev_metrics.get("price_parse_rate") if prev_metrics else None
        p_trans = prev_metrics.get("translation_rate") if prev_metrics else None
        p_img = prev_metrics.get("image_rate") if prev_metrics else None
        p_overall = prev_metrics.get("overall_success_rate") if prev_metrics else None

        prev_gen_label = f"Gen#{generation-1}" if prev_metrics else "—"
        regression_warning = ""
        if prev_metrics:
            if c_overall < p_overall:
                regression_warning = f"""<div style="background:#f8717122;border:1px solid #f87171;border-radius:8px;padding:12px;margin-bottom:16px;text-align:center;">
                    <span style="color:#f87171;font-weight:700;">⚠️ 회귀 감지! 전체 성공률이 {prev_gen_label}({p_overall}%) 대비 {round(p_overall - c_overall, 1)}%p 하락했습니다. 이전 세대 백업을 확인하세요.</span>
                </div>"""
            elif c_overall > p_overall:
                regression_warning = f"""<div style="background:#34d39922;border:1px solid #34d399;border-radius:8px;padding:12px;margin-bottom:16px;text-align:center;">
                    <span style="color:#34d399;font-weight:700;">✅ 성능 개선 확인! 전체 성공률이 {prev_gen_label}({p_overall}%) 대비 {round(c_overall - p_overall, 1)}%p 상승했습니다.</span>
                </div>"""

        delta_section = f"""
        <div style="margin-bottom:20px;">
            <h3 style="color:#c084fc;font-size:16px;margin-bottom:12px;border-bottom:1px solid #1e293b;padding-bottom:8px;">
                📊 세대간 성능 비교 (Performance Delta)
            </h3>
            {regression_warning}
            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;">
                <div style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:14px;text-align:center;">
                    <div style="font-size:11px;color:#94a3b8;margin-bottom:4px;">전체 성공률</div>
                    <div style="font-size:22px;font-weight:800;color:#60a5fa;">{c_overall}%</div>
                    <div style="margin-top:4px;">{_delta_html(c_overall, p_overall, '%p')}</div>
                    <div style="font-size:10px;color:#475569;margin-top:2px;">{prev_gen_label}: {p_overall if p_overall is not None else '—'}%</div>
                </div>
                <div style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:14px;text-align:center;">
                    <div style="font-size:11px;color:#94a3b8;margin-bottom:4px;">💰 가격 파싱률</div>
                    <div style="font-size:22px;font-weight:800;color:#fbbf24;">{c_price}%</div>
                    <div style="margin-top:4px;">{_delta_html(c_price, p_price, '%p')}</div>
                    <div style="font-size:10px;color:#475569;margin-top:2px;">{prev_gen_label}: {p_price if p_price is not None else '—'}%</div>
                </div>
                <div style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:14px;text-align:center;">
                    <div style="font-size:11px;color:#94a3b8;margin-bottom:4px;">🌐 번역 커버리지</div>
                    <div style="font-size:22px;font-weight:800;color:#a78bfa;">{c_trans}%</div>
                    <div style="margin-top:4px;">{_delta_html(c_trans, p_trans, '%p')}</div>
                    <div style="font-size:10px;color:#475569;margin-top:2px;">{prev_gen_label}: {p_trans if p_trans is not None else '—'}%</div>
                </div>
                <div style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:14px;text-align:center;">
                    <div style="font-size:11px;color:#94a3b8;margin-bottom:4px;">🖼️ 이미지 커버리지</div>
                    <div style="font-size:22px;font-weight:800;color:#2dd4bf;">{c_img}%</div>
                    <div style="margin-top:4px;">{_delta_html(c_img, p_img, '%p')}</div>
                    <div style="font-size:10px;color:#475569;margin-top:2px;">{prev_gen_label}: {p_img if p_img is not None else '—'}%</div>
                </div>
            </div>
        </div>"""
    history_rows = ""
    for h in history[-10:]:  # 최근 10개만
        history_rows += f"""<tr>
            <td style="padding:6px 10px;border-bottom:1px solid #1e293b;text-align:center;color:#60a5fa;font-weight:bold;">#{h.get('generation','?')}</td>
            <td style="padding:6px 10px;border-bottom:1px solid #1e293b;color:#94a3b8;">{h.get('timestamp','')[:16].replace('T',' ')}</td>
            <td style="padding:6px 10px;border-bottom:1px solid #1e293b;text-align:center;color:#e2e8f0;">{h.get('total_data',0)}</td>
            <td style="padding:6px 10px;border-bottom:1px solid #1e293b;text-align:center;color:#f87171;">{h.get('failed_data',0)}</td>
            <td style="padding:6px 10px;border-bottom:1px solid #1e293b;text-align:center;color:#34d399;">{h.get('success_data',0)}</td>
            <td style="padding:6px 10px;border-bottom:1px solid #1e293b;text-align:center;color:#fbbf24;">{h.get('updated_vendors',0)}개 갱신 / {h.get('new_vendors',0)}개 신규</td>
        </tr>"""

    # 업체별 학습된 규칙 카드 생성
    vendor_cards = ""
    for vid, rule in merged_overrides.items():
        if vid == "_meta" or not isinstance(rule, dict):
            continue
        vendor_name = rule.get("vendor", rule.get("vendor_id", vid))
        change_reason = html_mod.escape(str(rule.get("change_reason", "변경 사유 없음")))
        gen_num = rule.get("generation", "?")

        # 실패 건수 표시
        vg = vendor_groups.get(vid, {})
        v_failed = len(vg.get("failed", [])) if isinstance(vg, dict) else 0
        v_success = len(vg.get("success", [])) if isinstance(vg, dict) else 0
        badge_color = "#f87171" if v_failed > 0 else "#34d399"

        fields_html = ""
        field_labels = {
            "pricing_pattern": ("💰", "가격 추출 패턴"),
            "recommended_style": ("🎨", "번역 톤앤매너"),
            "bundle_logic": ("📦", "상품 병합 규칙"),
            "profile_rules": ("📝", "프로필 규칙"),
            "skip_conditions": ("🚫", "스킵 조건"),
            "boundary_signals": ("🔲", "상품 경계 신호"),
        }
        for key, (icon, label) in field_labels.items():
            val = rule.get(key)
            if val:
                if isinstance(val, list):
                    display_val = ", ".join(html_mod.escape(str(v)) for v in val[:8])
                    if len(val) > 8:
                        display_val += f" ...외 {len(val)-8}개"
                else:
                    display_val = html_mod.escape(str(val))
                    if len(display_val) > 200:
                        display_val = display_val[:200] + "..."
                fields_html += f"""<div style="margin-bottom:8px;">
                    <span style="color:#60a5fa;font-weight:600;">{icon} {label}:</span>
                    <span style="color:#cbd5e1;margin-left:6px;font-size:13px;word-break:break-all;">{display_val}</span>
                </div>"""

        vendor_cards += f"""<div style="background:#0f172a;border:1px solid #1e3a5f;border-radius:10px;padding:16px;margin-bottom:12px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                <div style="display:flex;align-items:center;gap:8px;">
                    <span style="font-size:16px;font-weight:700;color:#e2e8f0;">{html_mod.escape(str(vendor_name))}</span>
                    <span style="background:#1e3a5f;color:#60a5fa;padding:2px 8px;border-radius:12px;font-size:11px;">Gen #{gen_num}</span>
                </div>
                <div style="display:flex;gap:6px;">
                    <span style="background:{badge_color}22;color:{badge_color};padding:2px 8px;border-radius:12px;font-size:11px;">오답 {v_failed}건</span>
                    <span style="background:#34d39922;color:#34d399;padding:2px 8px;border-radius:12px;font-size:11px;">성공 {v_success}건</span>
                </div>
            </div>
            <div style="background:#0b1121;border-radius:8px;padding:12px;margin-bottom:8px;">
                <div style="color:#fbbf24;font-size:12px;font-weight:600;margin-bottom:6px;">📌 변경 사유</div>
                <div style="color:#94a3b8;font-size:13px;">{change_reason}</div>
            </div>
            {fields_html}
        </div>"""

    if not vendor_cards:
        vendor_cards = '<div style="text-align:center;color:#64748b;padding:20px;">학습된 업체 규칙이 없습니다.</div>'

    report = f"""<div style="font-family:'Segoe UI',sans-serif;color:#e2e8f0;max-width:100%;">
        <!-- 헤더 -->
        <div style="background:linear-gradient(135deg,#1e3a8a,#7c3aed);border-radius:12px;padding:24px;margin-bottom:20px;text-align:center;">
            <div style="font-size:28px;margin-bottom:4px;">🧬</div>
            <h2 style="margin:0;font-size:22px;color:white;">AI 적응형 학습 결과 리포트</h2>
            <p style="margin:6px 0 0;color:#c4b5fd;font-size:14px;">Generation #{generation} — Adaptive Rule Learning Engine v2.0</p>
        </div>

        <!-- 통계 카드 -->
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px;">
            <div style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:16px;text-align:center;">
                <div style="font-size:24px;font-weight:800;color:#60a5fa;">{total_products}</div>
                <div style="font-size:12px;color:#64748b;margin-top:4px;">전체 분석 데이터</div>
            </div>
            <div style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:16px;text-align:center;">
                <div style="font-size:24px;font-weight:800;color:#34d399;">{success_rate}%</div>
                <div style="font-size:12px;color:#64748b;margin-top:4px;">파싱 성공률</div>
            </div>
            <div style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:16px;text-align:center;">
                <div style="font-size:24px;font-weight:800;color:#f87171;">{total_failed}</div>
                <div style="font-size:12px;color:#64748b;margin-top:4px;">오답 (학습 대상)</div>
            </div>
            <div style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:16px;text-align:center;">
                <div style="font-size:24px;font-weight:800;color:#fbbf24;">{updated_count + new_count}</div>
                <div style="font-size:12px;color:#64748b;margin-top:4px;">업체 규칙 변경</div>
            </div>
        </div>

        {delta_section}

        <!-- 업체별 학습 결과 -->
        <div style="margin-bottom:20px;">
            <h3 style="color:#60a5fa;font-size:16px;margin-bottom:12px;border-bottom:1px solid #1e293b;padding-bottom:8px;">
                📋 업체별 학습된 규칙 상세 ({updated_count}개 갱신 / {new_count}개 신규)
            </h3>
            {vendor_cards}
        </div>

        <!-- 학습 히스토리 -->
        <div style="margin-bottom:20px;">
            <h3 style="color:#60a5fa;font-size:16px;margin-bottom:12px;border-bottom:1px solid #1e293b;padding-bottom:8px;">
                📈 학습 히스토리 (최근 10세대)
            </h3>
            <div style="overflow-x:auto;">
                <table style="width:100%;border-collapse:collapse;background:#0f172a;border:1px solid #1e293b;border-radius:8px;overflow:hidden;">
                    <thead>
                        <tr style="background:#1e293b;">
                            <th style="padding:8px 10px;text-align:center;color:#94a3b8;font-size:12px;">세대</th>
                            <th style="padding:8px 10px;text-align:left;color:#94a3b8;font-size:12px;">학습 시각</th>
                            <th style="padding:8px 10px;text-align:center;color:#94a3b8;font-size:12px;">전체</th>
                            <th style="padding:8px 10px;text-align:center;color:#94a3b8;font-size:12px;">오답</th>
                            <th style="padding:8px 10px;text-align:center;color:#94a3b8;font-size:12px;">성공</th>
                            <th style="padding:8px 10px;text-align:center;color:#94a3b8;font-size:12px;">결과</th>
                        </tr>
                    </thead>
                    <tbody>{history_rows}</tbody>
                </table>
            </div>
        </div>

        <!-- 안내 -->
        <div style="background:#1e293b;border-radius:8px;padding:14px;text-align:center;">
            <span style="color:#94a3b8;font-size:13px;">
                💡 크롤링을 더 많이 실행하고 학습 버튼을 누를수록 AI 규칙이 계속 진화합니다.
                <br>다음 크롤링부터 학습된 규칙이 자동 적용됩니다. (환경설정에서 AI 딥러닝 오버라이드 활성화 필요)
            </span>
        </div>
    </div>"""

    return report

@app.post("/api/apply_dynamic_ai_rules")
def apply_dynamic_ai_rules(req: AnalyzeResultRequest):
    """
    AI 딥러닝 엔진 — 지속적 학습 (Continuous Learning) v2.0

    기존 방식(Overwrite): 매번 백지에서 규칙을 새로 생성 -> 과거 지식 소멸
    새 방식(Merge/Upgrade): 기존 규칙 + 실패 데이터(오답노트) -> 확장된 규칙 생성

    핵심 원리 (일론 머스크 제1원칙):
    1. [State Retention] 기존에 학습된 규칙을 LLM에게 기억으로 제공
    2. [Loss Calculation] 성공 데이터가 아닌, 실패 데이터(오답)를 우선 선별
    3. [Gradient Update] 기존 규칙을 파괴하지 않고, 예외를 수용하도록 확장
    """
    import os, json, datetime

    def _compiled_rules_from_analysis_payload(payload):
        """분석 시작 단계의 compiled_vendor_rules를 크롤러 실행용 오버라이드로 변환한다."""
        compiled = {}
        if not isinstance(payload, dict):
            return compiled
        payload_items = payload.get("items") if isinstance(payload.get("items"), list) else [payload]
        for item in payload_items:
            if not isinstance(item, dict):
                continue
            for rule in item.get("compiled_vendor_rules", []) or []:
                if not isinstance(rule, dict):
                    continue
                vid = rule.get("vendor_id") or "global"
                price_policy = rule.get("price_policy") if isinstance(rule.get("price_policy"), dict) else {}
                boundary_policy = rule.get("boundary_policy") if isinstance(rule.get("boundary_policy"), dict) else {}
                image_policy = rule.get("image_policy") if isinstance(rule.get("image_policy"), dict) else {}
                scoring_policy = rule.get("scoring_policy") if isinstance(rule.get("scoring_policy"), dict) else {}
                posting_type = str(rule.get("posting_type") or "").lower()
                posting_pattern = "분할 포스팅" if posting_type == "split" else "단일 포스팅" if posting_type == "single" else ""
                explicit_patterns = price_policy.get("explicit_patterns") or []
                if isinstance(explicit_patterns, str):
                    explicit_patterns = [explicit_patterns]
                compiled[vid] = {
                    "vendor_id": vid,
                    "name": rule.get("vendor_name", ""),
                    "posting_type": rule.get("posting_type", ""),
                    "posting_pattern": posting_pattern,
                    "identity_keys": rule.get("identity_keys", []),
                    "price_policy": price_policy,
                    "boundary_policy": boundary_policy,
                    "image_policy": image_policy,
                    "scoring_policy": scoring_policy,
                    "price_regex": explicit_patterns[0] if explicit_patterns else "",
                    "boundary_signals": boundary_policy.get("new_product_signals", []),
                    "supplement_patterns": boundary_policy.get("supplement_signals", []),
                    "grouping_rules": " > ".join(boundary_policy.get("same_product_priority", []) or []),
                    "matching_rules": " / ".join(rule.get("identity_keys", []) or []),
                    "avg_images_per_product": image_policy.get("max_images", 20),
                    "change_reason": rule.get("change_reason", "AI 분석자료 compiled_vendor_rules 기반 실행 룰"),
                    "confidence": rule.get("confidence", 0),
                }
        return compiled

    def _merge_rule_dict(base, override):
        out = dict(base or {})
        for key, value in (override or {}).items():
            if isinstance(out.get(key), dict) and isinstance(value, dict):
                nested = dict(out[key])
                nested.update(value)
                out[key] = nested
            elif isinstance(out.get(key), list) and isinstance(value, list):
                out[key] = list(dict.fromkeys(out[key] + value))
            elif value not in (None, "", []):
                out[key] = value
        return out

    api_key = _get_gemini_key(req.api_key)
    if not api_key:
        return {"status": "error", "message": "Gemini API 키가 설정되지 않았습니다."}

    try:
        from google import genai
        client = genai.Client(api_key=api_key)

        base_dir = os.path.dirname(os.path.abspath(__file__))
        override_file = os.path.join(base_dir, "ai_dynamic_overrides.json")
        history_dir = os.path.join(base_dir, "ai_learning_history")
        os.makedirs(history_dir, exist_ok=True)

        # ──────────────────────────────────────────────────────
        # STEP 1: 기존 학습 데이터(State) 로딩 — "기억 유지"
        # ──────────────────────────────────────────────────────
        existing_overrides = {}
        if os.path.exists(override_file):
            with open(override_file, 'r', encoding='utf-8') as f:
                try:
                    existing_overrides = json.load(f)
                except Exception:
                    pass

        # ──────────────────────────────────────────────────────
        # STEP 2: 실패 데이터(오답 노트) 우선 선별 — "Loss Calculation"
        # ──────────────────────────────────────────────────────
        print("[AI 딥러닝] STEP 2-A: 상품 필터링 및 업체별 그룹화 시작...")
        vendor_groups = {}
        for p in req.products:
            vid = p.get("vendor_id", "") or "unknown"
            if vid not in vendor_groups:
                vendor_groups[vid] = {"success": [], "failed": []}

            price_val = str(p.get("price_input", p.get("price", ""))).strip()
            is_price_failed = (not price_val or price_val in ("", "0", "-", "단가미상"))
            is_trans_failed = not p.get("description", p.get("raw_description", "")).strip()
            is_img_failed = len(p.get("image_urls", []) or p.get("image_files", [])) == 0

            # 대량의 데이터를 수백 건씩 돌릴 때 속도 지연을 막기 위해 
            # 1차 루프 단계에서는 무거운 _compact_products_for_ai_analysis를 호출하지 않고 원본 레코드만 들고 있습니다.
            item = {
                "vendor_id": vid,
                "vendor": p.get("vendor_name", ""),
                "goods_id": p.get("goods_id", ""),
                "shop_id": p.get("shop_id", ""),
                "original_text": (p.get("description_original", p.get("original_chinese", "")) or "")[:400],
                "translated_text": (p.get("description", p.get("raw_description", "")) or "")[:400],
                "price": price_val,
                "price_source": p.get("price_source", ""),
                "image_count": len(p.get("image_urls", []) or p.get("image_files", [])),
                "failure_reasons": [],
                "_raw_product": p
            }
            if is_price_failed:
                item["failure_reasons"].append("가격 파싱 실패")
            if is_trans_failed:
                item["failure_reasons"].append("번역 누락")
            if is_img_failed:
                item["failure_reasons"].append("이미지 없음")

            if item["failure_reasons"]:
                vendor_groups[vid]["failed"].append(item)
            else:
                vendor_groups[vid]["success"].append(item)

        print("[AI 딥러닝] STEP 2-B: 업체별 최대 표본 추출 및 후행 가공(Compact) 실행...")
        curated_failed = []
        curated_success = []
        for vid, group in vendor_groups.items():
            total_vendor = len(group["failed"]) + len(group["success"])
            price_fail_rate = len(group["failed"]) / max(total_vendor, 1)
            # 가격 파싱 실패율이 높을수록 더 많은 실패 샘플 수집
            fail_limit = 10 if price_fail_rate >= 0.8 else 7 if price_fail_rate >= 0.5 else 5
            
            # 최종 선별된 실패 표본에 대해서만 _compact_products_for_ai_analysis을 실행하여 가공 정보를 결합
            for item in group["failed"][:fail_limit]:
                p = item.pop("_raw_product")
                try:
                    compact_one = _compact_products_for_ai_analysis([p], limit=1)[0]
                except Exception:
                    compact_one = {}
                item["identity_summary"] = compact_one.get("identity_summary", p.get("identity_summary", {}))
                item["evidence_items"] = compact_one.get("evidence_items", [])
                item["price_ocr_candidates"] = compact_one.get("price_ocr_candidates", p.get("price_ocr_candidates", {}))
                item["source_posts"] = compact_one.get("source_posts", p.get("source_posts", [])[:8] if isinstance(p.get("source_posts", []), list) else [])
                item["decision_trace"] = compact_one.get("decision_trace", p.get("decision_trace", [])[:12] if isinstance(p.get("decision_trace", []), list) else [])
                curated_failed.append(item)

            for item in group["success"][:3]:
                p = item.pop("_raw_product")
                try:
                    compact_one = _compact_products_for_ai_analysis([p], limit=1)[0]
                except Exception:
                    compact_one = {}
                item["identity_summary"] = compact_one.get("identity_summary", p.get("identity_summary", {}))
                item["evidence_items"] = compact_one.get("evidence_items", [])
                item["price_ocr_candidates"] = compact_one.get("price_ocr_candidates", p.get("price_ocr_candidates", {}))
                item["source_posts"] = compact_one.get("source_posts", p.get("source_posts", [])[:8] if isinstance(p.get("source_posts", []), list) else [])
                item["decision_trace"] = compact_one.get("decision_trace", p.get("decision_trace", [])[:12] if isinstance(p.get("decision_trace", []), list) else [])
                curated_success.append(item)
        print(f"[AI 딥러닝] STEP 2-C: 최종 선별 완료 (오답 표본: {len(curated_failed)}건, 성공 표본: {len(curated_success)}건)")

        total_products = len(req.products)
        total_failed = sum(len(g["failed"]) for g in vendor_groups.values())
        total_success = total_products - total_failed

        # ──────────────────────────────────────────────────────
        # STEP 3: 프롬프트 구성 — "Merge/Upgrade"
        # ──────────────────────────────────────────────────────
        existing_rules_str = json.dumps(existing_overrides, ensure_ascii=False, indent=2) if existing_overrides else "없음 (최초 학습)"
        failed_data_str = json.dumps(curated_failed, ensure_ascii=False) if curated_failed else "없음"
        success_data_str = json.dumps(curated_success, ensure_ascii=False) if curated_success else "없음"
        analysis_payload_str = (
            json.dumps(req.analysis_payload, ensure_ascii=False, indent=2)
            if req.analysis_payload else
            "없음 — 분석 시작 단계에서 생성된 AI 분석자료가 전달되지 않았습니다."
        )
        telemetry_events = []
        try:
            from backend.database import get_db
            telemetry_events = get_db().get_recent_crawl_events(
                platform="weishang",
                event_types=[
                    "candidate_rejected",
                    "candidate_soft_pass",
                    "price_parse_failed",
                    "download_empty",
                    "product_download_empty",
                    "product_discarded",
                    "duplicate_skipped",
                    "candidate_retry",
                    "candidate_retry_exhausted",
                    "boundary_decision",
                    "candidate_snapshot",
                    "api_packet_hit",
                ],
                limit=300,
            )
        except Exception:
            telemetry_events = []

        optimized_telemetry = []
        for ev in telemetry_events[:120]:
            optimized_telemetry.append({
                "vendor_id": ev.get("vendor_id", ""),
                "vendor": ev.get("vendor_name", ""),
                "event_type": ev.get("event_type", ""),
                "reason": ev.get("reason", ""),
                "raw_text": (ev.get("raw_text") or "")[:500],
                "metadata": ev.get("metadata", {}),
            })
        telemetry_data_str = json.dumps(optimized_telemetry, ensure_ascii=False) if optimized_telemetry else "없음"
        try:
            from backend.weishang_diagnostics import simulate_decision_trace, summarize_identity_stats
            rule_simulation = {
                "trace_simulation": simulate_decision_trace(req.products or []),
                "identity_stats": summarize_identity_stats(telemetry_events),
            }
            rule_simulation_str = json.dumps(rule_simulation, ensure_ascii=False, indent=2)
        except Exception:
            rule_simulation_str = "없음"

        generation = len(existing_overrides.get("_meta", {}).get("history", [])) + 1 if existing_overrides.get("_meta") else 1

        prompt = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AI 딥러닝 엔진 — 지속적 학습 (Generation #{generation})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

당신은 데이터 크롤링 시스템의 딥러닝 룰 엔진 관리자이며,
기존에 학습된 규칙을 파괴하지 않고 발전시키는 것이 최우선 임무입니다.

[핵심 원칙 (절대 위반 금지)]
1. 기존 규칙이 잘 작동하는 부분은 반드시 그대로 유지하세요.
2. 오답 데이터에서 발견된 새로운 패턴만 추가/확장하세요.
3. 기존 정규식을 삭제하지 말고, 새로운 대안 패턴을 추가(OR 연결)하세요.
4. 모든 변경에는 "왜 바꿨는지" change_reason을 반드시 기록하세요.
5. 상품별 source_posts/decision_trace가 있으면, 이것을 실제 크롤러 판단 근거로 보고 같은 상품 묶기/분리/가격/이미지 순서 규칙을 컴파일하세요.
6. evidence_items/source_posts.evidence의 identity confidence, price_candidates, image_candidates는 실제 크롤러 판단 증거입니다. 신뢰도 낮은 식별자는 강한 병합 규칙으로 만들지 말고, 먼저 API/goods_id/image fingerprint 보강 규칙으로 컴파일하세요.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[현재 학습 상태 (기존 규칙 — 이것이 당신의 '기억'입니다)]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{existing_rules_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[이번 크롤링 통계]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 전체 수집: {total_products}건
- 성공(파싱 완료): {total_success}건
- 실패(오답): {total_failed}건 (실패율: {round(total_failed/max(total_products,1)*100, 1)}%)
- 관련 업체 수: {len(vendor_groups)}개

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[오답 데이터 — 기존 규칙이 처리하지 못한 예외 케이스]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{failed_data_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[성공 데이터 — 기존 규칙이 잘 작동한 사례 (참고용)]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{success_data_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[AI 분석 시작 단계에서 생성된 딥러닝 적용용 분석자료 — 최우선 참고]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{analysis_payload_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[크롤링 telemetry — AI 판단 전 필터/가격/다운로드 단계에서 발생한 실패와 완화 사례]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{telemetry_data_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[규칙 시뮬레이터 — source_posts/decision_trace 기반 사전 영향도]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{rule_simulation_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[출력 요구사항 — 반드시 준수]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
오직 JSON 객체만 출력하세요. 다른 설명, 마크다운, 주석은 일절 포함하지 마세요.
최상위 구조는 vendor_id를 키로 하는 객체이며, 각 값은 아래 스키마를 따릅니다:

{{
  "vendor_id_here": {{
    "vendor_id": "업체의 고유 ID",
    "pricing_pattern": "가격 추출 정규식 또는 패턴 설명 (기존 + 새로운 패턴을 OR로 병합)",
    "price_regex": "Python 정규식. 가능하면 실제 단가 숫자만 캡처그룹 1번에 담기. 예: P\\s*(\\d+) 또는 \\d{{4,}}(\\d{{3}})$",
    "price_decoder": "필요한 경우 sandwich 등 가격 디코딩 방식. 없으면 빈 문자열",
    "price_offset": 0,
    "recommended_style": "번역 톤앤매너 및 문체 지침",
    "bundle_logic": "같은 상품의 여러 포스팅을 묶기 위한 조건",
    "profile_rules": "상품명 생성, 특징 처리에 대한 종합 규칙",
    "skip_conditions": ["스킵해야 하는 텍스트 패턴 배열"],
    "boundary_signals": ["상품 경계를 나타내는 키워드 배열"],
    "supplement_patterns": ["보충컷/디테일/사이즈표를 나타내는 키워드 배열"],
    "posting_type": "single|split|mixed",
    "identity_keys": ["货号", "款号", "搜索码", "商品编号"],
    "price_policy": {{
      "explicit_patterns": ["P\\s*(\\d+)", "¥\\s*(\\d+)"],
      "guard_keywords": ["货号", "款号", "规格", "码数", "尺码", "搜索码"],
      "missing_price_behavior": "reject|allow_but_mark_missing|use_vendor_default",
      "long_number_price_rule": "none|last_3_digits|identifier_tail_3",
      "identifier_tail_price": false,
      "identifier_tail_digits": 3
    }},
    "boundary_policy": {{
      "new_product_signals": ["新款", "上新", "主图"],
      "supplement_signals": ["细节", "实拍", "尺码表", "尺寸表", "商品属性"],
      "same_product_priority": ["same_identity_key", "same_title_terms", "vision_similarity"],
      "split_when_multiple_identity_keys": true
    }},
    "image_policy": {{
      "max_images": 20,
      "order": ["color_front_back", "representative_detail", "size_chart_last"]
    }},
    "scoring_policy": {{
      "candidate_keep_threshold": 4,
      "duplicate_keep_threshold": 4,
      "new_product_threshold": 5,
      "supplement_threshold": -4,
      "min_images_override": 0,
      "weights": {{
        "candidate_identity_code": 4,
        "candidate_price_signal": 3,
        "candidate_image_count_4_plus": 3,
        "candidate_product_context": 2,
        "boundary_code_signal": 3,
        "boundary_price_signal": 2,
        "boundary_new_product_signal": 2,
        "boundary_supplement_signal": -3,
        "boundary_role_detail": -2,
        "boundary_role_spec": -2,
        "boundary_role_size": -2
      }}
    }},
    "avg_images_per_product": 0,
    "has_price": true,
    "change_reason": "이번 학습에서 무엇이 왜 변경되었는지 한 줄 설명",
    "generation": {generation}
  }}
}}

기존 규칙에 이미 있는 업체는 기존 값을 기반으로 확장하고,
새로운 업체는 오답 데이터를 기반으로 신규 생성하세요.
분석자료의 compiled_vendor_rules가 있으면 이를 최우선으로 실행 가능한 룰에 반영하세요.
레거시 필드(price_regex, bundle_logic 등)와 실행용 필드(price_policy, boundary_policy, image_policy)는 동시에 보존하세요.
_meta 키는 건드리지 마세요.

[Gen#4 집중 분석 지시]
1. 가격 파싱 0% 업체는 반드시 원문 텍스트에서 가격을 나타내는 단서·패턴을 인간 수준으로 세밀히 찾아 price_regex에 반영하세요.
2. guard_keywords에는 크기/무게/신체치수 단위(克重, 重量, 身高, 体重, cm, kg)를 포함하여 가격 오인을 방지하세요.
3. skip_conditions에는 비상품 포스팅 키워드(发货实拍, 打包实拍, 鉴定, 客户反馈, 招代理, 通知, 放假 등)를 추가하세요.
4. 단, 실제 상품명에 포함될 수 있는 일반적 단어는 skip_conditions에 넣지 마세요.
"""

        # ──────────────────────────────────────────────────────
        # STEP 4: LLM 호출 — 규칙 생성 (JSON 응답 강제 옵션 추가 + 타임아웃 60초 지정)
        # ──────────────────────────────────────────────────────
        print(f"[AI 딥러닝] STEP 4-A: Gemini API 호출 시작... (프롬프트 크기: {len(prompt)}자)")
        try:
            try:
                res = client.models.generate_content(
                    model='gemini-2.5-pro',
                    contents=prompt,
                    config={
                        "temperature": 0.15,
                        "response_mime_type": "application/json",
                        "http_options": {"timeout": 60.0}
                    }
                )
            except Exception as timeout_config_err:
                print(f"[AI 딥러닝] ⚠️ 타임아웃 옵션 미지원 혹은 기타 오류 발생 ({str(timeout_config_err)}), 기본 설정으로 재시도합니다.")
                res = client.models.generate_content(
                    model='gemini-2.5-pro',
                    contents=prompt,
                    config={
                        "temperature": 0.15,
                        "response_mime_type": "application/json"
                    }
                )
            print("[AI 딥러닝] STEP 4-B: Gemini API 응답 수신 완료.")
        except Exception as api_err:
            print(f"[AI 딥러닝] ❌ Gemini API 호출 에러 발생: {str(api_err)}")
            raise api_err

        json_text = res.text.strip()
        if json_text.startswith("```json"):
            json_text = json_text[7:]
        if json_text.startswith("```"):
            json_text = json_text[3:]
        if json_text.endswith("```"):
            json_text = json_text[:-3]
        json_text = json_text.strip()

        # JSON 파싱 및 완화 처리 로직 보강
        import re
        try:
            new_rules = json.loads(json_text)
        except json.JSONDecodeError as initial_err:
            try:
                # 완화 기법 1: 객체나 배열의 마지막 쉼표(Trailing Comma) 제거 (예: ,} -> } or ,] -> ])
                cleaned_text = re.sub(r',\s*([\}\]])', r'\1', json_text)
                # 완화 기법 2: 간혹 제어 문자나 잘못된 역슬래시 이스케이프 완화
                cleaned_text = re.sub(r'\\([^\/\"\\bfnrtu])', r'\1', cleaned_text)
                new_rules = json.loads(cleaned_text)
            except Exception:
                # 에러 진단 디버그 출력
                import sys
                print("[AI JSON 파싱 실패 로그]", file=sys.stderr)
                print(f"오류: {str(initial_err)}", file=sys.stderr)
                print(f"AI 원본 응답 일부: {json_text[:2000]}", file=sys.stderr)
                raise initial_err

        if isinstance(new_rules, list):
            converted = {}
            for rule in new_rules:
                vid = rule.get("vendor_id")
                if vid:
                    converted[vid] = rule
            new_rules = converted

        compiled_rules = _compiled_rules_from_analysis_payload(req.analysis_payload)
        for vid, compiled_rule in compiled_rules.items():
            new_rules[vid] = _merge_rule_dict(new_rules.get(vid, {}), compiled_rule)

        # ──────────────────────────────────────────────────────
        # STEP 5: 기존 규칙과 병합 (Merge, not Overwrite)
        # ──────────────────────────────────────────────────────
        merged_overrides = dict(existing_overrides)

        if "_meta" not in merged_overrides:
            merged_overrides["_meta"] = {"history": [], "created_at": datetime.datetime.now().isoformat()}

        updated_count = 0
        new_count = 0
        for vid, rule in new_rules.items():
            if vid == "_meta":
                continue
            if vid in merged_overrides:
                merged_overrides[vid] = _merge_rule_dict(merged_overrides[vid], rule)
                merged_overrides[vid]["vendor_id"] = rule.get("vendor_id", vid)
                merged_overrides[vid]["generation"] = generation
                updated_count += 1
            else:
                merged_overrides[vid] = rule
                new_count += 1

        # ──────────────────────────────────────────────────────
        # STEP 5-B: 세대간 비교를 위한 상세 메트릭 계산
        # ──────────────────────────────────────────────────────
        # 업체별 세부 지표 계산
        vendor_metrics = {}
        price_success_total = 0
        trans_success_total = 0
        img_success_total = 0
        for vid, group in vendor_groups.items():
            v_total = len(group["success"]) + len(group["failed"])
            v_price_ok = sum(1 for p in group["success"] + group["failed"]
                            if "가격 파싱 실패" not in p.get("failure_reasons", []))
            v_trans_ok = sum(1 for p in group["success"] + group["failed"]
                            if "번역 누락" not in p.get("failure_reasons", []))
            v_img_ok = sum(1 for p in group["success"] + group["failed"]
                          if "이미지 없음" not in p.get("failure_reasons", []))
            price_success_total += v_price_ok
            trans_success_total += v_trans_ok
            img_success_total += v_img_ok
            vendor_metrics[vid] = {
                "total": v_total,
                "price_rate": round(v_price_ok / max(v_total, 1) * 100, 1),
                "trans_rate": round(v_trans_ok / max(v_total, 1) * 100, 1),
                "img_rate": round(v_img_ok / max(v_total, 1) * 100, 1),
            }

        overall_price_rate = round(price_success_total / max(total_products, 1) * 100, 1)
        overall_trans_rate = round(trans_success_total / max(total_products, 1) * 100, 1)
        overall_img_rate = round(img_success_total / max(total_products, 1) * 100, 1)
        overall_success_rate = round(total_success / max(total_products, 1) * 100, 1)

        history_entry = {
            "generation": generation,
            "timestamp": datetime.datetime.now().isoformat(),
            "total_data": total_products,
            "failed_data": total_failed,
            "success_data": total_success,
            "updated_vendors": updated_count,
            "new_vendors": new_count,
            "metrics": {
                "overall_success_rate": overall_success_rate,
                "price_parse_rate": overall_price_rate,
                "translation_rate": overall_trans_rate,
                "image_rate": overall_img_rate,
                "vendor_count": len(vendor_groups),
                "per_vendor": vendor_metrics
            }
        }
        merged_overrides["_meta"]["history"].append(history_entry)
        merged_overrides["_meta"]["last_updated"] = datetime.datetime.now().isoformat()
        merged_overrides["_meta"]["total_generations"] = generation

        # ──────────────────────────────────────────────────────
        # STEP 6: 저장 + 백업
        # ──────────────────────────────────────────────────────
        if os.path.exists(override_file):
            backup_name = f"ai_overrides_gen{generation - 1}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            backup_path = os.path.join(history_dir, backup_name)
            with open(override_file, 'r', encoding='utf-8') as f_src:
                with open(backup_path, 'w', encoding='utf-8') as f_dst:
                    f_dst.write(f_src.read())

        with open(override_file, 'w', encoding='utf-8') as f:
            json.dump(merged_overrides, f, ensure_ascii=False, indent=2)
        try:
            current_settings = get_system_settings()
            current_settings["use_dynamic_ai_rules"] = True
            save_system_settings(current_settings)
        except Exception:
            pass

        summary = (
            f"🧬 딥러닝 Generation #{generation} 학습 완료!\n"
            f"📊 분석 데이터: {total_products}건 (성공 {total_success} / 오답 {total_failed})\n"
            f"🔄 업데이트된 업체: {updated_count}개 | 신규 추가: {new_count}개\n"
            f"💾 이전 세대 백업 완료"
        )

        # ──────────────────────────────────────────────────────
        # STEP 7: 학습 결과 HTML 리포트 생성
        # ──────────────────────────────────────────────────────
        report_html = _build_learning_report_html(
            generation=generation,
            total_products=total_products,
            total_success=total_success,
            total_failed=total_failed,
            updated_count=updated_count,
            new_count=new_count,
            merged_overrides=merged_overrides,
            vendor_groups=vendor_groups
        )

        # AI 규칙 컴파일 성공 기여 포인트 500 P 적립
        try:
            from backend.database import get_db
            get_db().add_points(500, f"AI 딥러닝 Generation #{generation} 성공 기여")
        except Exception as pe:
            print(f"[Reward System] Error adding points for deep learning generation: {pe}")

        return {"status": "success", "message": summary, "report_html": report_html}

    except json.JSONDecodeError as e:
        return {"status": "error", "message": f"AI 응답을 JSON으로 파싱하는 데 실패했습니다. (오류: {str(e)}) 다시 시도해주세요."}
    except Exception as e:
        return {"status": "error", "message": f"딥러닝 학습 중 오류 발생: {str(e)}"}

class StartPostRequest(BaseModel):
    platforms: list = ["네이버 밴드"]  # ["네이버 밴드", "카카오스토리"] 등 다중 선택
    category: str
    delayMin: int
    delayMax: int
    dry_run: bool = False
    skip_duplicate_posts: bool = True
    selected_indices: List[int] = []

@app.post("/api/start_post")
def start_post(req: StartPostRequest):
    global _last_start_post_at
    engine = get_engine()
    now = time.time()
    with _start_post_lock:
        if now - _last_start_post_at < 2.0:
            engine.add_log("⚠️ 포스팅 시작 요청이 너무 빠르게 반복되어 중복 요청을 무시합니다.", "WARNING", False)
            return {"status": "ignored", "message": "posting start request duplicated"}
        _last_start_post_at = now

    if engine.is_posting_running():
        engine.add_log("⚠️ 포스팅 작업이 이미 실행 중입니다. 새 시작 요청을 무시합니다.", "WARNING", False)
        return {"status": "busy", "message": "posting already running"}

    settings = {
        "platforms": req.platforms,
        "category": req.category,
        "delayMin": req.delayMin,
        "delayMax": req.delayMax,
        "dry_run": req.dry_run,
        "skip_duplicate_posts": req.skip_duplicate_posts,
        "selected_indices": req.selected_indices or [],
    }
    engine.last_post_settings = settings
    from backend.queue_manager import get_queue_manager
    qm = get_queue_manager()
    if not qm.add_unique_job("POST", settings):
        engine.add_log("⚠️ 이미 대기/실행 중인 포스팅 큐가 있어 새 요청을 무시합니다.", "WARNING", False)
        return {"status": "busy", "message": "posting job already queued"}
    engine.add_log("✅ 포스팅 작업이 큐에 등록되었습니다.", "INFO", False)
    return {"status": "queued"}

@app.get("/api/user/points")
def get_user_points_api():
    from backend.database import get_db
    try:
        points = get_db().get_user_points()
        return {"status": "success", "points": points}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/user/points/history")
def get_user_points_history_api():
    from backend.database import get_db
    try:
        history = get_db().get_point_history(limit=50)
        return {"status": "success", "history": history}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/queue/status")
def get_queue_status():
    from backend.queue_manager import get_queue_manager
    return get_queue_manager().get_queue_status()

@app.get("/api/queue/jobs")
def get_queue_jobs():
    from backend.database import get_db
    db = get_db()
    with db.lock:
        conn = db.connect()
        c = conn.cursor()
        c.execute("SELECT id, task_type, status, error_msg, created_at, updated_at FROM job_queue ORDER BY created_at DESC LIMIT 50")
        rows = c.fetchall()
        conn.close()

    jobs = []
    for r in rows:
        raw_status = r[2]
        status_val = raw_status
        if raw_status == "SUCCESS":
            status_val = "success"
        elif raw_status == "DRY_RUN":
            status_val = "dry_run"
        elif raw_status == "FAIL":
            status_val = "fail"
            
        jobs.append({
            "id": r[0],
            "task_type": r[1],
            "status": status_val,
            "error_msg": r[3],
            "created_at": r[4],
            "updated_at": r[5]
        })
    return {"jobs": jobs}

@app.post("/api/queue/clear")
def clear_queue():
    from backend.database import get_db
    db = get_db()
    with db.lock:
        conn = db.connect()
        c = conn.cursor()
        c.execute("DELETE FROM job_queue")
        conn.commit()
        conn.close()
    return {"status": "cleared"}

@app.post("/api/stop")
def stop_crawling():
    engine = get_engine()
    engine.stop_all()
    return {"status": "stopped"}

@app.get("/api/weishang_vendors")
def get_weishang_vendors():
    import json, os
    vendor_file = os.path.join(_BASE_DIR, "weishang_vendors.json")
    if os.path.exists(vendor_file):
        try:
            with open(vendor_file, "r", encoding="utf-8") as f:
                vendors = json.load(f)
                try:
                    from pricing_logic import clean_vendor_name
                except ImportError:
                    from backend.pricing_logic import clean_vendor_name
                for v in vendors:
                    if "name" in v:
                        v["name"] = clean_vendor_name(v["name"])
                return {"status": "success", "vendors": vendors}
        except Exception as e:
            return {"status": "error", "message": f"파일 읽기 오류: {e}"}
    return {"status": "success", "vendors": []}

@app.post("/api/weishang_vendors")
async def save_weishang_vendors(request: Request):
    import json, os
    try:
        data = await request.json()
        vendors = data.get("vendors", [])
        try:
            from pricing_logic import clean_vendor_name
        except ImportError:
            from backend.pricing_logic import clean_vendor_name
        for v in vendors:
            if "name" in v:
                v["name"] = clean_vendor_name(v["name"])
        vendor_file = os.path.join(_BASE_DIR, "weishang_vendors.json")
        with open(vendor_file, "w", encoding="utf-8") as f:
            json.dump(vendors, f, ensure_ascii=False, indent=2)
        return {"status": "success", "message": "업체 목록이 저장되었습니다."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/weishang_vendors/sync")
def sync_weishang_vendors():
    engine = get_engine()
    # Execute synchronously since it only takes ~15 seconds and we return the result directly.
    try:
        vendors = engine.sync_vendors()
        return {"status": "success", "vendors": vendors}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/exchange/naver")
def get_naver_exchange_rate():
    try:
        import urllib.request
        import json
        url = "https://m.search.naver.com/p/csearch/content/qapirender.nhn?key=calculator&pkid=141&q=%ED%99%98%EC%9C%A8&where=m&u1=keb&u6=standardUnit&u7=0&u3=CNY&u4=KRW&u8=down&u2=1"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=5).read().decode('utf-8')
        data = json.loads(resp)
        val_str = str(data['country'][1]['value']).replace(',', '')
        val = float(val_str)
        return {"status": "success", "rate": val}
    except Exception as e:
        return {"status": "error", "message": "네이버 환율 API 통신 오류: " + str(e)}


class SchedulerTaskSchema(BaseModel):
    name: str
    interval_type: str  # 'daily', 'interval'
    interval_value: str
    source_platform: Optional[str] = "웨이상(Szwego)"
    target_platforms: list
    crawling_count: Optional[int] = 10
    delay_min: Optional[int] = 15
    delay_max: Optional[int] = 45

@app.get("/api/scheduler")
def api_get_scheduler():
    from backend.database import get_db
    try:
        tasks = get_db().get_all_scheduler_tasks()
        return {"status": "success", "tasks": tasks}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/scheduler")
def api_create_scheduler(req: SchedulerTaskSchema):
    from backend.database import get_db
    try:
        db = get_db()
        task_id = db.add_scheduler_task(
            name=req.name,
            interval_type=req.interval_type,
            interval_value=req.interval_value,
            source_platform=req.source_platform,
            target_platforms=req.target_platforms,
            crawling_count=req.crawling_count,
            delay_min=req.delay_min if req.delay_min is not None else 15,
            delay_max=req.delay_max if req.delay_max is not None else 45
        )
        from backend.scheduler_manager import sync_active_scheduler_tasks
        sync_active_scheduler_tasks()
        return {"status": "success", "task_id": task_id}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.delete("/api/scheduler/{task_id}")
def api_delete_scheduler(task_id: int):
    from backend.database import get_db
    try:
        db = get_db()
        db.delete_scheduler_task(task_id)
        from backend.scheduler_manager import sync_active_scheduler_tasks
        sync_active_scheduler_tasks()
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/scheduler/{task_id}/toggle")
def api_toggle_scheduler(task_id: int):
    from backend.database import get_db
    try:
        db = get_db()
        new_state = db.toggle_scheduler_task(task_id)
        from backend.scheduler_manager import sync_active_scheduler_tasks
        sync_active_scheduler_tasks()
        return {"status": "success", "is_active": new_state}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/scheduler/{task_id}/trigger")
def api_trigger_scheduler(task_id: int):
    try:
        from backend.scheduler_manager import run_scheduled_job
        import threading
        # 백그라운드로 즉시 1회 가동
        threading.Thread(target=run_scheduled_job, args=[task_id], daemon=True).start()
        return {"status": "success", "message": "스케줄 작업이 백그라운드에서 강제 작동되었습니다."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/cleanup/chrome")
def api_cleanup_chrome():
    try:
        import subprocess
        killed = []
        for proc in ["chrome.exe", "chromedriver.exe", "undetected_chromedriver.exe"]:
            res = subprocess.run(f"taskkill /F /IM {proc}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0:
                killed.append(proc)
        return {"status": "success", "message": f"정리된 프로세스: {', '.join(killed) if killed else '없음'}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/cleanup/locks")
def api_cleanup_locks():
    try:
        import glob
        import os
        from backend.database import _PROJECT_ROOT
        cleaned = []
        profile_dirs = glob.glob(os.path.join(_PROJECT_ROOT, "*profile*"))
        for p_dir in profile_dirs:
            if not os.path.isdir(p_dir):
                continue
            for lf in ["SingletonLock", "lock", "Default/SingletonLock", "Default/lock"]:
                path = os.path.join(p_dir, lf)
                if os.path.exists(path) or os.path.islink(path):
                    try:
                        os.remove(path)
                        cleaned.append(f"{os.path.basename(p_dir)}/{lf}")
                    except Exception:
                        pass
        return {"status": "success", "message": f"제거된 락 파일: {', '.join(cleaned) if cleaned else '없음'}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/system/toggle_topmost")
async def toggle_topmost(request: Request):
    """
    ctypes로 FindWindowW 한 메인창과 보조창의 항상 위 설정을 토글한다.
    """
    try:
        import ctypes
        from ctypes import wintypes
        data = await request.json()
        enable = data.get("enable", True)

        user32 = ctypes.windll.user32
        HWND_TOPMOST = -1
        HWND_NOTOPMOST = -2
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001

        insert_after = HWND_TOPMOST if enable else HWND_NOTOPMOST

        hwnd_main = user32.FindWindowW(None, "Winwin 크롤러 3.3 (메인 제어판)")
        hwnd_log = user32.FindWindowW(None, "실시간 콘솔 로그 (보조창)")

        flags = SWP_NOMOVE | SWP_NOSIZE

        if hwnd_main:
            user32.SetWindowPos(hwnd_main, insert_after, 0, 0, 0, 0, flags)
        if hwnd_log:
            user32.SetWindowPos(hwnd_log, insert_after, 0, 0, 0, 0, flags)

        return {"status": "success", "topmost": enable}
    except Exception as e:
        return {"status": "error", "message": str(e)}

class ProfileVendorRequest(BaseModel):
    vendor_id: str
    vendor_url: str
    api_key: str = ""

def _get_vendor_profile_crawler(engine):
    """업체 AI 분석은 웨이상 크롤러 전용 메서드를 사용한다."""
    crawler = getattr(engine, "_source_crawler", None)
    if crawler and hasattr(crawler, "profile_vendor_style"):
        return crawler

    crawler = getattr(engine, "_vendor_profile_crawler", None)
    if crawler and hasattr(crawler, "profile_vendor_style"):
        return crawler

    try:
        from platforms.weishang.crawler import WeishangCrawler
    except ImportError:
        from backend.platforms.weishang.crawler import WeishangCrawler
    crawler = WeishangCrawler(log_func=engine.add_log)
    engine._vendor_profile_crawler = crawler
    return crawler

_VENDOR_AI_PROFILE_FIELDS = [
    "category",
    "posting_pattern",
    "analysis_reason",
    "skip_conditions",
    "bundle_logic",
    "recommended_style",
    "pricing_pattern",
    "price_regex",
    "price_decoder",
    "price_offset",
    "post_structure",
    "grouping_rules",
    "matching_rules",
    "profile_rules",
    "boundary_signals",
    "supplement_patterns",
    "avg_images_per_product",
    "has_price",
]

def _apply_vendor_profile_result(vendor: dict, result: dict):
    for field in _VENDOR_AI_PROFILE_FIELDS:
        if field in result:
            vendor[field] = result.get(field)

@app.post("/api/profile_vendor")
def profile_vendor(req: ProfileVendorRequest, background_tasks: BackgroundTasks):
    engine = get_engine()
    profiler = _get_vendor_profile_crawler(engine)
    api_key = _get_gemini_key(req.api_key)
    if not api_key:
        return {"status": "error", "message": "Gemini API 키가 설정되지 않았습니다."}

    def _run_profiling():
        result = profiler.profile_vendor_style(req.vendor_url, api_key)
        if not result or not isinstance(result, dict) or not result.get("category"):
            engine.add_log(f"⚠️ {req.vendor_id} 프로파일링 결과가 유효하지 않습니다.", "WARNING", False)
            return

        # update weishang_vendors.json
        import json, os
        vendor_file = os.path.join(_BASE_DIR, "weishang_vendors.json")
        try:
            with open(vendor_file, "r", encoding="utf-8") as f:
                vendors = json.load(f)

            updated = False
            for v in vendors:
                if v.get("id") == req.vendor_id:
                    _apply_vendor_profile_result(v, result)

                    # 폴더(그룹) 자동 이동 로직 (기존 폴더가 카테고리명과 다르면 업데이트)
                    cat = result.get("category", "")
                    valid_folders = ["남성의류", "여성의류", "가방/지갑", "신발", "시계/잡화", "공장모음", "원도매모음", "기타"]
                    if cat in valid_folders:
                        v["folder"] = cat
                        engine.add_log(f"📂 {req.vendor_id} 업체를 '{cat}' 폴더로 자동 이동했습니다.", "INFO", False)

                    updated = True
                    break

            if updated:
                with open(vendor_file, "w", encoding="utf-8") as f:
                    json.dump(vendors, f, ensure_ascii=False, indent=2)
                engine.add_log(f"✅ {req.vendor_id} 업체의 포스팅 규칙 저장 완료: DB 갱신", "INFO", False)
                return {"status": "success", "message": f"{req.vendor_id} 분석 및 저장 완료"}
        except Exception as e:
            engine.add_log(f"❌ 프로파일 저장 실패: {e}", "ERROR", False)
            return {"status": "error", "message": str(e)}

    return _run_profiling()

class ProfileVendorsBulkRequest(BaseModel):
    vendor_ids: list[str]
    api_key: str = ""

@app.post("/api/profile_vendors_bulk")
def profile_vendors_bulk(req: ProfileVendorsBulkRequest, background_tasks: BackgroundTasks):
    engine = get_engine()
    profiler = _get_vendor_profile_crawler(engine)
    api_key = _get_gemini_key(req.api_key)
    if not api_key:
        return {"status": "error", "message": "Gemini API 키가 설정되지 않았습니다."}

    def _run_bulk_profiling():
        import json, os, time
        vendor_file = os.path.join(_BASE_DIR, "weishang_vendors.json")
        try:
            with open(vendor_file, "r", encoding="utf-8") as f:
                vendors = json.load(f)
        except Exception:
            vendors = []

        engine.add_log(f"🚀 총 {len(req.vendor_ids)}개 업체의 일괄 AI 딥러닝 분석(순차 진행)을 시작합니다...", "INFO", False)

        for vid in req.vendor_ids:
            v_url = next((v["url"] for v in vendors if v["id"] == vid), None)
            if not v_url:
                continue

            engine.add_log(f"⏳ [일괄 딥러닝] {vid} 업체 분석 시작...", "INFO", False)
            try:
                result = profiler.profile_vendor_style(v_url, api_key)
                if result and isinstance(result, dict) and result.get("category"):
                    updated = False
                    # 파일에서 최신 상태를 다시 읽어옵니다 (중간에 다른 프로세스가 수정했을 수 있음)
                    try:
                        with open(vendor_file, "r", encoding="utf-8") as f:
                            vendors_current = json.load(f)
                    except:
                        vendors_current = vendors

                    for v in vendors_current:
                        if v.get("id") == vid:
                            _apply_vendor_profile_result(v, result)

                            cat = result.get("category", "")
                            valid_folders = ["남성의류", "여성의류", "가방/지갑", "신발", "시계/잡화", "공장모음", "원도매모음", "기타"]
                            if cat in valid_folders:
                                v["folder"] = cat
                                engine.add_log(f"📂 {vid} 업체를 '{cat}' 폴더로 자동 이동했습니다.", "INFO", False)

                            updated = True
                            break
                    if updated:
                        with open(vendor_file, "w", encoding="utf-8") as f:
                            json.dump(vendors_current, f, ensure_ascii=False, indent=2)
                        vendors = vendors_current # 로컬 변수도 갱신
                        engine.add_log(f"✅ {vid} 업체의 포스팅 규칙 저장 완료: DB 갱신", "INFO", False)
                else:
                    engine.add_log(f"⚠️ {vid} 프로파일링 결과가 없습니다.", "WARNING", False)
            except Exception as e:
                engine.add_log(f"❌ {vid} 프로파일 중 에러 발생: {e}", "ERROR", False)

            engine.add_log(f"⏱️ 과부하 방지를 위해 5초 대기합니다...", "INFO", False)
            time.sleep(5)

        engine.add_log(f"🎉 총 {len(req.vendor_ids)}개 업체의 일괄 AI 딥러닝 분석이 모두 완료되었습니다!", "SUCCESS", False)

    background_tasks.add_task(_run_bulk_profiling)
    return {"status": "started", "message": f"총 {len(req.vendor_ids)}개 업체의 일괄 분석을 백그라운드 대기열에 추가했습니다. 콘솔 창의 진행 상황을 확인하세요."}

class UpdateVendorAIRulesRequest(BaseModel):
    vendor_id: str
    skip_conditions: list[str]
    bundle_logic: str = ""
    recommended_style: str = ""
    pricing_pattern: str = ""
    price_regex: str = ""
    price_decoder: str = ""
    price_offset: int = 0
    category: str = ""
    posting_pattern: str = ""
    analysis_reason: str = ""
    post_structure: str = ""
    grouping_rules: str = ""
    matching_rules: str = ""
    profile_rules: str = ""
    vendor_code: str = ""
    price_margin: str = ""

@app.post("/api/update_vendor_ai_rules")
def update_vendor_ai_rules(req: UpdateVendorAIRulesRequest):
    """지정된 벤더의 AI 룰 텍스트 및 조건을 수동으로 업데이트한다."""
    engine = get_engine()

    import json, os
    vendor_file = os.path.join(_BASE_DIR, "weishang_vendors.json")
    try:
        with open(vendor_file, "r", encoding="utf-8") as f:
            vendors = json.load(f)

        updated = False
        for v in vendors:
            if v.get("id") == req.vendor_id:
                v["skip_conditions"] = req.skip_conditions
                v["bundle_logic"] = req.bundle_logic
                v["recommended_style"] = req.recommended_style
                v["pricing_pattern"] = req.pricing_pattern
                v["price_regex"] = req.price_regex
                v["price_decoder"] = req.price_decoder
                import re
                try:
                    cleaned_offset = re.sub(r'[^\d\-]', '', str(req.price_margin).strip())
                    v["price_offset"] = int(cleaned_offset) if cleaned_offset else 0
                except:
                    v["price_offset"] = 0
                v["category"] = req.category
                v["posting_pattern"] = req.posting_pattern
                v["analysis_reason"] = req.analysis_reason
                v["profile_rules"] = req.profile_rules
                v["post_structure"] = req.post_structure
                v["grouping_rules"] = req.grouping_rules
                v["matching_rules"] = req.matching_rules
                v["vendor_code"] = req.vendor_code
                v["price_margin"] = req.price_margin
                updated = True
                break

        if updated:
            with open(vendor_file, "w", encoding="utf-8") as f:
                json.dump(vendors, f, ensure_ascii=False, indent=2)

            # 엔진 캐시 메모리도 동기화 (단일 업데이트는 별도로 없으나 다음 요청 시 불러올 때 문제없도록 함)
            engine.add_log(f"✅ {req.vendor_id} 업체의 AI 지식 커스텀 편집 사항이 저장되었습니다.", "SUCCESS", False)
            return {"status": "success", "message": "업데이트 완료"}

        return {"status": "error", "message": "업체를 찾을 수 없습니다."}
    except Exception as e:
        engine.add_log(f"❌ {req.vendor_id} AI 규칙 업데이트 실패: {e}", "ERROR", False)
        return {"status": "error", "message": str(e)}


class UpdateVendorSettingsSimpleRequest(BaseModel):
    vendor_id: str
    vendor_code: str
    price_margin: str

@app.post("/api/update_vendor_settings_simple")
def update_vendor_settings_simple(req: UpdateVendorSettingsSimpleRequest):
    """지정된 벤더의 업체코드와 단가 보정값만 수동으로 신속 업데이트한다."""
    engine = get_engine()
    import json, os, re
    vendor_file = os.path.join(_BASE_DIR, "weishang_vendors.json")
    try:
        if not os.path.exists(vendor_file):
            return {"status": "error", "message": "업체 목록 파일이 존재하지 않습니다."}

        with open(vendor_file, "r", encoding="utf-8") as f:
            vendors = json.load(f)

        updated = False
        for v in vendors:
            if v.get("id") == req.vendor_id:
                # 보정단가 필터링하여 price_offset도 갱신
                cleaned_margin = re.sub(r'[^\d\-]', '', str(req.price_margin).strip())
                v["price_offset"] = int(cleaned_margin) if cleaned_margin else 0
                v["vendor_code"] = req.vendor_code
                v["price_margin"] = req.price_margin
                updated = True
                break

        if updated:
            with open(vendor_file, "w", encoding="utf-8") as f:
                json.dump(vendors, f, ensure_ascii=False, indent=2)
            
            engine.add_log(f"✅ {req.vendor_id} 업체의 설정(코드: {req.vendor_code}, 보정: {req.price_margin})이 영구 저장되었습니다.", "SUCCESS", False)
            return {"status": "success", "message": "저장 완료"}
        
        return {"status": "error", "message": "업체를 찾을 수 없습니다."}
    except Exception as e:
        engine.add_log(f"❌ {req.vendor_id} 설정 저장 실패: {e}", "ERROR", False)
        return {"status": "error", "message": str(e)}


@app.post("/api/merge_similar_products")
def merge_similar_products():
    """1차 수집 완료된 상품들 중 동일 업체의 유사 상품(다른 색상 등)을 사후 병합한다."""
    import re
    import difflib
    import json
    import copy
    
    engine = get_engine()
    engine.ensure_products_loaded()
    
    # 병합용 색상 및 특수문자 제거 정규식
    COLOR_PATTERN = re.compile(
        r'(블랙|화이트|베이지|브라운|네이비|핑크|카키|그린|소라|블루|그레이|차콜|옐로우|레드|와인|퍼플|오렌지|아이보리|크림|머스타드|체리|살구|민트|오트밀|멜란지|검정|흰색|검은색|黑色|白色|灰色|蓝色|红色|黄色|绿色|橙色|紫色|粉色|棕色|米色|卡其色|藏青色|咖啡色|灰|蓝|红|黄|绿|橙|紫|粉|棕|米|卡기|藏青|咖啡|black|white|gray|grey|blue|red|yellow|green|orange|purple|pink|brown|beige|khaki|navy|coffee)\s*',
        re.IGNORECASE
    )
    
    def clean_text_for_similarity(text):
        if not text:
            return ""
        # 색상 관련 단어 제거
        text_no_color = COLOR_PATTERN.sub("", text)
        # 특수 기호 및 공백 제거로 알맹이만 비교
        return re.sub(r'[\s\W_]+', '', text_no_color)

    def extract_colors_korean(text):
        if not text:
            return []
        matches = re.findall(r'(?:컬러|색상|color)\s*[:：]\s*([^\n]+)', text, re.IGNORECASE)
        colors = []
        if matches:
            for match in matches:
                parts = re.split(r'[,/|·+ㆍ\s]+', match.strip())
                for p in parts:
                    p_clean = p.strip()
                    if p_clean and len(p_clean) < 10:
                        colors.append(p_clean)
        return colors

    def replace_colors_korean(text, new_colors):
        if not text or not new_colors:
            return text
        new_color_str = " / ".join(new_colors)
        pattern = re.compile(r'([✔]?\s*(?:컬러|색상|color)\s*[:：]\s*)([^\n]+)', re.IGNORECASE)
        if pattern.search(text):
            return pattern.sub(rf'\g<1>{new_color_str}', text)
        else:
            return text + f"\n\n✔ 컬러 : {new_color_str}"

    with engine.lock:
        products = [copy.deepcopy(p) for p in engine.crawled_products]
    
    if not products:
        return {"status": "success", "message": "병합할 상품이 존재하지 않습니다.", "merged_count": 0}

    from collections import defaultdict
    vendor_groups = defaultdict(list)
    for p in products:
        vendor = p.get("vendor_name", "Unknown").strip()
        vendor_groups[vendor].append(p)

    merged_ids_to_delete = set()
    updated_products_map = {}
    
    merged_pair_count = 0

    for vendor, group in vendor_groups.items():
        group_sorted = sorted(group, key=lambda x: x.get("db_id", 0))
        
        i = 0
        while i < len(group_sorted):
            main_p = group_sorted[i]
            main_db_id = main_p.get("db_id")
            
            if main_db_id in merged_ids_to_delete:
                i += 1
                continue

            main_raw = main_p.get("original_chinese", "") or main_p.get("raw_description", "") or main_p.get("title", "")
            main_cleaned = clean_text_for_similarity(main_raw)

            j = i + 1
            while j < len(group_sorted):
                sub_p = group_sorted[j]
                sub_db_id = sub_p.get("db_id")

                if sub_db_id in merged_ids_to_delete:
                    j += 1
                    continue

                sub_raw = sub_p.get("original_chinese", "") or sub_p.get("raw_description", "") or sub_p.get("title", "")
                sub_cleaned = clean_text_for_similarity(sub_raw)

                similarity = 0.0
                if main_cleaned and sub_cleaned:
                    similarity = difflib.SequenceMatcher(None, main_cleaned, sub_cleaned).ratio()

                # 상품명(title) 유사도 체크
                main_title_cleaned = clean_text_for_similarity(main_p.get("title", ""))
                sub_title_cleaned = clean_text_for_similarity(sub_p.get("title", ""))
                title_similarity = 0.0
                if main_title_cleaned and sub_title_cleaned:
                    title_similarity = difflib.SequenceMatcher(None, main_title_cleaned, sub_title_cleaned).ratio()

                main_codes = set(re.findall(r'[A-Za-z0-9]{6,}', main_p.get("raw_description", "") + main_p.get("product_code", "")))
                sub_codes = set(re.findall(r'[A-Za-z0-9]{6,}', sub_p.get("raw_description", "") + sub_p.get("product_code", "")))
                filtered_main_codes = {c for c in main_codes if not (c.startswith("NDM") or c.startswith("UNK"))}
                filtered_sub_codes = {c for c in sub_codes if not (c.startswith("NDM") or c.startswith("UNK"))}
                code_matched = bool(filtered_main_codes & filtered_sub_codes)

                if (similarity >= 0.82 and title_similarity >= 0.82) or (code_matched and title_similarity >= 0.82):
                    merged_ids_to_delete.add(sub_db_id)
                    
                    main_images = main_p.get("image_files", []) or []
                    sub_images = sub_p.get("image_files", []) or []
                    main_p["image_files"] = list(dict.fromkeys(main_images + sub_images))

                    main_paths = main_p.get("local_image_paths", []) or []
                    sub_paths = sub_p.get("local_image_paths", []) or []
                    main_p["local_image_paths"] = list(dict.fromkeys(main_paths + sub_paths))

                    main_colors = extract_colors_korean(main_p.get("raw_description", ""))
                    sub_colors = extract_colors_korean(sub_p.get("raw_description", ""))
                    all_colors = list(dict.fromkeys(main_colors + sub_colors))
                    
                    if all_colors:
                        for text_field in ["raw_description", "band_text", "insta_text"]:
                            if main_p.get(text_field):
                                main_p[text_field] = replace_colors_korean(main_p[text_field], all_colors)

                    sub_cn = sub_p.get("original_chinese", "")
                    if sub_cn and sub_cn not in (main_p.get("original_chinese", "") or ""):
                        main_p["original_chinese"] = (main_p.get("original_chinese", "") or "") + f"\n\n[병합색상 본문]\n" + sub_cn

                    updated_products_map[main_db_id] = main_p
                    merged_pair_count += 1
                    
                    group_sorted[j] = main_p

                j += 1
            i += 1

    if not merged_ids_to_delete:
        return {"status": "success", "message": "새로 병합할 유사 상품이 감지되지 않았습니다.", "merged_count": 0}

    db = get_db()
    try:
        for sub_id in merged_ids_to_delete:
            db.delete_product_by_id(sub_id)
        
        for main_id, updated_p in updated_products_map.items():
            db.update_product_by_id(main_id, updated_p)
            
        with engine.lock:
            filtered_prods = [p for p in engine.crawled_products if p.get("db_id") not in merged_ids_to_delete]
            for idx, p in enumerate(filtered_prods):
                db_id = p.get("db_id")
                if db_id in updated_products_map:
                    filtered_prods[idx] = updated_products_map[db_id]
            
            engine.crawled_products = filtered_prods
        
        engine.add_log(f"🎨 [사후 병합] 총 {merged_pair_count}건의 유사 색상 상품이 성공적으로 통합되었습니다. (서브 {len(merged_ids_to_delete)}건 삭제 완료)", "SUCCESS", False)
        engine.notify_update()
        
        return {"status": "success", "message": f"{merged_pair_count}쌍 병합 완료", "merged_count": len(merged_ids_to_delete)}
    except Exception as e:
        engine.add_log(f"❌ 사후 병합 처리 오류: {e}", "ERROR", False)
        return {"status": "error", "message": str(e)}


@app.get("/api/crawled_products")
def get_crawled_products(load: bool = True):
    """크롤링된 상품 데이터를 조회한다."""
    engine = get_engine()
    if load:
        engine.ensure_products_loaded()
    with engine.lock:
        data = [dict(item) for item in engine.crawled_products]
        try:
            from pricing_logic import clean_vendor_name
        except ImportError:
            from backend.pricing_logic import clean_vendor_name
        for item in data:
            if "vendor_name" in item:
                item["vendor_name"] = clean_vendor_name(item["vendor_name"])
    try:
        status_map = engine.db.get_latest_post_status_map()
        platform_fields = {
            "카카오스토리": ("post_status_kakao", "post_error_kakao"),
            "네이버 밴드": ("post_status_band", "post_error_band"),
        }
        for item in data:
            product_code = item.get("product_code", "")
            content_signature = engine._build_post_content_signature(item)
            for platform, (status_field, error_field) in platform_fields.items():
                # 현재 실행 중 메모리에 기록된 상태가 있으면 그것을 우선합니다.
                if item.get(status_field):
                    continue
                post_state = status_map.get((f"signature:{content_signature}", platform))
                if not post_state and not content_signature and product_code:
                    post_state = status_map.get((f"code:{product_code}", platform))
                if not post_state:
                    continue
                raw_status = post_state.get("status", "")
                if raw_status == "SUCCESS":
                    item[status_field] = "success"
                    item[error_field] = ""
                elif raw_status == "DRY_RUN":
                    item[status_field] = "dry_run"
                    item[error_field] = "Dry-run 시뮬레이션 성공"
                elif raw_status == "FAIL":
                    item[status_field] = "fail"
                    item[error_field] = post_state.get("error_reason", "")
    except Exception as e:
        engine.add_log(f"⚠️ 게시 상태 병합 실패: {str(e)[:80]}", "WARNING", False)
    return {
        "count": len(data),
        "saved_count": getattr(engine, "db_saved_product_count", len(data)),
        "products_loaded": getattr(engine, "products_loaded", True),
        "db_load_progress": getattr(engine, "db_load_progress", {}),
        "products": data,
        "qr_base64": getattr(engine, "weishang_qr_base64", None)
    }

@app.get("/api/db_load_progress")
def get_db_load_progress():
    """DB에서 크롤링 데이터 불러오기 진행률을 반환합니다."""
    engine = get_engine()
    return engine.db_load_progress

@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    try:
        from backend.license_manager import check_license_status
        license_info = check_license_status()
        if not license_info.get("is_valid"):
            # 로컬 테스트 편의성을 위해 라이센스가 유효하지 않더라도 연결을 강제로 끊지 않고 로그만 출력합니다.
            print(f"[라이선스 경고] {license_info.get('message')}")
    except Exception as e:
        print(f"[라이선스 예외] {e}")
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming WS messages if needed
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

class UpdateProductRequest(BaseModel):
    index: int
    field: str
    value: Any

@app.put("/api/crawled_products")
def update_crawled_product(req: UpdateProductRequest):
    """크롤링된 상품 데이터를 수정한다."""
    engine = get_engine()
    with engine.lock:
        if 0 <= req.index < len(engine.crawled_products):
            engine.crawled_products[req.index][req.field] = req.value
            from backend.database import get_db
            get_db().update_product_by_index(req.index, engine.crawled_products[req.index])
            engine.add_log(f"✏️ 상품 {req.index+1} [{req.field}] 수정 완료", "INFO", False)
            return {"status": "updated"}
    return {"status": "error", "message": "잘못된 인덱스"}

class FinalReviewRequest(BaseModel):
    indices: Optional[List[int]] = None
    use_ai: bool = True
    max_ai_items: int = 5
    api_key: Optional[str] = None
    fx: Optional[float] = None
    category: Optional[str] = None

def _review_text(value) -> str:
    return str(value or "").strip()

def _review_is_missing_number(value) -> bool:
    text = _review_text(value)
    if text in ("", "-", "0", "None", "none", "단가미상", "단가없음"):
        return True
    digits = re.sub(r"[^\d]", "", text)
    return not digits or int(digits or 0) <= 0

def _review_normalize_image_key(value) -> str:
    text = _review_text(value).replace("\\", "/").split("?")[0].split("#")[0].lower()
    return os.path.basename(text) or text

def _review_reorder_and_dedupe_images(values):
    if not isinstance(values, list):
        return values, 0, False

    seen = set()
    unique = []
    removed = 0
    for value in values:
        key = _review_normalize_image_key(value)
        if not key:
            continue
        if key in seen:
            removed += 1
            continue
        seen.add(key)
        unique.append(value)

    def is_size_chart(item):
        text = _review_text(item).lower()
        return any(token in text for token in ("尺码", "尺寸", "size", "사이즈", "sizechart", "size_chart"))

    size_items = [item for item in unique if is_size_chart(item)]
    body_items = [item for item in unique if not is_size_chart(item)]
    # 20장 자르기 제한을 제거하고, 사이즈표를 가장 마지막으로 보내는 정렬만 수행
    ordered = body_items + size_items

    changed = ordered != values
    if len(unique) > len(ordered):
        removed += len(unique) - len(ordered)
    return ordered, removed, changed

def _review_extract_price_from_text(text):
    text = _review_text(text)
    if not text:
        return ""

    guard = re.compile(r"(货号|款号|搜索码|商品编号|编码|尺码|尺寸|码数|size|Size|SIZE|机芯|规格|sw\d*|eta\b|cal\b|miyota|미요타|오토|automatic|quartz|쿼츠|18k|24k|14k|最新|新款|new|release|寸|inch|인치|포장박스|게런티|게런티카드|부속품|가로|세로|높이|폭|长|宽|高|厚)", re.I)
    patterns = [
        r"(?:🅿️?|[PpＰｐ]|出厂价|批发价|批价|拿货价|出货价|成本价|供货价|档口价|가격|금액|价格|售价|批发|拿货)\s*[:：]?\s*[¥￥]?\s*(\d{2,4})\b",
        r"[¥￥]\s*(\d{2,4})\b",
        r"💰\s*(\d{2,4})\b",
    ]
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        has_explicit_price_word = any(re.search(pat, line, re.I) for pat in [r"[PpＰｐ]", "出厂价", "批发价", "批价", "拿货价", "出货价", "价格", "售价", "💰", "[¥￥]", "가격", "금액", "批发", "拿货"])
        if not has_explicit_price_word and guard.search(line):
            continue
        for pattern in patterns:
            match = re.search(pattern, line, re.I)
            if not match:
                continue
            value = int(match.group(1))
            if 20 <= value <= 5000:
                return str(value)
    return ""

def _review_code_is_ok(code) -> bool:
    text = _review_text(code).upper()
    if not text or text == "AUTO":
        return False
    if re.search(r"[\s가-힣\u4e00-\u9fff]", text):
        return False
    compact = re.sub(r"[^A-Z0-9_-]", "", text)
    if len(compact) < 6:
        return False
    return not compact.isdigit()

def _review_translation_is_suspicious(product) -> bool:
    title = _review_text(product.get("title"))
    desc = _review_text(product.get("raw_description") or product.get("description"))
    vendor = _review_text(product.get("vendor_name"))
    generic_title = not title or title.lower() in ("item", "unknown", "상품") or (vendor and title == f"{vendor} 상품")
    has_chinese = bool(re.search(r"[\u4e00-\u9fff]", f"{title}\n{desc}"))
    too_short = len(desc) < 18
    machine_noise = bool(re.search(r"(undefined|null|nan|상품속성|商品属性)", f"{title}\n{desc}", re.I))
    return generic_title or has_chinese or too_short or machine_noise

def _review_sanitize_description(desc, product_code=None, old_code=None):
    text = _review_text(desc)
    if not text:
        return text
    text = text.replace("복각", "재현")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"(ㅡ{8,}\n?){3,}", "ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ\n", text)
    if product_code and old_code and old_code != product_code:
        text = re.sub(rf"\b{re.escape(old_code)}\b", product_code, text)
    if product_code and re.search(r"상품코드\s*[:：]", text):
        text = re.sub(r"상품코드\s*[:：]\s*[A-Za-z0-9_-]+", f"상품코드: {product_code}", text)
    return text.strip()

def _run_minimal_ai_final_review(product, api_key):
    """번역문이 의심될 때만 짧은 텍스트 검토를 수행합니다."""
    if not api_key:
        return {}
    raw = _review_text(product.get("original_chinese") or product.get("raw_text"))
    desc = _review_text(product.get("raw_description") or product.get("description"))
    title = _review_text(product.get("title"))
    if not (raw or desc or title):
        return {}
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        prompt = f"""
너는 쇼핑몰 업로드 전 최종 검토자다. 비용 절감을 위해 오직 텍스트만 확인한다.
아래 상품의 한국어 제목/본문이 중국어 그대로 남았거나 이상하면 자연스럽게 최소 수정하라.
가격, 상품코드, 사진 순서는 절대 새로 만들지 말라.
응답은 JSON만 반환하라.

현재 제목: {title[:300]}
현재 한국어 본문: {desc[:1200]}
중국어 원문 참고: {raw[:1200]}

형식:
{{"title":"수정 제목 또는 기존 제목", "raw_description":"수정 본문 또는 기존 본문", "reason":"짧은 수정 이유"}}
"""
        res = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        text = (getattr(res, "text", "") or "").strip()
        if not text:
            return {}
        return json.loads(text)
    except Exception:
        return {}

@app.post("/api/crawled_products/final_review")
def final_review_crawled_products(req: FinalReviewRequest):
    """리스트 상품을 업로드 전 최종 검토하고, 저비용 규칙 기반 수정 후 의심 항목만 AI로 보정합니다."""
    engine = get_engine()
    engine.ensure_products_loaded()

    target_indices = req.indices
    api_key = _get_gemini_key(req.api_key or "")
    max_ai_items = _bounded_int(req.max_ai_items, 5, 0, 20)
    base_fx = float(req.fx or 0) if req.fx else float(get_system_settings().get("naver_fx", 200.0) or 200.0)
    if base_fx <= 0:
        base_fx = 200.0

    try:
        from backend.pricing_logic import generate_product_code_and_price
    except ImportError:
        from pricing_logic import generate_product_code_and_price

    reviewed = 0
    changed_count = 0
    ai_used = 0
    issue_summary = []

    from backend.database import get_db

    with engine.lock:
        if target_indices is None or len(target_indices) == 0:
            indices = list(range(len(engine.crawled_products)))
        else:
            indices = sorted({int(i) for i in target_indices if isinstance(i, int) or str(i).isdigit()})

        for idx in indices:
            if idx < 0 or idx >= len(engine.crawled_products):
                continue
            reviewed += 1
            product = dict(engine.crawled_products[idx])
            original_product = dict(product)
            issues = []
            fixes = []

            # 1. 사진 배열: 중복 제거, 사이즈표 마지막, 20장 제한
            for image_field in ("image_files", "local_image_paths", "image_urls", "image_server_urls"):
                new_values, removed, changed = _review_reorder_and_dedupe_images(product.get(image_field))
                if changed:
                    product[image_field] = new_values
                    if removed:
                        fixes.append(f"{image_field} 중복/초과 {removed}개 정리")
                    else:
                        fixes.append(f"{image_field} 순서 정리")
            image_count = len(product.get("image_files") or product.get("local_image_paths") or product.get("image_urls") or [])
            if image_count == 0:
                issues.append("이미지 없음")

            # 2. 단가: 본문 명시 가격만 보수적으로 추출
            raw_text = "\n".join([
                _review_text(product.get("original_chinese")),
                _review_text(product.get("raw_text")),
                _review_text(product.get("raw_description")),
            ])
            if _review_is_missing_number(product.get("price_input")):
                extracted_price = _review_extract_price_from_text(raw_text)
                if extracted_price:
                    product["price_input"] = extracted_price
                    product["price_source"] = "final_review_text"
                    fixes.append(f"단가 {extracted_price} 보정")
                else:
                    issues.append("단가 미확정")

            # 3. 상품코드/판매가: 단가가 있을 때만 계산으로 보정
            old_code = _review_text(product.get("product_code"))
            price_ready = not _review_is_missing_number(product.get("price_input"))
            if price_ready:
                generated_code, computed_sale_price, dg_display, calc_log = generate_product_code_and_price(
                    product.get("vendor_name", ""),
                    product.get("price_input", ""),
                    product.get("category") or req.category or "",
                    product.get("title", ""),
                    raw_text,
                    base_fx,
                )
                if generated_code and generated_code != "AUTO" and not _review_code_is_ok(product.get("product_code")):
                    product["product_code"] = generated_code
                    fixes.append("상품코드 자동 보정")
                if computed_sale_price and (_review_is_missing_number(product.get("sale_price")) or int(re.sub(r"[^\d]", "", str(product.get("sale_price") or "0")) or 0) < 1000):
                    product["sale_price"] = str(computed_sale_price)
                    fixes.append(f"판매가 {computed_sale_price:,}원 보정")
                product["price_detected"] = True
                product["price_calc_log"] = calc_log
            else:
                if not _review_code_is_ok(product.get("product_code")):
                    issues.append("상품코드 미확정")
                if _review_is_missing_number(product.get("sale_price")):
                    issues.append("판매가 미확정")

            # 4. 번역문 기본 정리 및 의심 항목만 AI 보정
            desc_before = product.get("raw_description", "")
            sanitized_desc = _review_sanitize_description(desc_before, product.get("product_code"), old_code)
            if sanitized_desc != _review_text(desc_before):
                product["raw_description"] = sanitized_desc
                fixes.append("번역문 기본 정리")

            if _review_translation_is_suspicious(product):
                issues.append("번역문 검토 필요")
                if req.use_ai and ai_used < max_ai_items and api_key:
                    ai_result = _run_minimal_ai_final_review(product, api_key)
                    if isinstance(ai_result, list) and len(ai_result) > 0:
                        ai_result = ai_result[0]

                    if isinstance(ai_result, dict):
                        ai_title = _review_text(ai_result.get("title"))
                        ai_desc = _review_text(ai_result.get("raw_description"))
                        if ai_title and ai_title != _review_text(product.get("title")):
                            product["title"] = ai_title[:120]
                            fixes.append("AI 제목 보정")
                        if ai_desc and ai_desc != _review_text(product.get("raw_description")):
                            product["raw_description"] = _review_sanitize_description(ai_desc, product.get("product_code"), old_code)
                            fixes.append("AI 본문 보정")
                        if ai_result:
                            ai_used += 1

            product["final_review_status"] = "fixed" if fixes else ("needs_check" if issues else "ok")
            product["final_review_issues"] = issues
            product["final_review_fixes"] = fixes
            product["final_review_at"] = datetime.datetime.now().isoformat(timespec="seconds")

            if product != original_product:
                engine.crawled_products[idx] = product
                get_db().update_product_by_index(idx, product)
                if fixes:
                    changed_count += 1

            if issues or fixes:
                issue_summary.append({
                    "index": idx,
                    "title": product.get("title", "")[:60],
                    "issues": issues[:5],
                    "fixes": fixes[:5],
                    "status": product["final_review_status"],
                })

    engine.add_log(
        f"🧾 AI 최종검토 완료: {reviewed}건 검토, {changed_count}건 수정, AI 사용 {ai_used}건",
        "SUCCESS",
        False,
    )
    engine.notify_update()
    return {
        "status": "success",
        "reviewed_count": reviewed,
        "changed_count": changed_count,
        "ai_used": ai_used,
        "issue_count": len([item for item in issue_summary if item.get("issues")]),
        "summary": issue_summary[:80],
    }

class DeleteProductRequest(BaseModel):
    index: int

@app.delete("/api/crawled_products")
def delete_crawled_product(req: DeleteProductRequest):
    """크롤링된 상품을 삭제한다."""
    engine = get_engine()
    with engine.lock:
        if 0 <= req.index < len(engine.crawled_products):
            from backend.database import get_db
            db = get_db()
            target_prod = engine.crawled_products[req.index]
            db_id = target_prod.get("db_id")
            if db_id is not None:
                db.delete_product_by_id(db_id)
            else:
                db.delete_product_by_index(req.index)
            removed = engine.crawled_products.pop(req.index)
            engine.db_saved_product_count = db.count_all_products()
            engine.add_log(f"🗑️ 상품 삭제: {removed.get('title','제목없음')[:20]}...", "INFO", False)
            return {"status": "deleted", "remaining": len(engine.crawled_products)}
    return {"status": "error", "message": "잘못된 인덱스"}

class DeleteBulkProductsRequest(BaseModel):
    indices: list[int]

@app.delete("/api/crawled_products/bulk")
def delete_crawled_products_bulk(req: DeleteBulkProductsRequest):
    """크롤링된 상품 여러 개를 한 번에 삭제합니다."""
    engine = get_engine()
    sorted_indices = sorted(req.indices, reverse=True)
    deleted_count = 0
    with engine.lock:
        from backend.database import get_db
        db = get_db()
        
        db_ids_to_delete = []
        indices_fallback = []
        for idx in sorted_indices:
            if 0 <= idx < len(engine.crawled_products):
                prod = engine.crawled_products[idx]
                db_id = prod.get("db_id")
                if db_id is not None:
                    db_ids_to_delete.append(db_id)
                else:
                    indices_fallback.append(idx)
                    
        if db_ids_to_delete:
            db.delete_products_bulk_by_ids(db_ids_to_delete)
        if indices_fallback:
            db.delete_products_bulk_by_indices(indices_fallback)
            
        for idx in sorted_indices:
            if 0 <= idx < len(engine.crawled_products):
                removed = engine.crawled_products.pop(idx)
                deleted_count += 1
                
        engine.db_saved_product_count = db.count_all_products()
        engine.add_log(f"선택한 {deleted_count}개 상품 일괄 삭제 완료", "INFO", False)
        return {"status": "deleted", "deleted_count": deleted_count, "remaining": len(engine.crawled_products)}

@app.delete("/api/crawled_products/all")
def delete_crawled_products_all():
    """크롤링된 모든 상품을 삭제합니다 (삭제 전 DB에 백업)."""
    engine = get_engine()
    if not getattr(engine, "products_loaded", True) and getattr(engine, "db_saved_product_count", 0) > 0:
        engine.ensure_products_loaded()
    with engine.lock:
        from backend.database import get_db
        db = get_db()
        db_product_count = 0
        try:
            db_product_count = db.count_all_products()
        except Exception as e:
            engine.add_log(f"DB 상품 개수 조회 실패: {e}", "WARNING", False)

        if db_product_count > 0 or engine.crawled_products:
            try:
                db.backup_current_products()
            except Exception as e:
                engine.add_log(f"전체 삭제 중 백업 실패: {e}", "WARNING", False)
                pass

        deleted_count = db_product_count if db_product_count > 0 else len(engine.crawled_products)
        engine.crawled_products.clear()

        try:
            db.truncate_all()
            engine.db_saved_product_count = 0
            engine.products_loaded = True
        except Exception:
            pass

        engine.add_log(f"초기화에 의해 {deleted_count}개 전체 상품 삭제 완료 (DB 백업됨)", "INFO", False)
        return {"status": "deleted", "deleted_count": deleted_count, "remaining": 0}

@app.get("/api/crawled_products/backup_info")
def get_backup_info():
    """DB 백업 그룹(타임라인) 리스트를 반환합니다."""
    from backend.database import get_db
    try:
        db = get_db()
        groups = db.get_backup_groups_info()
        if not groups:
            return {"status": "empty", "message": "저장된 백업 슬롯이 없습니다."}
        return {"status": "ok", "groups": groups}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/crawled_products/backup_group_detail")
def get_backup_group_detail(group_id: str):
    """특정 백업 슬롯의 상세 상품 리스트를 반환합니다."""
    try:
        from backend.database import get_db
        import os
        db = get_db()
        backup_data = db.get_backup_products_by_group(group_id)

        items = []
        for i, item in enumerate(backup_data):
            try:
                thumb = ""
                img_files = item.get("image_files", [])
                img_dir = item.get("local_image_dir", "")
                if img_files and img_dir:
                    thumb = os.path.join(img_dir, img_files[0])

                items.append({
                    "idx": i,
                    "title": (item.get("title") or "")[:40],
                    "sale_price": item.get("sale_price", ""),
                    "created_at": (item.get("created_at") or "")[:19],
                    "thumb": thumb,
                })
            except:
                pass

        # 최신순 정렬 (옵션)
        items.reverse()
        # 원래의 idx를 유지해야 restore_selected 할 때 정확히 매핑됨
        # reverse 했지만 idx 필드는 원본 인덱스를 가지고 있으므로 문제없음

        return {"status": "ok", "items": items, "count": len(items)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/crawled_products/restore_backup_selected")
async def restore_backup_selected(request: Request):
    """특정 백업 슬롯에서 선택한 인덱스의 상품만 현재 리스트에 추가합니다."""
    engine = get_engine()
    data = await request.json()
    group_id = data.get("backup_group_id", "")
    indices = data.get("indices", [])

    if not group_id:
        return {"status": "error", "message": "백업 슬롯이 지정되지 않았습니다."}
    if not indices:
        return {"status": "error", "message": "선택된 상품이 없습니다."}

    try:
        from backend.database import get_db
        db = get_db()
        backup_data = db.get_backup_products_by_group(group_id)

        if not backup_data:
            return {"status": "error", "message": "해당 그룹의 백업 데이터가 없습니다."}

        added = 0
        with engine.lock:
            for idx in sorted(indices):
                if 0 <= idx < len(backup_data):
                    item = backup_data[idx]
                    engine.crawled_products.append(item)
                    db.add_product(item)
                    added += 1
            engine.products_loaded = True
            engine.db_saved_product_count = db.count_all_products()

        engine.add_log(f"📂 DB 백업에서 선택한 {added}건 상품 추가 완료", "INFO", False)
        engine.notify_update()
        return {"status": "success", "count": added}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.delete("/api/crawled_products/backup_selected")
async def delete_backup_selected(request: Request):
    """특정 백업 슬롯에서 선택한 인덱스의 상품을 백업 목록에서 삭제합니다."""
    engine = get_engine()
    data = await request.json()
    group_id = data.get("backup_group_id", "")
    indices = data.get("indices", [])

    if not group_id:
        return {"status": "error", "message": "백업 슬롯이 지정되지 않았습니다."}
    if not indices:
        return {"status": "error", "message": "선택된 상품이 없습니다."}

    try:
        from backend.database import get_db
        db = get_db()
        deleted = db.delete_backup_products_by_group_indices(group_id, indices)
        remaining = len(db.get_backup_products_by_group(group_id))

        engine.add_log(f"🗑️ 백업 슬롯에서 선택한 {deleted}건 삭제 완료", "INFO", False)
        return {"status": "success", "deleted_count": deleted, "remaining": remaining}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.delete("/api/crawled_products/backup_groups")
async def delete_backup_groups(request: Request):
    """선택한 백업 슬롯 전체를 삭제합니다."""
    engine = get_engine()
    data = await request.json()
    group_ids = data.get("backup_group_ids", [])

    if not group_ids:
        return {"status": "error", "message": "선택된 백업 슬롯이 없습니다."}

    try:
        from backend.database import get_db
        db = get_db()
        deleted = db.delete_backup_groups(group_ids)
        groups = db.get_backup_groups_info()

        engine.add_log(f"🗑️ 백업 슬롯 {len(set(group_ids))}개 삭제 완료 ({deleted}건)", "INFO", False)
        return {"status": "success", "deleted_count": deleted, "groups": groups}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/crawled_products/restore_backup")
async def restore_crawled_products_backup(request: Request):
    """지정된 타임라인의 백업을 복구합니다."""
    engine = get_engine()
    data = await request.json()
    group_id = data.get("backup_group_id", "")

    if not group_id:
        return {"status": "error", "message": "복구할 백업 슬롯이 지정되지 않았습니다."}

    with engine.lock:
        try:
            from backend.database import get_db
            db = get_db()
            backup_data = db.get_backup_products_by_group(group_id)

            if not backup_data:
                return {"status": "error", "message": "해당 백업 데이터가 비어 있습니다."}

            engine.crawled_products.clear()
            db.truncate_all()

            for item in backup_data:
                engine.crawled_products.append(item)
                db.add_product(item)

            engine.products_loaded = True
            engine.db_saved_product_count = len(engine.crawled_products)
            engine.add_log(f"📂 타임머신 복구 완료: {len(backup_data)}건 상품 복원", "INFO", False)
            engine.notify_update()
            return {"status": "success", "count": len(backup_data)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

@app.post("/api/crawled_products/save_backup")
async def save_crawled_products_backup(request: Request):
    """현재 상품 리스트를 새로운 그룹(버전)으로 스냅샷 백업합니다."""
    engine = get_engine()
    try:
        data = await request.json()
        custom_name = data.get("custom_name", "")
        product_codes = data.get("product_codes", None)
    except:
        custom_name = ""
        product_codes = None

    with engine.lock:
        try:
            from backend.database import get_db
            check_list = product_codes if product_codes is not None else engine.crawled_products
            if not check_list:
                return {"status": "error", "message": "백업할 상품이 없습니다."}

            db = get_db()
            group_id = db.backup_current_products(custom_name, product_codes)

            count = len(product_codes) if product_codes is not None else len(engine.crawled_products)
            engine.add_log(f"💾 상품 리스트 스마트 백업 스냅샷 저장 완료! ({count}건)", "INFO", False)
            return {"status": "success", "count": count, "group_id": group_id}
        except Exception as e:
            return {"status": "error", "message": str(e)}

# ─── 공통 번역 응답 파서 ────────────────────────────────────────────────────
try:
    from backend.pricing_logic import parse_gemini_translation_common
except ImportError:
    from pricing_logic import parse_gemini_translation_common
try:
    from backend.ai_services import detect_category_with_vision
except ImportError:
    from ai_services import detect_category_with_vision

class TranslateManualRequest(BaseModel):
    raw_text: str
    api_key: str = ""
    custom_prompt: str
    category: str = "남성의류"
    prefix: str = "AUTO"
    vendor_name: str = ""
    image_path: str = ""

@app.post("/api/translate_manual")
def translate_manual(req: TranslateManualRequest):
    """지정된 프롬프트를 사용하여 AI 번역 수행"""
    api_key = _get_gemini_key(req.api_key)
    if not api_key:
        return {"status": "error", "message": "Gemini API 키가 입력되지 않았습니다."}
    if not req.raw_text:
        return {"status": "error", "message": "원본 텍스트가 없습니다."}

    try:
        from backend.database import get_cached_translation, set_cached_translation
        from backend.crawler_engine import get_engine

        # 1. Vision API를 활용한 카테고리 자동 교정
        final_category = req.category

        # 2. 먼저 캐시 조회 (동일 원문 + 카테고리)
        # 사용자/업체/밴드 기준 지침이 들어간 번역은 오래된 캐시가 품질을 막을 수 있어 새로 생성한다.
        use_translation_cache = not bool(str(req.custom_prompt or "").strip())
        image_key = req.image_path if hasattr(req, 'image_path') and req.image_path else ""
        cached_json = get_cached_translation(req.raw_text, final_category, image_key) if use_translation_cache else None
        if cached_json:
            import json
            try:
                out_data = json.loads(cached_json)
                from backend.pricing_logic import parse_gemini_translation_common, get_vendor_code

                kakao_text = out_data.get("kakao_text", "")
                band_text = out_data.get("band_text", "")
                insta_text = out_data.get("insta_text", "")
                core_material = out_data.get("core_material", "")
                hashtags = out_data.get("hashtags", [])

                final_text, title, sale_price, product_code = parse_gemini_translation_common(kakao_text, req.prefix, "", req.vendor_name)

                if req.vendor_name:
                    vendor_code_str = get_vendor_code(req.vendor_name)
                    vendor_highlight = f"✔ 업체코드: {vendor_code_str}\n"
                    if "ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ" in final_text:
                        final_text = final_text.replace("ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ", f"ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ\n{vendor_highlight}", 1)
                    else:
                        final_text = f"{title}\n{vendor_highlight}{final_text}"

                # if core_material:
                #     material_highlight = f"✨ 소재 포인트: {core_material}\nㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ\n"
                #     if "ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ" in final_text:
                #         final_text = final_text.replace("ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ", f"ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ\n{material_highlight}", 1)
                #     else:
                #         final_text = f"{title}\n{material_highlight}{final_text}"

                get_engine().add_log(f"⚡ [캐시 적중] '{final_category}' 카테고리 번역 결과를 캐시에서 즉시 불러왔습니다 (0.1초 소요).", "INFO", False)
                return {
                    "status": "success",
                    "translated_text": final_text,
                    "parsed_title": title,
                    "parsed_sale_price": sale_price,
                    "parsed_product_code": product_code,
                    "band_text": band_text,
                    "insta_text": insta_text,
                    "hashtags": hashtags,
                    "is_cached": True
                }
            except Exception as e:
                pass # 파싱 에러 시 새로 번역

        # 3. 캐시가 없으면 Vision AI로 카테고리 검증 및 보정
        if req.image_path:
            vision_cat = detect_category_with_vision(api_key, req.image_path, req.raw_text)
            if vision_cat and vision_cat != final_category:
                final_category = vision_cat
                get_engine().add_log(f"🤖 [Vision AI] 수동 번역 시 사용자가 선택한 카테고리를 '{vision_cat}'(으)로 교정하여 번역합니다.", "INFO", False)

                # 교정된 카테고리로 캐시 재확인
                image_key = req.image_path if hasattr(req, 'image_path') and req.image_path else ""
                cached_json = get_cached_translation(req.raw_text, final_category, image_key) if use_translation_cache else None
                if cached_json:
                    import json
                    try:
                        out_data = json.loads(cached_json)
                        from backend.pricing_logic import parse_gemini_translation_common, get_vendor_code
                        kakao_text = out_data.get("kakao_text", "")
                        band_text = out_data.get("band_text", "")
                        insta_text = out_data.get("insta_text", "")
                        core_material = out_data.get("core_material", "")
                        hashtags = out_data.get("hashtags", [])
                        final_text, title, sale_price, product_code = parse_gemini_translation_common(kakao_text, req.prefix, "", req.vendor_name)
                        if req.vendor_name:
                            vendor_code_str = get_vendor_code(req.vendor_name)
                            vendor_highlight = f"✔ 업체코드: {vendor_code_str}\n"
                            if "ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ" in final_text:
                                final_text = final_text.replace("ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ", f"ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ\n{vendor_highlight}", 1)
                            else:
                                final_text = f"{title}\n{vendor_highlight}{final_text}"
                        # if core_material:
                        #     material_highlight = f"✨ 소재 포인트: {core_material}\nㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ\n"
                        #     if "ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ" in final_text:
                        #         final_text = final_text.replace("ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ", f"ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ\n{material_highlight}", 1)
                        #     else:
                        #         final_text = f"{title}\n{material_highlight}{final_text}"
                        get_engine().add_log(f"⚡ [캐시 적중] 교정된 '{final_category}' 카테고리의 캐시를 즉시 반환합니다.", "INFO", False)
                        return {
                            "status": "success", "translated_text": final_text, "parsed_title": title, "parsed_sale_price": sale_price, "parsed_product_code": product_code, "band_text": band_text, "insta_text": insta_text, "hashtags": hashtags, "is_cached": True
                        }
                    except Exception:
                        pass

        from google import genai
        client = genai.Client(api_key=api_key.strip())
        # --- 카테고리별 사이즈 규칙 동적 할당 ---
        cat_lower = final_category.lower()
        if any(k in cat_lower for k in ["신발", "슬리퍼", "샌들", "스니커즈", "부츠", "로퍼", "뮬"]):
            size_rule_text = "4. 📏 신발류는 원문의 사이즈 범위(예: 38-45)를 번역하고, 아래 mm 매핑을 함께 기재할 것. (36:230~235, 37:240, 38:245, 39:250, 40:255, 41:260, 42:265~270, 43:275, 44:280, 45:285, 46:290). S/M/L 등 의류 사이즈 사용 절대 금지!"
            size_template_text = "✔ 사이즈 : 38 / 39 / 40 / 41 / 42 / 43 / 44 / 45\n  38 ▶ 245\n  39 ▶ 250\n  40 ▶ 255\n  41 ▶ 260\n  42 ▶ 265~270\n  43 ▶ 275\n  44 ▶ 280\n  45 ▶ 285\n  (원문의 사이즈 범위에 맞춰 기재, 정보가 없으면 이 항목 삭제)"
        elif any(k in cat_lower for k in ["바지", "데님", "팬츠", "하의"]):
            size_rule_text = "4. 📏 바지/팬츠류는 원문 기준(숫자 사이즈 혹은 S/M/L)을 우선하고 임의 변환하지 말 것. 실측표가 있으면 실측표 형태로 작성할 것."
            size_template_text = "✔ 사이즈 : (원문 기준 허리사이즈 또는 S/M/L 등 표기, 정보가 없으면 삭제)"
        elif any(k in cat_lower for k in ["가방", "지갑"]):
            size_rule_text = "4. 📏 가방/지갑류는 원문에 기재된 실제 크기/치수(예: 30x26x14cm 등)를 번역할 것. 의류 사이즈표(S/M/L) 절대 금지."
            size_template_text = "✔ 사이즈 : (원문의 실제 치수 번역, 정보가 없으면 삭제)"
        elif "시계" in cat_lower:
            size_rule_text = "4. 📏 시계류는 케이스 지름(예: 40mm) 등 기재된 치수를 번역할 것. 의류 사이즈표 절대 금지."
            size_template_text = "✔ 사이즈 : (원문의 케이스 지름 치수 등 번역, 정보가 없으면 삭제)"
        elif any(k in cat_lower for k in ["악세사리", "선글라스", "acc", "기타"]):
            size_rule_text = "4. 📏 액세서리류는 원문에 기재된 치수를 번역할 것. S/M/L 의류 사이즈표 절대 금지."
            size_template_text = "✔ 사이즈 : (원문의 실제 치수 번역, 정보가 없으면 삭제)"
        else: # 기본 의류 (남성의류, 여성의류, 패딩, 자켓 등)
            size_rule_text = "4. 📏 의류 사이즈는 '✔ 사이즈 : S / M / L' 형태로 적고, 각 사이즈별 한국 사이즈 매칭(▶ 기호 사용)을 포함할 것. (예: S ▶ 95, M ▶ 100)"
            size_template_text = "✔ 사이즈 : S / M / L / XL\n  S ▶ 95\n  M ▶ 100\n  L ▶ 105\n  XL ▶ 110"

        try:
            from backend.style_context import build_style_instruction
        except ImportError:
            from style_context import build_style_instruction
        style_section = build_style_instruction(final_category, include_band=True)


        profile_rule_text = ""
        if req.vendor_name:
            import json
            import os
            from backend.utils import _PROJECT_ROOT, _normalize_vendor_key
            vendor_file = os.path.join(_BASE_DIR, "weishang_vendors.json")
            if os.path.exists(vendor_file):
                try:
                    with open(vendor_file, "r", encoding="utf-8") as f:
                        vlist = json.load(f)
                        matched_vendor = None
                        for v in vlist:
                            if v.get("name") == req.vendor_name:
                                matched_vendor = v
                                break
                        if matched_vendor:
                            profile_parts = []
                            for label, key in [
                                ("업체 번역/문체 규칙", "profile_rules"),
                                ("상품 글 구성", "post_structure"),
                                ("묶음/분할 규칙", "grouping_rules"),
                                ("동일상품 매칭 규칙", "matching_rules"),
                                ("가격 표기/계산 패턴", "pricing_pattern"),
                                ("추천 판매 문체", "recommended_style"),
                                ("업체코드 (상품코드 앞자리 지정용)", "vendor_code"),
                                ("단가 보정값 (상품코드 계산 지정용)", "price_margin"),
                            ]:
                                value = matched_vendor.get(key)
                                if value:
                                    profile_parts.append(f"- {label}: {value}")
                            if profile_parts:
                                profile_rule_text = "\n\n🚨 [해당 업체 특화 AI 번역/상품화 규칙 - 최우선 참고]\n" + "\n".join(profile_parts) + "\n"
                except Exception as e:
                    print(f"Vendor profile load error: {e}")

        custom_section = ""
        if req.custom_prompt and req.custom_prompt.strip():
            custom_section = f"\n\n🚨 [사용자/업체 추가 번역 지침 - 최우선 반영]\n{req.custom_prompt.strip()}\n"

        prompt = f"""아래 [포스팅 템플릿]과 [번역 규칙]을 엄격하게 준수하여 중국어 상품 정보를 한국어 프리미엄 쇼핑몰용으로 번역해줘.
이번에는 카카오스토리용(kakao_text), 네이버 밴드용(band_text), 인스타그램용(insta_text) 3가지 버전으로 각각 작성해야 해.{profile_rule_text}{style_section}{custom_section}

[파라미터]
상품 카테고리: {final_category}

🚨 [다중 페르소나 템플릿 규칙]
0. [최고 엄격 규칙] 출력 결과물(kakao_text, band_text, insta_text)에 중국어(한자)가 단 한 글자라도 포함되어서는 절대 안 됩니다! 무조건 100% 자연스러운 한국어로 번역/의역하세요. (예: 简约圆领 -> 심플한 라운드넥)
0-1. [길이 제한] 본문 설명글을 너무 길고 장황하게 쓰지 마세요. 불필요한 미사여구를 빼고 상품의 핵심 특징만 간결하게 2~3가지 항목으로 축약하여 작성하세요.
0-2. [단어 교정] '러닝화'라는 단어는 절대 쓰지 마세요. 무조건 '런닝화' 혹은 '스니커즈'라는 단어로 대체하여 작성하세요.
0-3. [단어 치환] '이탈리아'라는 단어는 절대 쓰지 말고 무조건 '이태리'로 작성하세요. '정품'이라는 단어는 절대 쓰지 말고 무조건 '정규품싱크'로 작성하세요.
0-4. [군더더기 배제 및 인간화] 제품 특징/소재를 설명할 때 이미 단어 자체에 포함되어 있는 뻔한 설명이나 상업적 수식어(예: "~소재의 고급스러운 질감", "~공법의 디테일", "~자랑하는", "~를 사용하여 튼튼함" 등)는 완전히 빼세요. 불필요한 부연설명이나 미사여구를 모두 제거하고, 제품의 명확한 실물 사양/디테일만 딱부러지게 표현하세요.
    - 나쁜 예시: "이탈리아 수입 소가죽 소재의 고급스러운 질감", "정품 동일 공법의 로고 그래픽 디테일", "뛰어난 착화감을 자랑하는 특수 성형 밑창"
    - 좋은 예시: "이태리 수입 소가죽", "정규품싱크의 로고디테일", "뛰어난 착화감의 특수성형밑창"
1. [공통] 제목에 '[ 브랜드명 ]' 등 대괄호 태그는 절대 금지! 자연스럽게 첫 줄에 브랜드+상품명을 적을 것. 원문의 단가/금액/숫자 표시는 제목 생성 시 무조건 제외.
2. [공통] 컬러는 반드시 '✔ 컬러 : 블랙 / 화이트' 형태로 슬래시 구분 1줄. 사이즈는 아래 규칙 준수:
{size_rule_text}
3. [공통] 배송은 무조건 하단 양식처럼 '✔ 2박특송 : 입고 후 2 ~ 3일'과 '(개인통관부호 필수)'를 2줄로 추가할 것. 맨 마지막 줄에 코드나 ㄷㄱ를 임의로 생성하지 말 것.
4. [카카오스토리 버전 - kakao_text]
   기존처럼 개조식(`✔ 특징`)으로 짧고 명료하게 핵심만 전달. 각 항목 사이에는 ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ (14개) 구분선 삽입.
5. [네이버 밴드 버전 - band_text]
   친근한 소매상/단골 대상 어투 사용 ("언니들~ 이번에 들어온 신상...", "사장님들 퀄리티 미쳤어요 강추합니다!"). 카카오버전의 내용(컬러/사이즈/배송)은 하단에 동일하게 포함.
6. [인스타그램 버전 - insta_text]
   감성적이고 트렌디한 설명. 개조식(✔)보다는 자연스러운 줄글 형태로 작성하고, 해시태그를 본문 맨 아래 자연스럽게 배치. 컬러/사이즈/배송 정보는 심플하게 포함.
7. [소재 추출 - core_material]
   원문에 최고급 송아지 가죽(Calfskin), 캐시미어, 100% 면, 실크 등 핵심 프리미엄 소재가 있다면 그것만 딱 1~2단어로 추출. (예: "최고급 송아지 가죽", "캐시미어 100%"). 없으면 빈 문자열.
8. [해시태그 - hashtags]
   인스타그램 등에 쓸 최적의 한글 해시태그 5개를 배열로 생성.
9. [브랜드 추론 - detected_brand]
   원문에 은어나 알파벳 약어로 표기된 명품 브랜드명(예: sch/Schiapa -> Schiaparelli, lv -> Louis Vuitton, cc/C사 -> Chanel, h/H사 -> Hermes, d/D사 -> Dior, p/P사 -> Prada, b/B사 -> Balenciaga, g/G사 -> Gucci 등)이 있다면 이를 정식 명칭으로 풀어내어 번역본 제목 및 detected_brand에 정확히 반영할 것. 약어가 없거나 모를 경우 원문 그대로 사용.
10. [복수 상품 혼합 주의]
   원문에 여러 상품(구찌, 루이비통 등)의 설명이 섞여서 기재되어 있을 경우, 제공된 첨부 사진(또는 대표 사진)에 해당하는 상품의 설명만 골라서 번역할 것. 사진이 없거나 모를 경우 가장 위에 있는 메인 상품 1개만 번역하고 나머지는 과감히 버릴 것.

[중국어 원문]:
{req.raw_text}"""

        res = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=[prompt],
            config={"response_mime_type": "application/json", "response_schema": {
                "type": "OBJECT",
                "properties": {
                    "detected_brand": {"type": "STRING"},
                    "kakao_text": {"type": "STRING"},
                    "band_text": {"type": "STRING"},
                    "insta_text": {"type": "STRING"},
                    "core_material": {"type": "STRING"},
                    "hashtags": {"type": "ARRAY", "items": {"type": "STRING"}}
                },
                "required": ["raw_korean_translation", "detected_brand", "kakao_text", "band_text", "insta_text", "core_material", "hashtags"]
            }}
        )
        if res and res.text:
            import json
            try:
                out_data = json.loads(res.text)
                kakao_text = out_data.get("kakao_text", "")
                band_text = out_data.get("band_text", "")
                insta_text = out_data.get("insta_text", "")
                core_material = out_data.get("core_material", "")
                hashtags = out_data.get("hashtags", [])
            except Exception:
                kakao_text = ""
                band_text = ""
                insta_text = ""
                core_material = ""
                hashtags = []

            from backend.pricing_logic import parse_gemini_translation_common, get_vendor_code, extract_brand_from_text
            d_brand = extract_brand_from_text(req.raw_text, out_data.get("detected_brand", ""))
            final_text, title, sale_price, product_code = parse_gemini_translation_common(kakao_text, req.prefix, d_brand, req.vendor_name)

            if req.vendor_name:
                vendor_code_str = get_vendor_code(req.vendor_name)
                vendor_highlight = f"✔ 업체코드: {vendor_code_str}\n"
                if "ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ" in final_text:
                    final_text = final_text.replace("ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ", f"ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ\n{vendor_highlight}", 1)
                else:
                    final_text = f"{title}\n{vendor_highlight}{final_text}"

            # if core_material:
            #     material_highlight = f"✨ 소재 포인트: {core_material}\nㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ\n"
            #     if "ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ" in final_text:
            #         final_text = final_text.replace("ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ", f"ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ\n{material_highlight}", 1)
            #     else:
            #         final_text = f"{title}\n{material_highlight}{final_text}"

            from backend.database import set_cached_translation
            if use_translation_cache:
                image_key = req.image_path if hasattr(req, 'image_path') and req.image_path else ""
                set_cached_translation(req.raw_text, json.dumps(out_data, ensure_ascii=False), final_category, image_key)

            return {
                "status": "success",
                "translated_text": final_text,
                "parsed_title": title,
                "parsed_sale_price": sale_price,
                "parsed_product_code": product_code,
                "band_text": band_text,
                "insta_text": insta_text,
                "hashtags": hashtags,
                "is_cached": False
            }
        return {"status": "error", "message": "응답 텍스트가 비어있습니다."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ─── 일괄 재번역 API ────────────────────────────────────────────────────
class RetranslateAllRequest(BaseModel):
    api_key: str = ""
    custom_prompt: str
    category: str = "남성의류"
    prefix: str = "AUTO"
    naver_fx: float = 195.0
    indices: list[int] = []  # 빈 리스트면 전체, 아니면 해당 인덱스들만 재번역
    use_critic: bool = False
    critic_prompt: str = ""

@app.post("/api/retranslate_all")
def retranslate_all(req: RetranslateAllRequest, background_tasks: BackgroundTasks):
    """이미 수집된 상품 리스트 전체(또는 선택분)에 대해 AI 재번역을 일괄 실행한다."""
    engine = get_engine()

    if req.naver_fx:
        real_fx = req.naver_fx
    else:
        real_fx = 200.0 # 기본값

    engine.add_log(f"💱 재번역 시작: 프론트엔드 환경설정 환율 적용 완료 ({real_fx}원)", "INFO", False)

    api_key = _get_gemini_key(req.api_key)
    if not api_key:
        return {"status": "error", "message": "Gemini API 키가 입력되지 않았습니다."}
    if len(engine.crawled_products) == 0:
        return {"status": "error", "message": "재번역할 상품이 없습니다."}

    # 이미 재번역 진행 중이면 중복 실행 방지
    if getattr(engine, '_retranslate_running', False):
        return {"status": "error", "message": "이미 재번역이 진행 중입니다."}

    # 대상 인덱스 결정
    target_indices = req.indices if req.indices else list(range(len(engine.crawled_products)))
    # original_chinese가 있는 것만 필터
    valid_indices = [i for i in target_indices if 0 <= i < len(engine.crawled_products) and engine.crawled_products[i].get('original_chinese')]

    if not valid_indices:
        return {"status": "error", "message": "재번역 가능한 상품(중국어 원문 보유)이 없습니다."}

    # 기존 하드코딩된 레거시 프롬프트가 UI에서 넘어오면 무시 처리 (카테고리별 템플릿 강제 사용)
    clean_custom_prompt = req.custom_prompt
    if clean_custom_prompt:
        legacy_keywords = ["업데이트 프로젝트 지침", "시스템 내장 지침이 자동으로 적용됩니다", "웨이신 모멘트", "설명은 2줄~4줄", "선택한 스타일 지침"]
        for kw in legacy_keywords:
            if kw in clean_custom_prompt:
                clean_custom_prompt = ""
                break

    engine.start_batch_retranslate(
        api_key=api_key,
        category=req.category,
        naver_fx=req.naver_fx,
        target_indices=valid_indices,
        custom_prompt=clean_custom_prompt,
        use_critic=req.use_critic,
        critic_prompt=req.critic_prompt
    )

    return {"status": "started", "total": len(valid_indices), "message": f"{len(valid_indices)}개 상품 재번역을 시작합니다."}

@app.get("/api/retranslate_progress")
def get_retranslate_progress():
    """재번역 진행 상태를 조회한다."""
    engine = get_engine()
    progress = getattr(engine, 'retranslate_progress', {"current": 0, "total": 0, "running": False, "failed": 0})
    return progress

@app.post("/api/retranslate_stop")
def stop_retranslate():
    """진행 중인 재번역을 중단한다."""
    engine = get_engine()
    engine._retranslate_stop = True
    return {"status": "stopping"}


# ─── 워치독 감시 에이전트 API ────────────────────────────────────────────────
@app.get("/api/watchdog/latest_report")
def get_watchdog_latest_report():
    """가장 최근 워치독 리포트를 반환합니다."""
    try:
        from backend.crawl_watchdog import get_latest_report
        report = get_latest_report()
        if not report:
            return {"status": "empty", "message": "아직 워치독 리포트가 없습니다. 크롤링을 실행해주세요."}
        return {"status": "ok", "report": report}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/watchdog/reports")
def get_watchdog_reports(limit: int = 20):
    """워치독 리포트 목록을 반환합니다."""
    try:
        from backend.crawl_watchdog import get_report_list
        reports = get_report_list(limit)
        return {"status": "ok", "reports": reports, "count": len(reports)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/watchdog/alerts")
def get_watchdog_alerts():
    """최신 리포트의 미처리 이상 알림 목록을 반환합니다."""
    try:
        from backend.crawl_watchdog import get_latest_report
        report = get_latest_report()
        if not report:
            return {"status": "empty", "alerts": []}
        alerts = report.get("alerts", [])
        report_only = [a for a in alerts if a.get("severity") == "report_only"]
        return {"status": "ok", "alerts": report_only, "count": len(report_only)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/image")
def serve_local_image(path: str):
    """크롤링 된 로컬 이미지를 웹 브라우저에서 볼 수 있도록 제공합니다."""
    import os
    allowed_roots = [
        os.path.realpath(os.path.join(_BASE_DIR, "TEMP_CRAWLED")),
        os.path.realpath(os.path.join(_BASE_DIR, "UPDATE")),
    ]
    candidate = path if os.path.isabs(path) else os.path.join(_BASE_DIR, path)
    candidate = os.path.realpath(candidate)

    def _inside_allowed_root(root: str) -> bool:
        if not os.path.isdir(root):
            return False
        try:
            return os.path.commonpath([candidate, root]) == root
        except ValueError:
            return False

    is_allowed = any(_inside_allowed_root(root) for root in allowed_roots)
    if not is_allowed:
        return JSONResponse({"error": "Image path is not allowed"}, status_code=403)
    if os.path.isfile(candidate):
        return FileResponse(candidate, headers={"Cache-Control": "public, max-age=86400, immutable"})
    return JSONResponse({"error": "Image not found"}, status_code=404)


# --- 크롤링 이미지 정적 서빙 (동시 로딩 지원) ---
_TEMP_CRAWLED_DIR = os.path.join(_BASE_DIR, 'TEMP_CRAWLED')
if os.path.isdir(_TEMP_CRAWLED_DIR):
    app.mount('/static_images', StaticFiles(directory=_TEMP_CRAWLED_DIR), name='crawled_images')

_UPDATE_DIR = os.path.join(_BASE_DIR, 'UPDATE')
if os.path.isdir(_UPDATE_DIR):
    app.mount('/static_update', StaticFiles(directory=_UPDATE_DIR), name='update_images')

# ─── React 정적파일 서빙 (빌드 dist/ 폴더가 있을 때만 마운트) ───────────────
if os.path.isdir(_DIST_DIR):
    # /assets/* → React가 생성하는 JS/CSS chunk 파일들
    _assets_dir = os.path.join(_DIST_DIR, "assets")
    if os.path.isdir(_assets_dir):
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

    # SPA fallback: /api/* 외 모든 경로 → index.html
    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        index_file = os.path.join(_DIST_DIR, "index.html")
        if os.path.isfile(index_file):
            return FileResponse(index_file)
        return {"error": "React build not found. Run: cd web-ui && npm run build"}

if __name__ == "__main__":
    uvicorn.run("api_server:app", host="127.0.0.1", port=8000, reload=True)

