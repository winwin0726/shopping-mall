import sys
import threading
import uvicorn
from PyQt5.QtCore import QCoreApplication
from api_server import app

def run_fastapi():
    """백그라운드 스레드에서 FastAPI 서버를 실행합니다."""
    uvicorn.run(app, host="127.0.0.1", port=8002)

def main():
    """
    Winwin Crawler 3.3 하이브리드 앱 메인 엔진
    QCoreApplication(UI 없는 Qt 이벤트 루프)를 실행하면서
    별도 스레드로 FastAPI 서버를 띄웁니다.
    추후 이 스크립트가 QWebEngineView를 띄우도록 확장됩니다.
    """
    
    # 1. FastAPI 서버 스레드 시작
    api_thread = threading.Thread(target=run_fastapi, daemon=True)
    api_thread.start()
    print("[시스템] FastAPI 백엔드 서버가 시작되었습니다 (포트 8002)")

    # 2. PyQt 코어 앱 시작 (워커 스레드의 시그널 처리를 위해 반드시 필요함)
    qt_app = QCoreApplication(sys.argv)
    
    print("[시스템] PyQt 백엔드 엔진이 준비되었습니다. 이 창은 백룸입니다.")
    
    # 여기서 이벤트 루프 차단(실행 유지)
    sys.exit(qt_app.exec_())

if __name__ == "__main__":
    main()
