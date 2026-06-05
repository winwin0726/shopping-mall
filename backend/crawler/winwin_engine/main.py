import sys
import os

def main():
    # 1. 윈도우 환경 변수 및 플러그인 경로 사전 설정
    if sys.stdout and getattr(sys.stdout, 'encoding', None) != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    try:
        import PyQt5
        base = os.path.dirname(PyQt5.__file__)
        plugins = os.path.join(base, "Qt5", "plugins")
        platforms = os.path.join(plugins, "platforms")
        if os.path.exists(platforms):
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = platforms
    except Exception:
        pass

    # 2. 시작 전 환경 점검 로직 실행 (로딩창 띄우기)
    from startup_check import run_startup_check
    if not run_startup_check():
        print("시작 점검 실패 또는 사용자 취소로 인해 단말을 종료합니다.")
        sys.exit(0)

    # 3. 점검 통과 시 무거운 UI 모듈(winwin60.py) import 후 실행
    # (import를 지연시켜 시작 속도를 높이고 불필요한 메모리 낭비를 줄입니다)
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    import winwin60
    # winwin60.py의 메인 클래스 인스턴스화
    window = winwin60.KakaoCrawlerMainWindow()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
