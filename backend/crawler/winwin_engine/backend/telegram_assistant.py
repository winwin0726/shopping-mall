import threading
import time
import os
import re
import json
import telebot
from telebot import types

try:
    from backend.secret_store import get_secret, set_many
except ImportError:
    from secret_store import get_secret, set_many

try:
    from backend.database import get_system_settings, save_system_settings
except ImportError:
    from database import get_system_settings, save_system_settings

class TelegramAssistant:
    def __init__(self):
        self.bot = None
        self.thread = None
        self.running = False
        self.bot_token = None
        self.chat_id = None
        self.gemini_key = None
        self._lock = threading.Lock()
        self.user_states = {}  # FSM 상태 저장소 (chat_id: state_name)
        self.active_vendor_id = {}  # 현재 편집 중인 vendor_id 저장소 (chat_id: vendor_id)
        self._load_config()

    def _load_config(self):
        # system_settings.json에서 우선적으로 설정을 로드하여 하이브리드 연동 보장
        try:
            settings = get_system_settings()
            self.bot_token = settings.get("telegram_bot_token")
            self.chat_id = settings.get("telegram_admin_id")
        except Exception:
            pass

        # 폴백으로 secret_store 확인
        if not self.bot_token:
            self.bot_token = get_secret("telegram_bot_token")
        if not self.chat_id:
            self.chat_id = get_secret("telegram_chat_id")
        
        self.gemini_key = get_secret("gemini_api_key")

        # 토큰 정보가 있고 enabled 상태이면 기동
        try:
            settings = get_system_settings()
            if settings.get("telegram_bot_enabled", False) and self.bot_token and self.chat_id:
                self.start(self.bot_token, self.chat_id, self.gemini_key)
        except Exception:
            if self.bot_token and self.chat_id:
                self.start(self.bot_token, self.chat_id, self.gemini_key)

    def _save_config(self, token, chat_id, gemini_key=None):
        # 1. secret_store 백업 저장
        set_many({
            "telegram_bot_token": token,
            "telegram_chat_id": chat_id,
            "gemini_api_key": gemini_key,
        })
        # 2. system_settings.json 저장 (동시성 락 안전)
        try:
            settings = get_system_settings()
            settings["telegram_bot_token"] = token
            settings["telegram_admin_id"] = chat_id
            settings["telegram_bot_enabled"] = True
            save_system_settings(settings)
        except Exception:
            pass

    def start(self, token, chat_id, gemini_key=None):
        with self._lock:
            # 중복 봇 실행으로 인한 409 Conflict 오류를 원천 차단하기 위해
            # 가동 여부와 관계없이 기존 봇 인스턴스의 폴링을 선제 스톱하고 확실하게 회수 대기합니다.
            if self.bot:
                try:
                    self.bot.stop_polling()
                except Exception:
                    pass
                time.sleep(1.5)

            if self.running:
                if self.bot_token != token or self.chat_id != chat_id or self.gemini_key != gemini_key:
                    self.running = False
                    time.sleep(1.0)
                else:
                    # 토큰/ID가 동일하고 이미 running 중이면 중복 실행 생략
                    return

            if not token or not chat_id:
                return
                
            self.bot_token = token
            self.chat_id = chat_id
            if gemini_key:
                self.gemini_key = gemini_key
            self._save_config(token, chat_id, self.gemini_key)
            
            self.running = True
            self.bot = telebot.TeleBot(self.bot_token, threaded=False) # 스레드 세이프 안정 제어
            self._register_handlers()
            
            self.thread = threading.Thread(target=self._poll_loop, daemon=True, name="TelegramAssistantThread")
            self.thread.start()

    def stop(self):
        with self._lock:
            self.running = False
            if self.bot:
                try:
                    self.bot.stop_polling()
                except Exception:
                    pass

    def _send_message(self, text, reply_markup=None):
        if not self.bot or not self.chat_id:
            return
        try:
            self.bot.send_message(self.chat_id, text, parse_mode="HTML", reply_markup=reply_markup)
        except Exception:
            pass

    # --- 권한 데코레이터 패턴 ---
    def _is_admin(self, chat_id):
        return str(chat_id) == str(self.chat_id)

    def _register_handlers(self):
        # 텔레그램 핸들러 등록
        
        @self.bot.message_handler(commands=['start'])
        def cmd_start(message):
            if not self._is_admin(message.chat.id):
                self.bot.reply_to(message, "🔒 접근 권한이 없습니다.")
                return
            self.user_states[message.chat.id] = None # 대화 상태 리셋
            self._send_main_console(message.chat.id)

        @self.bot.callback_query_handler(func=lambda call: True)
        def handle_callback_query(call):
            if not self._is_admin(call.message.chat.id):
                self.bot.answer_callback_query(call.id, "🔒 접근 권한이 없습니다.")
                return
                
            data = call.data
            chat_id = call.message.chat.id
            self.bot.answer_callback_query(call.id) # 텔레그램 로딩 원 서클 즉시 종료

            from backend.crawler_engine import get_engine
            engine = get_engine()

            if data == "btn_status":
                self._send_status_update(chat_id)
            elif data == "btn_crawl_stop":
                self._stop_crawling(chat_id, engine)
            elif data == "btn_crawl_start":
                self._start_crawling_last_settings(chat_id, engine)
            elif data == "btn_settings":
                self._send_settings_console(chat_id)
            elif data == "btn_logs":
                self._send_recent_logs(chat_id, engine)
            elif data == "btn_photos":
                self._send_recent_photos(chat_id, engine)
            elif data == "btn_go_main":
                self.user_states[chat_id] = None
                self._send_main_console(chat_id)
            elif data == "btn_translate_toggle":
                self._toggle_ai_translation(chat_id)
            elif data == "btn_fx_change":
                self.user_states[chat_id] = "AWAITING_FX_RATE"
                self.bot.send_message(chat_id, "💱 <b>환율 변경 모드</b>\n변경하고 싶으신 환율 값을 소수점을 포함한 숫자로 입력해주세요.\n(예: <code>227.7</code> 또는 <code>228</code>)")
            elif data == "btn_vendor_rules":
                self.user_states[chat_id] = "AWAITING_VENDOR_SEARCH"
                self.bot.send_message(chat_id, "🏢 <b>업체 AI 규칙 관리</b>\n\n단가보정 및 규칙을 수정하고 싶은 <b>업체명(일부)</b>을 입력해주세요.\n(예: <code>A8</code> 또는 <code>돼지</code>)")
            elif data.startswith("vendor_detail_"):
                vendor_id = data.replace("vendor_detail_", "")
                self._send_vendor_detail(chat_id, vendor_id)
            elif data.startswith("btn_vendor_offset_"):
                vendor_id = data.replace("btn_vendor_offset_", "")
                self.user_states[chat_id] = "AWAITING_VENDOR_OFFSET"
                self.active_vendor_id[chat_id] = vendor_id
                self.bot.send_message(chat_id, "🔢 <b>신규 단가 보정값 입력</b>\n원화 보정값을 숫자로 입력해주세요. (예: <code>100</code>, <code>-50</code>, <code>0</code>)")

        @self.bot.message_handler(func=lambda message: True)
        def handle_text_message(message):
            if not self._is_admin(message.chat.id):
                return
            
            chat_id = message.chat.id
            state = self.user_states.get(chat_id)

            # 1. FSM 환율 변경 대기 상태 처리
            if state == "AWAITING_FX_RATE":
                text = message.text.strip()
                try:
                    new_fx = float(text)
                    if 100.0 <= new_fx <= 500.0:
                        # 1단계: system_settings.json의 환율 변경
                        try:
                            # 윈도우 cp949 한글 호환 보장을 위해 get/save settings 활용
                            settings = get_system_settings()
                            # transOptions의 naver_fx 변경
                            trans_opts = settings.get("transOptions", {})
                            trans_opts["naver_fx"] = new_fx
                            settings["transOptions"] = trans_opts
                            save_system_settings(settings)
                        except Exception:
                            pass

                        # 2단계: 크롤러 엔진의 메모리 캐시 동적 갱신
                        from backend.crawler_engine import get_engine
                        engine = get_engine()
                        if hasattr(engine, 'last_crawl_settings') and engine.last_crawl_settings:
                            try:
                                engine.last_crawl_settings["transOptions"]["naver_fx"] = new_fx
                            except Exception:
                                pass

                        self.user_states[chat_id] = None
                        self.bot.send_message(chat_id, f"✅ <b>환율이 {new_fx}원으로 동적 변경 완료되었습니다!</b>")
                        self._send_settings_console(chat_id)
                    else:
                        self.bot.send_message(chat_id, "⚠️ 환율 범위는 100원에서 500원 사이여야 합니다. 올바른 숫자를 다시 입력해주세요.")
                except ValueError:
                    self.bot.send_message(chat_id, "⚠️ 올바른 실수(숫자) 형식으로 입력해주세요. (예: 227.7)")
                return

            # 2. FSM 업체 검색 대기 상태 처리
            elif state == "AWAITING_VENDOR_SEARCH":
                query = message.text.strip().lower()
                if len(query) < 1:
                    self.bot.send_message(chat_id, "⚠️ 한 글자 이상 입력해주세요.")
                    return
                
                # weishang_vendors.json 로드
                vendors = []
                vendor_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "weishang_vendors.json")
                if os.path.exists(vendor_file):
                    try:
                        with open(vendor_file, "r", encoding="utf-8") as f:
                            vendors = json.load(f)
                    except Exception as e:
                        self.bot.send_message(chat_id, f"❌ 업체 리스트 로드 실패: {e}")
                        return
                
                matched = []
                for v in vendors:
                    v_name = v.get("name") or ""
                    if query in v_name.lower():
                        matched.append(v)
                        
                if not matched:
                    self.bot.send_message(chat_id, "🔍 검색된 업체가 없습니다. 다른 이름으로 검색해주세요.")
                    return
                
                # 최대 8개까지 인라인 버튼 생성
                markup = types.InlineKeyboardMarkup(row_width=1)
                for v in matched[:8]:
                    offset = v.get("price_offset", 0)
                    sign = "+" if offset >= 0 else ""
                    btn_text = f"🏢 {v['name']} (보정: {sign}{offset}원)"
                    markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"vendor_detail_{v['id']}"))
                
                if len(matched) > 8:
                    self.bot.send_message(chat_id, f"🔍 <b>총 {len(matched)}개 검색됨 (상위 8개 표시)</b>\n원하는 업체를 선택하세요:", reply_markup=markup, parse_mode="HTML")
                else:
                    self.bot.send_message(chat_id, "🔍 <b>검색 완료</b>\n원하는 업체를 선택하세요:", reply_markup=markup, parse_mode="HTML")
                return

            # 3. FSM 업체 보정값 입력 대기 상태 처리
            elif state == "AWAITING_VENDOR_OFFSET":
                text = message.text.strip()
                vendor_id = self.active_vendor_id.get(chat_id)
                if not vendor_id:
                    self.bot.send_message(chat_id, "⚠️ 세션이 만료되었습니다. 처음부터 다시 시도해주세요.")
                    self.user_states[chat_id] = None
                    return
                
                try:
                    new_offset = int(text)
                    success = self._update_vendor_offset_in_file(vendor_id, new_offset)
                    if success:
                        self.user_states[chat_id] = None
                        self.active_vendor_id[chat_id] = None
                        self.bot.send_message(chat_id, f"✅ <b>단가 보정값이 {new_offset}원으로 수정 및 동기화 완료되었습니다!</b>")
                        self._sync_vendor_offset_in_engine(vendor_id, new_offset)
                        self._send_vendor_detail(chat_id, vendor_id)
                    else:
                        self.bot.send_message(chat_id, "❌ 업체 설정 수정에 실패했습니다.")
                except ValueError:
                    self.bot.send_message(chat_id, "⚠️ 올바른 정수(숫자) 형식으로 입력해주세요. (예: 100 또는 -50)")
                return

            # 4. 일반 자연어 처리 폴백 (기존 3단계 AI 파싱 엔진 그대로 호환 연동)
            self._handle_natural_language(message.text, chat_id)

    # --- 메인 컨트롤 패널 UI 생성 ---
    def _send_main_console(self, chat_id):
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("▶️ 수집 시작", callback_data="btn_crawl_start"),
            types.InlineKeyboardButton("⏹️ 수집 중지", callback_data="btn_crawl_stop"),
            types.InlineKeyboardButton("📊 상태 조회", callback_data="btn_status"),
            types.InlineKeyboardButton("⚙️ 설정 관리", callback_data="btn_settings"),
            types.InlineKeyboardButton("📋 최근 로그", callback_data="btn_logs"),
            types.InlineKeyboardButton("🖼️ 최근 사진", callback_data="btn_photos")
        )
        msg = "🤖 <b>윈윈크롤러 3.3 원격 통합 콘솔</b>\n실행할 작업을 아래 버튼으로 선택하거나 대화하듯 명령어를 자유롭게 남겨주세요."
        self.bot.send_message(chat_id, msg, reply_markup=markup, parse_mode="HTML")

    # --- 환경설정 콘솔 UI 생성 ---
    def _send_settings_console(self, chat_id):
        fx_rate = 200.0
        ai_trans = "OFF"
        ai_budget = "economy"
        try:
            settings = get_system_settings()
            fx_rate = settings.get("transOptions", {}).get("naver_fx", 200.0)
            ai_trans = "ON" if settings.get("ai_translate_during_crawl", False) else "OFF"
            ai_budget = settings.get("ai_budget_mode", "economy")
        except Exception:
            pass

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("💱 환율 변경", callback_data="btn_fx_change"),
            types.InlineKeyboardButton("🔁 AI번역 토글", callback_data="btn_translate_toggle"),
            types.InlineKeyboardButton("🏢 업체 규칙 관리", callback_data="btn_vendor_rules")
        )
        markup.add(
            types.InlineKeyboardButton("🔙 메인으로 이동", callback_data="btn_go_main")
        )
        msg = (
            f"⚙️ <b>윈윈크롤러 환경설정 패널</b>\n\n"
            f"• 💱 <b>현재 환율</b>: <code>{fx_rate}원</code>\n"
            f"• 🔁 <b>실시간 AI 번역</b>: <code>{ai_trans}</code>\n"
            f"• 🧮 <b>AI 예산 모드</b>: <code>{ai_budget}</code>"
        )
        self.bot.send_message(chat_id, msg, reply_markup=markup, parse_mode="HTML")

    # --- AI 번역 토글 핸들러 ---
    def _toggle_ai_translation(self, chat_id):
        try:
            settings = get_system_settings()
            current_status = settings.get("ai_translate_during_crawl", False)
            settings["ai_translate_during_crawl"] = not current_status
            save_system_settings(settings)
            
            # 크롤러 엔진의 메모리 캐시 동적 갱신
            from backend.crawler_engine import get_engine
            engine = get_engine()
            if hasattr(engine, 'last_crawl_settings') and engine.last_crawl_settings:
                engine.last_crawl_settings["ai_translate_during_crawl"] = not current_status

            status_str = "활성화" if not current_status else "비활성화"
            self.bot.send_message(chat_id, f"✅ <b>실시간 AI 번역이 {status_str} 처리되었습니다!</b>")
            self._send_settings_console(chat_id)
        except Exception as e:
            self.bot.send_message(chat_id, f"❌ 토글 실패: {e}")

    # --- 크롤링 시작 핸들러 (이전 설정 그대로 복제) ---
    def _start_crawling_last_settings(self, chat_id, engine):
        is_running = False
        if engine.crawling_thread is not None:
            is_running = engine.crawling_thread.is_alive() if hasattr(engine.crawling_thread, 'is_alive') else engine.crawling_thread.isRunning()
        
        if is_running:
            self.bot.send_message(chat_id, "⚠️ 이미 크롤러 엔진이 구동 중입니다.")
            return

        if hasattr(engine, 'last_crawl_settings') and engine.last_crawl_settings:
            try:
                engine.start_crawling(engine.last_crawl_settings)
                p = engine.last_crawl_settings.get("platform", "웨이상(Szwego)")
                c = engine.last_crawl_settings.get("count", 0)
                self.bot.send_message(chat_id, f"🚀 <b>크롤러 수집 가동 시작!</b>\n- 플랫폼: {p}\n- 수집 갯수: {c}개\n(이전 기동 환경 세팅을 그대로 계승하여 수집합니다.)")
            except Exception as err:
                self.bot.send_message(chat_id, f"❌ 크롤러 시작 실패: {err}")
        else:
            self.bot.send_message(chat_id, "⚠️ 이전 크롤링 세팅값이 존재하지 않습니다. PC 웹 제어판에서 수집을 한 번 실행해 주십시오.")

    # --- 크롤링 중지 핸들러 ---
    def _stop_crawling(self, chat_id, engine):
        is_running = False
        if engine.crawling_thread is not None:
            is_running = engine.crawling_thread.is_alive() if hasattr(engine.crawling_thread, 'is_alive') else engine.crawling_thread.isRunning()
            
        if is_running:
            engine.stop_all()
            self.bot.send_message(chat_id, "🛑 <b>수집 강제 중단 명령 수신!</b>\n크롤러 안전 스레드 회수 작업을 개시합니다. 잠시만 대기해 주십시오...")
        else:
            self.bot.send_message(chat_id, "ℹ️ 현재 실행 중인 수집 스레드가 없습니다.")

    # --- 진행 상황 보고 핸들러 ---
    def _send_status_update(self, chat_id):
        from backend.crawler_engine import get_engine
        engine = get_engine()
        
        is_crawling = False
        if engine.crawling_thread is not None:
            is_crawling = engine.crawling_thread.is_alive() if hasattr(engine.crawling_thread, 'is_alive') else engine.crawling_thread.isRunning()

        # 큐매니저 상태 (포스팅 대기열)
        from backend.queue_manager import get_queue_manager
        qm = get_queue_manager()
        queue_status = qm.get_queue_status()
        active_jobs_count = queue_status.get("pending", 0) + queue_status.get("running", 0)
        
        msg = "📊 <b>실시간 시스템 상태 보고서</b>\n\n"
        if is_crawling:
            progress = engine.progress
            current = progress.get('val', 0)
            total = progress.get('max', 0)
            percent = int((current / total) * 100) if total > 0 else 0
            
            # 가시성 높은 게이지바 생성
            filled_blocks = int(percent / 10)
            gauge_bar = "█" * filled_blocks + "░" * (10 - filled_blocks)
            
            msg += f"🟢 <b>수집 상황</b>: [ {gauge_bar} ] {percent}%\n"
            msg += f"• 진행 상태: <code>{current} / {total}</code> 건 완료\n"
            if progress.get("current_item"):
                msg += f"• 현재 상점: <code>{progress['current_item']}</code>\n"
        else:
            msg += "⚪ <b>수집 상황</b>: 대기 중 (Idle)\n"
            
        msg += f"• 📤 <b>업로드 대기열</b>: <code>{active_jobs_count}건</code> 대기 중\n"
        msg += f"• 📦 <b>현재 캐싱 상품수</b>: <code>{len(engine.crawled_products)}건</code> 적재됨\n"
        
        self.bot.send_message(chat_id, msg, parse_mode="HTML")

    # --- 최근 로그 스트리밍 피드 ---
    def _send_recent_logs(self, chat_id, engine):
        if not hasattr(engine, 'logs') or not engine.logs:
            self.bot.send_message(chat_id, "📋 현재 기록된 수집 로그가 비어있습니다.")
            return

        # 마지막 10개 로그만 가져와 가공
        recent_entries = engine.logs[-12:]
        log_lines = []
        for log in recent_entries:
            # 텔레그램 HTML 특수문자 이스케이프
            txt = log["text"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            log_lines.append(f"• {txt}")

        msg = "📋 <b>최근 수집 로그 피드 (마지막 12줄)</b>\n\n" + "\n".join(log_lines)
        self.bot.send_message(chat_id, msg, parse_mode="HTML")

    # --- 최근 수집 사진 피드 스트리밍 ---
    def _send_recent_photos(self, chat_id, engine):
        if not engine.crawled_products:
            self.bot.send_message(chat_id, "🖼️ 최근 수집된 상품 정보가 존재하지 않습니다.")
            return

        # 가장 마지막 수집 상품 가져오기
        latest_prod = engine.crawled_products[-1]
        local_paths = latest_prod.get("local_image_paths", [])
        
        if not local_paths:
            self.bot.send_message(chat_id, "🖼️ 최근 상품 정보는 있으나 다운로드된 로컬 사진이 없습니다.")
            return

        self.bot.send_message(chat_id, f"📸 <b>최근 수집 완료 상품 사진 전송 개시</b>\n상품코드: <code>{latest_prod.get('product_code')}</code>\n상점명: {latest_prod.get('vendor_name')}")
        
        media_group = []
        count = 0
        for path in local_paths:
            if count >= 3: # 최대 3장만 발송하여 네트워크 버퍼 보장
                break
            if os.path.exists(path):
                try:
                    with open(path, 'rb') as f:
                        media_group.append(types.InputMediaPhoto(f.read()))
                    count += 1
                except Exception:
                    pass

        if media_group:
            try:
                self.bot.send_media_group(chat_id, media_group)
            except Exception as e:
                self.bot.send_message(chat_id, f"❌ 사진 앨범 전송 실패: {e}")
        else:
            self.bot.send_message(chat_id, "⚠️ 전송 가능한 올바른 형식의 사진 파일을 찾지 못했습니다.")

    # --- 자연어 명령어 인텐트 분석 (Gemini API 파싱 및 처리) ---
    def _handle_natural_language(self, text, chat_id):
        # 기존 AI 인텐트 분석 로직 그대로 유지
        ai_intent = self._parse_intent_with_ai(text)
        
        action = "unknown"
        target_platforms = []
        target_count = None
        target_vendor_names = []
        
        if ai_intent:
            action = ai_intent.get("action", "unknown")
            target_platforms = ai_intent.get("platforms", [])
            target_count = ai_intent.get("count")
            target_vendor_names = ai_intent.get("vendor_names", [])
        else:
            # fallback 매칭
            if "크롤" in text or "수집" in text or ("시작" in text and "올려" not in text and "업로드" not in text):
                action = "crawl"
                if "웨이상" in text: target_platforms.append("웨이상(Szwego)")
                elif "카스" in text or "카카오스토리" in text: target_platforms.append("카카오스토리")
                elif "밴드" in text or "네이버밴드" in text: target_platforms.append("네이버 밴드")
            elif "올려" in text or "업로드" in text or "포스팅" in text:
                action = "post"
                if "카스" in text or "카카오스토리" in text: target_platforms.append("카카오스토리")
                if "밴드" in text or "네이버밴드" in text: target_platforms.append("네이버 밴드")
            
            match = re.search(r'(\d+)개', text)
            if match:
                target_count = int(match.group(1))

        from backend.crawler_engine import get_engine
        engine = get_engine()

        if action in ["crawl", "crawl_and_post"]:
            target_vendor_urls = []
            final_vendor_names = []
            try:
                vendor_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "weishang_vendors.json")
                if os.path.exists(vendor_file):
                    with open(vendor_file, "r", encoding="utf-8") as f:
                        vendors = json.load(f)
                        if target_vendor_names:
                            for vn in target_vendor_names:
                                for v in vendors:
                                    if v.get("name") and vn.replace(" ", "").lower() in v["name"].replace(" ", "").lower():
                                        if v.get("url"):
                                            target_vendor_urls.append(v["url"])
                                            final_vendor_names.append(v["name"])
                                            break
                        else:
                            for v in vendors:
                                if v.get("name") and len(v["name"]) >= 2 and v["name"] in text:
                                    if v.get("url"):
                                        target_vendor_urls.append(v["url"])
                                        final_vendor_names.append(v["name"])
            except Exception:
                pass

            is_running = False
            if engine.crawling_thread is not None:
                is_running = engine.crawling_thread.is_alive() if hasattr(engine.crawling_thread, 'is_alive') else engine.crawling_thread.isRunning()
            
            if is_running:
                self.bot.send_message(chat_id, "⚠️ 이미 크롤링이 진행 중입니다.")
            else:
                if hasattr(engine, 'last_crawl_settings') and engine.last_crawl_settings:
                    settings = dict(engine.last_crawl_settings)
                    if target_platforms and "웨이상(Szwego)" in target_platforms:
                        settings["platform"] = "웨이상(Szwego)"
                    if target_count:
                        settings["count"] = target_count
                    if target_vendor_urls:
                        settings["vendorUrl"] = "\n".join(target_vendor_urls)
                        
                    try:
                        engine.start_crawling(settings)
                        msg = f"🚀 <b>크롤러 시작 지시 수신</b>\n- 플랫폼: {settings['platform']}\n"
                        if target_count: msg += f"- 갯수: {target_count}개\n"
                        if final_vendor_names: msg += f"- 업체: {', '.join(final_vendor_names)}\n"
                        msg += "(그 외 상세 환경 설정은 기존 PC 상태를 유지합니다.)"
                        self.bot.send_message(chat_id, msg)
                    except Exception as e:
                        self.bot.send_message(chat_id, f"❌ 크롤러 시작 실패: {str(e)}")
                else:
                    self.bot.send_message(chat_id, "⚠️ 봇에 이전 크롤링 환경설정이 기록되어 있지 않습니다. PC에서 '수집'을 먼저 실행해 주십시오.")

        elif action in ["post", "crawl_and_post"]:
            if hasattr(engine, 'last_post_settings') and engine.last_post_settings:
                settings = dict(engine.last_post_settings)
                if target_platforms:
                    post_plats = [p for p in target_platforms if p != "웨이상(Szwego)"]
                    if post_plats:
                        settings["platforms"] = post_plats
                    
                from backend.queue_manager import get_queue_manager
                qm = get_queue_manager()
                if qm.add_unique_job("POST", settings):
                    platforms_str = ", ".join(settings["platforms"])
                    self.bot.send_message(chat_id, f"📤 <b>업로드 시작 지시 수신</b>\n- 업로드 플랫폼: {platforms_str}\n(작업 대기열 추가 완료)")
                else:
                    self.bot.send_message(chat_id, "⚠️ 이미 업로드 작업이 대기열에 들어있거나 가동 중입니다.")
            else:
                self.bot.send_message(chat_id, "⚠️ 이전 업로드 세팅 정보가 존재하지 않습니다. PC 제어판에서 포스팅을 먼저 가동해 주십시오.")
        else:
            self.bot.send_message(chat_id, "🤔 어떤 작업을 원하시는지 인지하지 못했습니다.\n\n💡 <b>대화 명령어 예시:</b>\n- <i>'샤넬 15개 밴드에 수집해줘'</i>\n- <i>'지금 로그 보여줘'</i>\n- <i>'수집 멈춰'</i>")

    def _parse_intent_with_ai(self, text):
        if not self.gemini_key:
            return None
        try:
            from google import genai
            client = genai.Client(api_key=self.gemini_key.strip())
            prompt = f"""
사용자의 텔레그램 명령어를 분석해서 JSON 형식으로 의도를 추출해.
가능한 행동(action): "crawl"(크롤링/수집), "post"(업로드/포스팅), "status"(상태확인), "stop"(중지), "unknown"
만약 둘 다 해야하면 "crawl_and_post"로 설정해.
플랫폼(platforms) 배열 가능 값: "웨이상(Szwego)", "카카오스토리", "네이버 밴드"

분석할 명령어: "{text}"

출력 형식 (오직 JSON만, 마크다운 코드블록 금지):
{{
    "action": "crawl_and_post",
    "platforms": ["카카오스토리", "네이버 밴드"],
    "count": 15,
    "vendor_names": ["샤넬", "프라다"]
}}
"""
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            raw_text = response.text.strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.split("\n", 1)[1]
            if raw_text.endswith("```"):
                raw_text = raw_text.rsplit("\n", 1)[0]
            
            return json.loads(raw_text)
        except Exception:
            return None

    def _poll_loop(self):
        # 봇 가동 알림
        self._send_message("🤖 <b>안티그래비티 AI 비서 콘솔 부팅 완료!</b>\n아래의 메뉴 패널을 이용하시거나 대화하듯 편하게 명령해 주세요.", reply_markup=None)
        self._send_main_console(self.chat_id)
        
        while self.running:
            if not self.bot_token or not self.chat_id:
                time.sleep(3)
                continue
                
            try:
                # telebot의 내장 polling 호출로 대폭 안정화
                self.bot.polling(none_stop=True, timeout=20, long_polling_timeout=15)
            except Exception as e:
                # 예외 시 대기 후 재시도
                time.sleep(5)
            time.sleep(1)

    def _send_vendor_detail(self, chat_id, vendor_id):
        # weishang_vendors.json 로드하여 해당 vendor 정보 조회
        vendor_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "weishang_vendors.json")
        vendor = None
        if os.path.exists(vendor_file):
            try:
                with open(vendor_file, "r", encoding="utf-8") as f:
                    vendors = json.load(f)
                    for v in vendors:
                        if v.get("id") == vendor_id:
                            vendor = v
                            break
            except Exception:
                pass
        
        if not vendor:
            self.bot.send_message(chat_id, "❌ 해당 업체 정보를 찾을 수 없습니다.")
            return
            
        offset = vendor.get("price_offset", 0)
        sign = "+" if offset >= 0 else ""
        has_price = "있음" if vendor.get("has_price", True) else "없음"
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("💱 보정값 수정", callback_data=f"btn_vendor_offset_{vendor_id}"),
            types.InlineKeyboardButton("🔙 업체 검색", callback_data="btn_vendor_rules")
        )
        markup.add(
            types.InlineKeyboardButton("🔙 메인으로", callback_data="btn_go_main")
        )
        
        msg = (
            f"🏢 <b>업체 AI 규칙 상세</b>\n\n"
            f"• <b>업체명</b>: <code>{vendor.get('name')}</code>\n"
            f"• <b>카테고리</b>: <code>{vendor.get('category')}</code>\n"
            f"• <b>단가 표기</b>: <code>{has_price}</code>\n"
            f"• 💱 <b>현재 단가보정</b>: <code>{sign}{offset}원</code>\n"
            f"• ⚙️ <b>정규식</b>: <code>{vendor.get('price_regex') or '기본값'}</code>"
        )
        self.bot.send_message(chat_id, msg, reply_markup=markup, parse_mode="HTML")

    def _update_vendor_offset_in_file(self, vendor_id, new_offset):
        vendor_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "weishang_vendors.json")
        with self._lock:
            try:
                with open(vendor_file, "r", encoding="utf-8") as f:
                    vendors = json.load(f)
                
                updated = False
                for v in vendors:
                    if v.get("id") == vendor_id:
                        v["price_offset"] = new_offset
                        updated = True
                        break
                
                if updated:
                    with open(vendor_file, "w", encoding="utf-8") as f:
                        json.dump(vendors, f, ensure_ascii=False, indent=2)
                    return True
            except Exception as e:
                print(f"Error updating vendor offset in file: {e}")
        return False

    def _sync_vendor_offset_in_engine(self, vendor_id, new_offset):
        try:
            from backend.crawler_engine import get_engine
            engine = get_engine()
            # 1. 크롤러 엔진 메모리에 로드된 벤더 캐시가 있다면 업데이트
            if hasattr(engine, '_source_crawler') and engine._source_crawler:
                crawler = engine._source_crawler
                if hasattr(crawler, 'vendors') and crawler.vendors:
                    for v in crawler.vendors:
                        if v.get("id") == vendor_id:
                            v["price_offset"] = new_offset
                            break
        except Exception:
            pass

    def send_push_notification(self, text, photo_paths=None):
        if not self.bot or not self.chat_id:
            return
        
        try:
            # 1. 사진이 동봉된 경우 미디어 그룹 전송
            if photo_paths and len(photo_paths) > 0:
                media_group = []
                count = 0
                for path in photo_paths:
                    if count >= 3: # 네트워크 버퍼 상 상위 3개만 발송
                        break
                    if os.path.exists(path):
                        try:
                            with open(path, 'rb') as f:
                                # 첫 번째 이미지에 캡션을 리포트로 동봉
                                caption = text if count == 0 else None
                                media_group.append(types.InputMediaPhoto(f.read(), caption=caption, parse_mode="HTML"))
                            count += 1
                        except Exception:
                            pass
                
                if media_group:
                    self.bot.send_media_group(self.chat_id, media_group)
                    return
            
            # 2. 사진이 없거나 전송 실패 시 텍스트만 전송
            self.bot.send_message(self.chat_id, text, parse_mode="HTML")
        except Exception as e:
            print(f"Error sending telegram push notification: {e}")

_assistant_instance = TelegramAssistant()

def get_telegram_assistant():
    return _assistant_instance
