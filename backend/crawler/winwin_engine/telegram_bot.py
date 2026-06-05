import time
import requests
from PyQt5.QtCore import QThread, pyqtSignal

class TelegramBotThread(QThread):
    command_received = pyqtSignal(str)
    log_signal = pyqtSignal(str)

    def __init__(self, token, chat_id, parent=None):
        super().__init__(parent)
        self.token = token
        self.chat_id = chat_id
        self.running = False
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.last_update_id = None

    def run(self):
        # 토큰이나 chat_id가 없으면 모니터링 실행 안 함
        if not self.token or not self.chat_id:
            self.log_signal.emit("⚠️ 텔레그램 설정이 비어있어 봇 모니터링을 시작하지 못했습니다.")
            return

        self.running = True
        self.log_signal.emit("🤖 텔레그램 봇 수신 대기 시작...")
        
        while self.running:
            try:
                url = f"{self.api_url}/getUpdates"
                params = {"timeout": 3}  # 3초 주기로 즉각 반응 체크
                if self.last_update_id:
                    params["offset"] = self.last_update_id + 1
                
                resp = requests.get(url, params=params, timeout=10)
                data = resp.json()
                
                if data.get("ok") and data.get("result"):
                    for item in data["result"]:
                        update_id = item["update_id"]
                        self.last_update_id = update_id
                        
                        if "message" in item and "text" in item["message"]:
                            msg = item["message"]
                            sender_id = str(msg["chat"]["id"])
                            text = msg["text"].strip()
                            
                            # 등록된 사용자의 Chat ID와 일치할 때만 시그널 전송 (보안)
                            if sender_id == str(self.chat_id):
                                self.command_received.emit(text)
                            else:
                                self.log_signal.emit(f"⚠️ 권한 없는 사용자의 텔레그램 접근 시도 차단: (ID: {sender_id})")
            except Exception as e:
                # 타임아웃이나 일시적 네트워크 에러 등은 무시하고 계속 루프
                pass
            
            time.sleep(0.5)

    def stop(self):
        self.running = False
        self.wait()

    def send_message(self, text):
        """WinWin 메인 프로그램 측에서 사용자에게 알림을 보낼 때 쓰는 메서드"""
        if not self.token or not self.chat_id:
            return False
            
        try:
            url = f"{self.api_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML"
            }
            resp = requests.post(url, json=payload, timeout=5)
            return resp.json().get("ok", False)
        except Exception as e:
            self.log_signal.emit(f"❌ 텔레그램 메시지 발송 실패: {e}")
            return False
