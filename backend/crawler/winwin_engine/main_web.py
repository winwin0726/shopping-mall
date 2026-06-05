"""
main_web.py — 하이브리드 앱 진입점 (Phase 2 고도화 버전)
==============================================
무겁고 오래된 PyQt5 WebEngine을 완전히 버리고, 
윈도우 네이티브 Edge WebView2(PyWebView)를 사용하여
FastAPI(8001) 서버와 React UI를 눈 깜짝할 사이에 띄웁니다.

실행 방법:
    python main_web.py
"""

import sys
import os
import time
import threading
import webview
import urllib.request
import atexit
import ctypes

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# ── 글로벌 크래시 감시 로거 탑재 ──────────────────────────────────────────────
import traceback
import datetime

def init_crash_logger():
    """프로그램이 예상치 못한 에러로 종료될 때, 100% 로그 파일을 저장하도록 감시기를 등록합니다."""
    def save_crash_report(exctype, value, tb, thread_name="MainThread"):
        try:
            log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
            os.makedirs(log_dir, exist_ok=True)
            
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = os.path.join(log_dir, f"crash_{thread_name}_{ts}.log")
            
            error_msg = "".join(traceback.format_exception(exctype, value, tb))
            
            with open(log_file, "w", encoding="utf-8") as f:
                f.write("===================================================\n")
                f.write("🚨 WINWIN CRAWLER CRASH REPORT (비정상 종료 발생)\n")
                f.write("===================================================\n")
                f.write(f"발생 시각 : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"발생 스레드: {thread_name}\n")
                f.write(f"에러 타입 : {exctype.__name__}\n")
                f.write(f"에러 내용 : {value}\n")
                f.write("---------------------------------------------------\n")
                f.write("상세 Traceback:\n")
                f.write(error_msg)
                f.write("===================================================\n")
                
            print(f"[CrashLogger] 치명적 오류가 발생하여 로그를 파일에 백업했습니다: {log_file}")
        except Exception as e:
            try:
                print(f"[CrashLogger] 크래시 보고서 작성 실패: {e}")
            except:
                pass

    def main_excepthook(exctype, value, tb):
        save_crash_report(exctype, value, tb, "MainThread")
        sys.__excepthook__(exctype, value, tb)
        
    sys.excepthook = main_excepthook

    def thread_excepthook(args):
        thread_name = args.thread.name if args.thread else "UnknownThread"
        save_crash_report(args.exc_type, args.exc_value, args.exc_traceback, thread_name)
        sys.__excepthook__(args.exc_type, args.exc_value, args.exc_traceback)
        
    threading.excepthook = thread_excepthook

init_crash_logger()

try:
    # 윈도우 OS 배율(125%, 150% 등)을 무시하고 무조건 1픽셀=1픽셀로 강제 매칭
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

# ── 경로 설정 ─────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"))

BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# ── FastAPI 서버를 백그라운드 스레드로 실행 ───────────────────────────────────
SERVER_PORT = 8001
SERVER_URL = f"http://127.0.0.1:{SERVER_PORT}"

def _run_server():
    """별도 스레드에서 uvicorn FastAPI 서버를 구동합니다."""
    import uvicorn
    uvicorn.run(
        "api_server:app",
        host="127.0.0.1",
        port=SERVER_PORT,
        log_level="warning",   # 콘솔 출력 최소화
        access_log=False,
    )

def _wait_for_server(timeout: int = 15) -> bool:
    """FastAPI 서버가 응답할 때까지 최대 timeout초 대기합니다."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{SERVER_URL}/api/status", timeout=1)
            return True
        except Exception:
            time.sleep(0.3)
    return False

_cleanup_started = False

def _cleanup_automation_browsers():
    """앱 종료 시 크롤러가 띄운 Chrome/Selenium 세션을 같이 정리한다."""
    global _cleanup_started
    if _cleanup_started:
        return
    _cleanup_started = True
    try:
        from backend.crawler_engine import get_engine
        engine = get_engine()
        try:
            engine.stop_all()
        except Exception:
            pass
        try:
            engine.cleanup()
        except Exception as e:
            print(f"[main_web] ⚠️ 자동화 브라우저 정리 오류: {e}")

        # 드라이버 quit이 실패한 경우에도 자동화 프로필을 잡고 있는 Chrome만 보조 정리한다.
        for profile_name in os.listdir(BASE_DIR):
            if profile_name.startswith(("kakao_profile_", "band_profile_")):
                profile_dir = os.path.join(BASE_DIR, profile_name)
                try:
                    engine._kill_chrome_for_profile(profile_dir)
                except Exception:
                    pass
    except Exception as e:
        print(f"[main_web] ⚠️ 종료 정리 루틴 오류: {e}")

atexit.register(_cleanup_automation_browsers)

def kill_process_using_port(port):
    """지정한 포트를 점유 중인 외부 프로세스를 찾아 강제로 정리합니다."""
    import subprocess
    try:
        # netstat로 포트를 사용하는 PID 검색
        cmd = f'netstat -ano | findstr :{port}'
        output = subprocess.check_output(cmd, shell=True).decode('utf-8', errors='ignore')
        
        pids = set()
        for line in output.strip().split('\n'):
            if 'LISTENING' in line:
                parts = line.split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    pids.add(int(pid))
        
        current_pid = os.getpid()
        for pid in pids:
            if pid != current_pid:
                print(f"[PortCleaner] 포트 {port}를 점유 중인 좀비 프로세스(PID: {pid}) 강제 종료 시도...")
                subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"[PortCleaner] PID {pid} 정리 완료.")
    except Exception:
        pass

def main():
    print(f"[main_web] 🚀 차세대 크롤러 3.3 엔진 부팅 중...")

    # 8001 포트 잔여 좀비 프로세스 자동 청소
    kill_process_using_port(SERVER_PORT)

    # 1. FastAPI 백그라운드 엔진 가동
    server_thread = threading.Thread(target=_run_server, daemon=True)
    server_thread.start()
    
    # 2. 엔진 활성화 대기 (보통 1~2초 이내)
    if not _wait_for_server():
        print("❌ FastAPI 로컬 엔진 시작에 실패했습니다. 포트 중복을 확인하세요.")
        sys.exit(1)
        
    print(f"✅ 엔진 활성화! 렌더러 창을 생성합니다. ({SERVER_URL})")

    # 3. 네이티브 Edge WebView2 렌더러 실행
    cache_bust = int(time.time())
    
    class WebApi:
        def __init__(self):
            self._main_window = None
            self._log_window = None
            self._is_maximized = False
            
        def toggle_pin(self, enable):
            print(f"[WebAPI] 항상 위 고정 설정: {enable}")
            if self._main_window:
                self._main_window.on_top = bool(enable)
            if self._log_window:
                self._log_window.on_top = bool(enable)
            return True

        def minimize_window(self):
            if self._main_window:
                self._main_window.minimize()

        def toggle_maximize(self):
            if self._main_window:
                if self._is_maximized:
                    self._main_window.restore()
                    self._is_maximized = False
                else:
                    self._main_window.maximize()
                    self._is_maximized = True

        def close_window(self):
            _cleanup_automation_browsers()
            if self._main_window:
                self._main_window.destroy()
            if self._log_window:
                self._log_window.destroy()
            sys.exit(0)
            
        def resize_window(self, width, height):
            if self._main_window:
                self._main_window.resize(int(width), int(height))

    api = WebApi()
    
    # ── DPI 배율을 고려한 화면 정중앙 배치 계산 ───────────────────
    _user32 = ctypes.windll.user32
    try:
        # 윈도우 시스템 DPI 배율 구하기 (기본 96 DPI = 1.0배율)
        _dpi = _user32.GetDpiForSystem()
        _scale = _dpi / 96.0
    except Exception:
        _scale = 1.0

    # 물리 해상도를 DPI 배율로 나누어 실제 논리 해상도로 보정합니다.
    _screen_w = int(_user32.GetSystemMetrics(0) / _scale)
    _screen_h = int(_user32.GetSystemMetrics(1) / _scale)
    
    # 프레임리스(frameless=True)이므로 보이지 않는 OS 윈도우 테두리가 사라집니다. 따라서 실제 브라우저 렌더링 영역 크기인 1450x950을 보정 없이 그대로 할당합니다.
    _main_w, _main_h = 1450, 950
    _log_w, _log_h = 450, 950
    
    # 메인 제어판 창이 모니터 화면의 정확한 가로/세로 정중앙에 오도록 좌표를 설정합니다.
    _center_x = max(0, (_screen_w - _main_w) // 2)
    _center_y = max(0, (_screen_h - _main_h) // 2)

    main_window = webview.create_window(
        "Winwin 크롤러 3.3 (메인 제어판)",
        f"{SERVER_URL}?_t={cache_bust}",
        width=_main_w,
        height=_main_h,
        resizable=True,
        frameless=True,
        x=_center_x,
        y=_center_y,
        js_api=api
    )
    
    log_window = webview.create_window(
        "실시간 콘솔 로그 (보조창)",
        f"{SERVER_URL}/log_only?_t={cache_bust}",
        width=_log_w,
        height=_log_h,
        x=_center_x + _main_w - 14,
        y=_center_y,
    )
    
    api._main_window = main_window
    api._log_window = log_window
    
    def start_magnetic_dock_loop():
        # 윈도우 OS 수준에서 메인 창을 직접 추적하여 60FPS로 자석 도킹하는 백그라운드 구동기
        import ctypes
        from ctypes import wintypes
        import threading
        
        def _loop():
            user32 = ctypes.windll.user32
            hwnd_main = 0
            hwnd_log = 0
            
            # 두 윈도우의 HWND(핸들)를 찾을 때까지 대기
            for _ in range(50):
                if not hwnd_main:
                    hwnd_main = user32.FindWindowW(None, "Winwin 크롤러 3.3 (메인 제어판)")
                if not hwnd_log:
                    hwnd_log = user32.FindWindowW(None, "실시간 콘솔 로그 (보조창)")
                if hwnd_main and hwnd_log:
                    break
                time.sleep(0.1)
                
            if not hwnd_main or not hwnd_log:
                return

            rect_main = wintypes.RECT()
            rect_log = wintypes.RECT()
            
            user32.GetWindowRect(hwnd_main, ctypes.byref(rect_main))
            last_mx = rect_main.left
            last_my = rect_main.top
            last_mw = rect_main.right - rect_main.left
            last_mh = rect_main.bottom - rect_main.top

            user32.GetWindowRect(hwnd_log, ctypes.byref(rect_log))
            last_lx = rect_log.left
            last_ly = rect_log.top
            
            SNAP_DIST = 40
            OFFSET_X = -14
            LBUTTON = 0x01
            
            was_main_minimized = False
            was_log_minimized = False
            SW_MINIMIZE = 6
            SW_RESTORE = 9
            SW_SHOWNA = 8

            while True:
                time.sleep(0.015) # ~60fps 폴링
                if not user32.IsWindow(hwnd_main) or not user32.IsWindow(hwnd_log):
                    break
                    
                is_main_minimized = (user32.IsIconic(hwnd_main) != 0)
                is_log_minimized = (user32.IsIconic(hwnd_log) != 0)
                
                if is_main_minimized != was_main_minimized:
                    if is_main_minimized:
                        user32.ShowWindow(hwnd_log, SW_MINIMIZE)
                        is_log_minimized = True
                    else:
                        user32.ShowWindow(hwnd_log, SW_RESTORE)
                        is_log_minimized = False
                elif is_log_minimized != was_log_minimized:
                    if is_log_minimized:
                        user32.ShowWindow(hwnd_main, SW_MINIMIZE)
                        is_main_minimized = True
                    else:
                        user32.ShowWindow(hwnd_main, SW_RESTORE)
                        is_main_minimized = False
                        
                was_main_minimized = is_main_minimized
                was_log_minimized = is_log_minimized
                
                # 최소화 상태일 경우 도킹 위치 계산 건너뛰기 (가장자리 음수 좌표 방지)
                if is_main_minimized or is_log_minimized:
                    time.sleep(0.1)
                    continue
                    
                user32.GetWindowRect(hwnd_main, ctypes.byref(rect_main))
                mx, my = rect_main.left, rect_main.top
                mw = rect_main.right - rect_main.left
                mh = rect_main.bottom - rect_main.top
                
                user32.GetWindowRect(hwnd_log, ctypes.byref(rect_log))
                lx, ly = rect_log.left, rect_log.top
                lw = rect_log.right - rect_log.left
                
                main_moved = (mx != last_mx or my != last_my or mw != last_mw or mh != last_mh)
                log_moved = (lx != last_lx or ly != last_ly)
                
                # 이상적인 도킹 목표 지점 계산
                target_lx = mx + mw + OFFSET_X
                target_ly = my
                
                # 마우스 왼쪽 버튼 클릭 상태 확인
                # 0x8000 플래그가 켜져 있으면 현재 눌려있는 상태
                is_mouse_down = (user32.GetAsyncKeyState(LBUTTON) & 0x8000) != 0
                
                # 이전 프레임 기준의 이상적인 도킹 목표 지점 (이걸 기준으로 붙어있었는지 판단해야 고속 이동 시에도 안 떨어짐)
                old_target_lx = last_mx + last_mw + OFFSET_X
                old_target_ly = last_my
                
                if main_moved:
                    # 메인 창이 움직일 때, "보조창이 직전 프레임에 도킹된 상태였나?" 검사
                    was_snapped = abs(last_lx - old_target_lx) < 15 and abs(last_ly - old_target_ly) < 15
                    if was_snapped:
                        user32.SetWindowPos(hwnd_log, 0, target_lx, target_ly, lw, mh, 0x0014)
                        lx, ly = target_lx, target_ly
                        
                elif log_moved:
                    # 유저가 보조창을 개별적으로 옮겼을 때
                    # 마우스에서 손을 뗐고 + 스냅 반경(SNAP_DIST) 안에 들어왔다면 자석처럼 착!
                    if not is_mouse_down:
                        if abs(lx - target_lx) < SNAP_DIST and abs(ly - target_ly) < SNAP_DIST:
                            user32.SetWindowPos(hwnd_log, 0, target_lx, target_ly, lw, mh, 0x0014)
                            lx, ly = target_lx, target_ly
                
                last_mx, last_my, last_mw, last_mh = mx, my, mw, mh
                last_lx, last_ly = lx, ly

        threading.Thread(target=_loop, daemon=True).start()

    def on_main_closed():
        _cleanup_automation_browsers()
        try: log_window.destroy()
        except: pass

    def on_log_closed():
        _cleanup_automation_browsers()
        try: main_window.destroy()
        except: pass
        try: sys.exit(0)
        except: pass

    main_window.events.closed += on_main_closed
    log_window.events.closed += on_log_closed
    start_magnetic_dock_loop()

    # private_mode=False는 로컬 스토리지 보존을 위해 중요합니다.
    # debug=True 시 브라우저에서 메뉴(F12) 등 디버깅이 편합니다.
    # 주의: debug=True 설정 시 DevTools 창이 자동으로 뜨는 불편함이 있어 False로 되돌립니다.
    try:
        webview.start(private_mode=False, debug=False)
    finally:
        _cleanup_automation_browsers()

if __name__ == "__main__":
    main()
