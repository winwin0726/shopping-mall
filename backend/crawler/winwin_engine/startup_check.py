import sys
import os
import subprocess
import urllib.request
import json
import re
from PyQt5.QtWidgets import QApplication, QProgressDialog, QMessageBox, QDialog, QVBoxLayout, QLabel, QProgressBar
from PyQt5.QtCore import Qt, QThread, pyqtSignal

class StartupCheckThread(QThread):
    progress_signal = pyqtSignal(int, str)
    complete_signal = pyqtSignal(bool, str)

    def __init__(self):
        super().__init__()

    def get_installed_chrome_version(self):
        """윈도우 레지스트리를 통해 설치된 크롬 버전을 가져옵니다."""
        try:
            reg_keys = [
                r"HKCU\Software\Google\Chrome\BLBeacon",
                r"HKLM\Software\Google\Chrome\BLBeacon",
                r"HKLM\Software\WOW6432Node\Google\Chrome\BLBeacon",
            ]
            for key in reg_keys:
                try:
                    out = subprocess.check_output(
                        ["reg", "query", key, "/v", "version"],
                        stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="ignore"
                    )
                    m = re.search(r"version\s+REG_SZ\s+([0-9.]+)", out, re.IGNORECASE)
                    if m:
                        return m.group(1).strip()
                except:
                    pass
        except:
            pass
        return None

    def get_latest_chrome_version(self):
        """일반 사용자용 크롬의 최신 안정(Stable) 버전을 웹에서 확인합니다."""
        try:
            # Google Chrome Version History API
            url = "https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                versions = data.get("versions", [])
                if versions:
                    return versions[0]["version"]
            return None
        except Exception as e:
            return None

    def check_playwright_installed(self):
        """playwright가 로컬 환경에 캐시되어 있는지 체크합니다."""
        # 로컬 앱데이터 폴더에서 ms-playwright 폴더 확인
        pw_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "ms-playwright")
        if os.path.exists(pw_dir):
            # 내부 크로미움 바이너리가 있는지 얕게 검사 (폴더 수)
            subdirs = os.listdir(pw_dir)
            if len(subdirs) > 0:
                return True
        return False

    def run(self):
        # 1. 필수 폴더 점검
        self.progress_signal.emit(10, "기본 폴더 및 파일 점검 중...")
        required_dirs = ['UPDATE', 'TEMP_CRAWLED', 'profiles', 'temp_kakao_images', 'temp_data_images']
        for d in required_dirs:
            os.makedirs(d, exist_ok=True)
            
        if not os.path.exists('vendors.txt'):
            with open('vendors.txt', 'w', encoding='utf-8') as f:
                f.write("업체명미지정\n")

        self.sleep_short()

        # 2. 크롬 브라우저 점검
        self.progress_signal.emit(30, "Chrome 브라우저 버전 확인 중...")
        installed_ver = self.get_installed_chrome_version()
        
        if not installed_ver:
            self.complete_signal.emit(False, "NO_CHROME")
            return

        # 버전 비교 (메이저 버전만 비교해도 무방)
        latest_ver = self.get_latest_chrome_version()
        if latest_ver:
            try:
                inst_major = int(installed_ver.split('.')[0])
                lat_major = int(latest_ver.split('.')[0])
                
                if inst_major < lat_major:
                    self.complete_signal.emit(False, f"CHROME_UPDATE_NEEDED|{installed_ver}|{latest_ver}")
                    return
            except:
                pass

        self.sleep_short()

        # 3. Playwright 엔진(브라우저) 확보 점검
        self.progress_signal.emit(60, "크롤링 가속 엔진(Playwright) 확인 중...")
        if not self.check_playwright_installed():
            self.progress_signal.emit(70, "최초 실행입니다. 엔진을 다운로드합니다 (수 분 소요).")
            try:
                # pyinstaller로 패키징되더라도 파이썬 내장 subprocess를 사용해 다운로드 호출
                # CLI 명령어가 실행파일명이 다를 수 있으므로 python -m 커맨드를 사용
                subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"], 
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                self.complete_signal.emit(False, f"PW_ERROR|{str(e)}")
                return

        self.progress_signal.emit(100, "모든 점검 완료! 프로그램을 시작합니다.")
        self.sleep_short()
        self.complete_signal.emit(True, "OK")

    def sleep_short(self):
        self.msleep(500)

class StartupCheckDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.success = False

    def initUI(self):
        self.setWindowTitle("WinWin 크롤러 시작 점검")
        self.setFixedSize(400, 150)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        layout = QVBoxLayout()
        self.label = QLabel("시스템 환경을 점검하고 있습니다.\n잠시만 기다려주세요...")
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)
        
        self.pbar = QProgressBar(self)
        self.pbar.setValue(0)
        layout.addWidget(self.pbar)
        
        self.setLayout(layout)

        self.thread = StartupCheckThread()
        self.thread.progress_signal.connect(self.update_progress)
        self.thread.complete_signal.connect(self.on_complete)

    def start_check(self):
        self.thread.start()

    def update_progress(self, val, msg):
        self.pbar.setValue(val)
        self.label.setText(msg)

    def on_complete(self, is_ok, msg):
        if is_ok:
            self.success = True
            self.accept()
        else:
            if msg == "NO_CHROME":
                QMessageBox.critical(self, "Chrome 미설치", "이 프로그램은 Google Chrome 브라우저가 필요합니다.\n크롬을 먼저 설치한 뒤 실행해주세요.")
                import webbrowser
                webbrowser.open("https://www.google.com/chrome/")
            elif msg.startswith("CHROME_UPDATE_NEEDED"):
                parts = msg.split('|')
                inst = parts[1] if len(parts) > 1 else '?'
                lat = parts[2] if len(parts) > 2 else '?'
                
                reply = QMessageBox.question(
                    self, 'Chrome 업데이트 필요', 
                    f"현재 크롬 버전({inst})이 구형입니다.\n최신 안정화 버전({lat})으로 업데이트하시겠습니까?\n(예: 크롬을 열어 업데이트 안내 / 아니오: 그냥 시작)",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
                )
                
                if reply == QMessageBox.Yes:
                    import webbrowser
                    webbrowser.open("chrome://settings/help")
                    QMessageBox.information(self, "안내", "크롬 창이 열리면 업데이트를 완료하고 재시작한 뒤,\n다시 프로그램을 실행해주세요.")
                    self.reject()
                else:
                    self.success = True
                    self.accept()
            elif msg.startswith("PW_ERROR"):
                QMessageBox.critical(self, "설치 오류", f"필수 엔진을 다운로드하는 중 오류가 발생했습니다.\n{msg}\n네트워크 연결을 확인한 뒤 다시 시도해주세요.")
            
            if not self.success:
                self.reject()

def run_startup_check():
    # Application 인스턴스가 없을 경우에만 생성
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    dialog = StartupCheckDialog()
    dialog.show()
    dialog.start_check()
    
    app.exec_()
    return dialog.success

if __name__ == '__main__':
    if run_startup_check():
        print("모든 점검 통과. 메인 프로그램 실행 가능")
    else:
        print("점검 실패 또는 취소됨")
