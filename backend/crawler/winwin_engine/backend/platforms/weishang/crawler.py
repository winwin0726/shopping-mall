import os

import re

import datetime

import requests

import json

import base64

import time

from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup

from playwright.sync_api import sync_playwright

from pydantic import BaseModel, Field





class GeminiProductSchema(BaseModel):

    title: str = Field(description="[ 브랜드명 ] 추출된 한국어 제목")

    body: str = Field(description="판매 양식이 완벽하게 복제된 전체 텍스트 본문 (설명, 사이즈, 컬러 등 모두 포함)")





def sanitize_path_component(name: str) -> str:

    name = re.sub(r'["\'<>:\\/|?*]', "_", name)

    name = name.replace("\r", "").replace("\n", " ")

    return name.strip()





def get_korean_initial(text):

    import re

    CHOSUNG_LIST = ["g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s", "ss", "y", "j", "jj", "c", "k", "t", "p", "h"]

    result = ""

    for char in text:

        if re.match(r"[가-힣]", char):

            ch1 = (ord(char) - ord("가")) // 588

            result += CHOSUNG_LIST[ch1]

        elif re.match(r"[A-Za-z0-9]", char):

            result += char.lower()

    return result





def apply_forbidden_words(text: str) -> str:

    if not text: return text

    try:

        from backend.database import get_system_settings

        settings = get_system_settings()

        words = settings.get("forbidden_words", [])

        for w in words:

            if w and len(w.strip()) > 0:

                text = text.replace(w, "")

    except Exception:

        pass

    return text



class WeishangCrawler:



    def __init__(self, log_func=None, add_product_func=None, update_product_func=None, qr_callback=None, telemetry_func=None):
        self.stop_flag = False
        self.log_func = log_func if log_func else print
        self.add_product_func = add_product_func
        self.update_product_func = update_product_func
        self.qr_callback = qr_callback
        self.telemetry_func = telemetry_func
        self.auth_state_path = "auth_state.json"

        # [추가] Playwright 리소스 참조를 위한 인스턴스 변수 정의
        self.playwright_mgr = None
        self.browser = None
        self.context = None
        self.page = None
        self._img_pool = ThreadPoolExecutor(max_workers=6, thread_name_prefix="img_dl")

    def close_browser(self):
        """Playwright 브라우저 및 관련 리소스를 세포 단위로 안전하게 정리합니다."""
        try:
            if self.page:
                self.page.close()
        except Exception:
            pass
        finally:
            self.page = None

        try:
            if self.context:
                self.context.close()
        except Exception:
            pass
        finally:
            self.context = None

        try:
            if self.browser:
                self.browser.close()
        except Exception:
            pass
        finally:
            self.browser = None

        try:
            if self.playwright_mgr:
                self.playwright_mgr.stop()
        except Exception:
            pass
        finally:
            self.playwright_mgr = None
        self.add_log("🧹 Playwright 브라우저 및 자원 정리 완료", "INFO")



    def add_log(self, msg, level="INFO"):

        self.log_func(msg, level, False)



    def stop(self):

        self.stop_flag = True



    def _download_single_image(self, url, dest_path, min_size=5120):

        """단일 이미지 다운로드 및 해상도 체크. 로컬 파일 경로인 경우 바로 복사합니다. 성공 시 파일명 반환, 실패 시 None."""

        import os

        try:

            if not str(url).startswith("http"):

                import shutil

                if os.path.exists(url):

                    shutil.copy2(url, dest_path)

                    return os.path.basename(dest_path)

                return None



            r = requests.get(url, timeout=10, headers={

                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",

                "Referer": "https://www.szwego.com/"

            })

            if r.status_code == 200:

                if min_size > 0 and len(r.content) < min_size:

                    return None

                

                                # 설정 불러오기 (SQLite 동시성 스레드 락 방지를 위해 캐싱된 멤버 변수 사용)
                min_w = getattr(self, "min_image_width", 200)
                min_h = getattr(self, "min_image_height", 200)

                

                # 해상도 체크 (Pillow 사용)

                import io

                from PIL import Image

                try:

                    img = Image.open(io.BytesIO(r.content))

                    width, height = img.size

                    if width < min_w or height < min_h:

                        self.add_log(f"  ⚠️ 저해상도 이미지 스킵 ({width}x{height} < {min_w}x{min_h}): {url[-30:]}", "WARNING")

                        return None

                except Exception as e:

                    self.add_log(f"  ⚠️ 이미지 크기 확인 오류: {e}", "WARNING")

                

                with open(dest_path, "wb") as f:

                    f.write(r.content)

                return os.path.basename(dest_path)

            else:

                self.add_log(f"  ❌ 사진 다운로드 거부됨 ({r.status_code}): {url[-40:]}", "WARNING")

        except Exception as e:

            self.add_log(f"  ❌ 사진 다운로드 오류: {e}", "WARNING")

        return None



    def _download_images_parallel(self, img_urls, item_dir, prefix="_tmp_", min_size=5120):

        """이미지 URL 리스트를 ThreadPool로 병렬 다운로드. 파일명 리스트 반환."""

        if not img_urls:

            return []

        futures = {}

        for i, url in enumerate(img_urls):

            if self.stop_flag:

                break

            dest = os.path.join(item_dir, f"{prefix}{i+1}.jpg")

            fut = self._img_pool.submit(self._download_single_image, url, dest, min_size)

            futures[fut] = i

        # ?쒖꽌 ?좎?瑜장)꾪빐 ?몃뜳장)湲곕컲 寃곌낵 ?섏쭛

        results = [None] * len(img_urls)

        for fut in as_completed(futures):

            idx = futures[fut]

            try:

                results[idx] = fut.result(timeout=30)

            except Exception:

                pass

        return [r for r in results if r is not None]



    def _shutdown_pools(self):

        """ThreadPool 안전 종료"""

        try:

            self._img_pool.shutdown(wait=False, cancel_futures=True)

        except Exception:

            pass



    def _retry_goto(self, page, url, max_retries=3, timeout=60000, wait_until="domcontentloaded"):

        """페이지 접속 재시도 (Self-Healing). 성공 시 True, 실패 시 False."""

        for attempt in range(1, max_retries + 1):

            try:

                page.goto(url, timeout=timeout, wait_until=wait_until)

                return True

            except Exception as e:

                wait_sec = 2 ** attempt  # 吏장)諛깆삤장) 2, 4, 8珥?

                if attempt < max_retries:

                    self.add_log(f"  ⏳ [AI 재시도 {attempt}/{max_retries}] {e} - {wait_sec}초 후 재시도", "WARNING")

                    page.wait_for_timeout(wait_sec * 1000)

                else:

                    self.add_log(f"  ❌ [접속 실패] {max_retries}회 재시도 모두 실패: {e}", "ERROR")

        return False



    def _safe_ai_call(self, translator, contents, model='gemini-2.5-flash-lite', config=None, max_retries=2, timeout_hint=30):

        """AI API 호출 재시도 래퍼 (429/타임아웃/네트워크 오류 자동 복구)."""

        for attempt in range(1, max_retries + 1):

            try:

                kwargs = dict(model=model, contents=contents)

                if config:

                    kwargs['config'] = config

                result = translator.models.generate_content(**kwargs)

                return result

            except Exception as e:

                err_str = str(e).lower()

                is_rate_limit = '429' in err_str or 'rate' in err_str or 'quota' in err_str

                wait_sec = 30 if is_rate_limit else (2 ** attempt)

                if attempt < max_retries:

                    reason = "API 요청 제한(Rate Limit)" if is_rate_limit else "네트워크/시간초과"

                    self.add_log(f"  ⏳ [AI 재시도 {attempt}/{max_retries}] {e} - {wait_sec}초 후 재시도", "WARNING")

                    time.sleep(wait_sec)

                else:

                    self.add_log(f"  ❌ [AI 호출 실패] {max_retries}회 모두 실패: {e}", "ERROR")

        return None



    def run(self, settings: dict):
        # SQLite 동시성 스레드 락 충돌 방지를 위한 설정 최초 1회 캐싱
        try:
            from backend.database import get_system_settings
            sys_settings = get_system_settings()
            self.min_image_width = sys_settings.get("min_image_width", 200)
            self.min_image_height = sys_settings.get("min_image_height", 200)
            self.add_log(f"⚙️ [설정 캐싱 완료] 최소 해상도 필터링 기준: {self.min_image_width}x{self.min_image_height}", "INFO")
        except Exception as se:
            self.add_log(f"⚠️ 시스템 설정 로드 오류 (기본값 200x200 사용): {se}", "WARNING")
            self.min_image_width = 200
            self.min_image_height = 200

        import traceback

        import os

        vendor_url_raw = settings.get("vendorUrl", "")

        vendor_urls = [u.strip() for u in vendor_url_raw.split() if u.strip().startswith("http")]

        if not vendor_urls:

            self.add_log("⚠️ 웨이상(Szwego) 업체 URL이 입력되지 않았습니다.", "ERROR")

            return



        def _extract_vendor_id(url_or_id: str) -> str:

            try:

                import urllib.parse

                import re

                text = urllib.parse.unquote(str(url_or_id or ""))

                # Hash fragment (#/shop_detail/...) 포함 URL 지원

                m = re.search(r"[/#](?:shop_detail|theme_detail)[/#]([^/?#\s]+)", text)

                if m:

                    return m.group(1)

                # shop_detail 없이 직접 ID가 전달된 경우

                if text.startswith("_"):

                    return text.strip()

            except Exception as e:

                print(f"Exception in _extract_vendor_id: {e}")

            return ""



        def _normalize_vendor_url(url: str) -> str:

            text = str(url or "").strip()

            vid = _extract_vendor_id(text)

            if vid:

                return f"shop_detail/{vid}"

            return text.split("?")[0].rstrip("/")



        def _safe_int(value, default=0):

            try:

                return int(float(value))

            except Exception:

                return default



        def _has_any_keyword(text: str, keywords) -> bool:

            if not keywords:

                return False

            if isinstance(keywords, str):

                keywords = re.split(r"[,/\n|]+", keywords)

            return any(str(k).strip() and str(k).strip() in text for k in keywords)



        target_count = settings.get("count", 10)

        trans_options = settings.get("transOptions", {})



        translator = None

        if trans_options and trans_options.get("enable"):

            gemini_key = trans_options.get("api_key", "").strip()

            if gemini_key:

                try:

                    from google import genai

                    translator = genai.Client(api_key=gemini_key)

                except ImportError:

                    self.add_log("⚠️ 'google-genai' 모듈이 설치되지 않아 번역이 불가능합니다.", "WARNING")

                except Exception as e:

                    self.add_log(f"⚠️ Gemini 클라이언트 생성 실패: {e}", "WARNING")

            else:

                self.add_log("⚠️ Gemini API Key가 비어있습니다. 번역이 생략됩니다.", "WARNING")



        def _verify_same_product_visually(img_url_1, img_url_2):
            if not translator:
                return None

            try:
                import requests
                import os
                from google.genai import types
                
                def _get_image_bytes(url):
                    if not str(url).startswith("http"):
                        if os.path.exists(url):
                            with open(url, "rb") as f:
                                return f.read()
                        return None
                    try:
                        r = requests.get(url, timeout=5)
                        if r.status_code == 200:
                            return r.content
                    except: pass
                    return None

                img1_bytes = _get_image_bytes(img_url_1)
                img2_bytes = _get_image_bytes(img_url_2)
                
                if not img1_bytes or not img2_bytes:
                    return True

                # --- [고도화] 로컬 dHash 이미지 대조 가드 추가 ---
                def _calculate_dhash(img_bytes):
                    try:
                        from PIL import Image
                        import io
                        img = Image.open(io.BytesIO(img_bytes))
                        # 9x8 리사이즈 및 그레이스케일 변환
                        img = img.convert('L').resize((9, 8), Image.Resampling.LANCZOS)
                        pixels = list(img.getdata())
                        
                        difference = []
                        for row in range(8):
                            for col in range(8):
                                pixel_left = pixels[row * 9 + col]
                                pixel_right = pixels[row * 9 + col + 1]
                                difference.append(pixel_left > pixel_right)
                                
                        decimal_value = 0
                        hex_string = []
                        for index, value in enumerate(difference):
                            if value:
                                decimal_value += 2 ** (index % 8)
                            if (index % 8) == 7:
                                hex_string.append(hex(decimal_value)[2:].zfill(2))
                                decimal_value = 0
                        return "".join(hex_string)
                    except Exception as he:
                        self.add_log(f"  ⚠️ [로컬 해시 오류] {he}", "WARNING")
                        return None

                def _hamming_distance(hash1, hash2):
                    if not hash1 or not hash2 or len(hash1) != len(hash2):
                        return 99
                    val1 = int(hash1, 16)
                    val2 = int(hash2, 16)
                    return bin(val1 ^ val2).count('1')

                hash1 = _calculate_dhash(img1_bytes)
                hash2 = _calculate_dhash(img2_bytes)
                
                if hash1 and hash2:
                    dist = _hamming_distance(hash1, hash2)
                    self.add_log(f"  👁️ [로컬 해시 대조] 해밍 거리: {dist} (지문1: {hash1}, 지문2: {hash2})", "INFO")
                    
                    if dist <= 5:
                        self.add_log(f"  ✅ [로컬 판정] 완전히 동일한 상품 이미지 확정 (해밍 거리: {dist}) - AI 호출 생략", "INFO")
                        return True
                    elif dist >= 16:
                        self.add_log(f"  ❌ [로컬 판정] 서로 다른 상품 이미지 확정 (해밍 거리: {dist}) - AI 호출 생략", "INFO")
                        return False
                    # 6 ~ 15 사이일 경우에만 애매하므로 아래 비전 AI API로 최종 검증

                prompt = "두 이미지를 정밀 비교해줘. 이 두 사진은 '동일한 상품'의 각도/색상/모델착용 여부만 다른 사진이야? [판단 기준] 1. 옷의 기본 종류(형태)나 폼팩터(지퍼 유무, 넥라인 등)가 다르면 무조건 '아니오'. 2. 찍는 방향, 거리, 명암(빛)은 미세하게 달라도 괜찮아. 3. 핵심은 [같은 배경 느낌]에서 촬영되었으며, 옷의 [같은 모양, 같은 로고, 같은 패턴(무늬)]을 가졌는지야. 이 핵심 조건들이 일치하고 완전히 동일한 디자인의 상품이 확실할 때만 '예'라고만 대답해."

                

                model_chain = ['gemini-3.1-flash-lite', 'gemini-2.5-flash', 'gemini-1.5-flash-latest']

                

                import time

                for current_model in model_chain:

                    for attempt in range(1, 3): # 각 모델당 2번 시도

                        try:

                            ans = translator.models.generate_content(

                                model=current_model,

                                contents=[

                                    types.Part.from_bytes(data=img1_bytes, mime_type='image/jpeg'),

                                    types.Part.from_bytes(data=img2_bytes, mime_type='image/jpeg'),

                                    prompt

                                ]

                            )

                            txt = ans.text.strip().lower()

                            self.add_log(f"  👁️ [비전 AI 판독] 동일 상품 판별 결과: {txt} ({current_model})", "INFO")

                            if "아니오" in txt or "아니" in txt or "no" in txt or "다름" in txt or "다른" in txt:

                                return False

                            return True

                        except Exception as e:

                            err_str = str(e).lower()

                            is_not_found = '404' in err_str or 'not found' in err_str

                            is_overload = '429' in err_str or '503' in err_str or 'rate' in err_str or 'quota' in err_str or 'unavailable' in err_str

                            

                            if is_not_found:

                                self.add_log(f"  ⚠️ [비전 AI] '{current_model}' 미지원/접근불가. 다음 모델로 우회합니다.", "WARNING")

                                break # 바로 다음 모델로 넘어감

                            

                            if is_overload and attempt < 2:

                                self.add_log(f"  ⚠️ [비전 AI 과부하] {current_model} 에러. 5초 대기 후 재시도... ({attempt}/2)", "WARNING")

                                time.sleep(5)

                                continue

                            else:

                                self.add_log(f"  ⚠️ [비전 AI 실패] {current_model} 에러 발생: {e}. 다음 모델로 우회합니다.", "WARNING")

                                break # 시도 횟수 초과거나 다른 에러면 다음 모델로 넘어감

                

                self.add_log("  ❌ [비전 AI 최종 실패] 사용 가능한 모든 모델이 실패했습니다.", "ERROR")

                return None

            except Exception as outer_e:

                self.add_log(f"  ⚠️ [비전 AI 준비 에러] 이미지 다운로드/네트워크 실패: {outer_e}", "WARNING")

                return None



        dest_dir = "TEMP_CRAWLED/weishang_images"

        os.makedirs(dest_dir, exist_ok=True)



        try:
            self.playwright_mgr = sync_playwright().start()
            self.add_log("[1] 웨이상 크롬 엔진(Playwright)을 시작합니다.")
            has_auth = os.path.exists(self.auth_state_path)

            if True:
                import random as _rnd

                # 봇 감지 회피: 실제 브라우저에 가까운 User-Agent 풀 사용

                _UA_POOL = [

                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",

                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",

                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",

                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",

                ]

                _chosen_ua = _rnd.choice(_UA_POOL)

                # 자연스러운 화면 해상도 선택

                _viewports = [{"width": 1536, "height": 864}, {"width": 1440, "height": 900}, {"width": 1920, "height": 1080}]

                _vp = _rnd.choice(_viewports)

                self.add_log(f"[1-1] 🛡️ UA: {_chosen_ua[:60]}... | 해상도: {_vp['width']}x{_vp['height']}")



                is_headless = settings.get('headless', False)

                is_ghost = settings.get('ghost_mode', False)

                

                _launch_args = [

                    "--no-sandbox",

                    "--disable-blink-features=AutomationControlled",

                    "--disable-features=ProtocolHandlerRegistry,WindowManagement,LocalFonts",

                    "--disable-notifications",

                    "--disable-popup-blocking",

                    "--disable-dev-shm-usage",

                    "--lang=zh-CN",

                ]



                if is_headless or is_ghost:

                    # 헤드리스 대신 창 최소화 및 모니터 밖으로 강제 고정 (유령 창 효과)

                    _launch_args.extend([

                        "--window-size=500,800",

                        "--window-position=-32000,-32000"

                    ])

                    _vp = {"width": 500, "height": 800}

                else:

                    _launch_args.append(f"--window-size={_vp['width']},{_vp['height']}")



                self.browser = self.playwright_mgr.chromium.launch(
                    headless=False,
                    args=_launch_args
                )
                browser = self.browser



                _ctx_args = dict(

                    viewport=_vp,

                    user_agent=_chosen_ua,

                    locale="zh-CN",             # 중국 로케일

                    timezone_id="Asia/Shanghai",  # 중국 시간대

                    permissions=["clipboard-read", "clipboard-write", "notifications"],

                    extra_http_headers={

                        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",

                        "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',

                        "sec-ch-ua-platform": '"Windows"',

                    }

                )



                if has_auth:
                    self.add_log("[1-2] 기존에 저장된 웨이상 로그인(세션) 정보를 불러옵니다.")
                    self.context = self.browser.new_context(storage_state=self.auth_state_path, **_ctx_args)
                else:
                    self.add_log("[1-2] ⚠️ 저장된 웨이상 로그인 정보가 없습니다.")
                    self.context = self.browser.new_context(**_ctx_args)
                context = self.context
                self.page = self.context.new_page()
                page = self.page



                # Playwright 자동화 흔적 완화 + 팝업 차단

                page.add_init_script("""

                    // 1. webdriver 플래그 숨기기 (가장 기본적인 봇 감지 항목)

                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });



                    // 2. chrome 객체 위장 (headless 브라우저는 chrome 객체가 없음)

                    window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){}, app: {} };



                    // 3. plugins 위장 (봇은 보통 0개)

                    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });



                    // 4. languages 위장

                    Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });



                    // 5. permissions 위장 (자동화 감지 우회)

                    const originalQuery = window.navigator.permissions.query;

                    navigator.permissions.query = (params) => (

                        params.name === 'notifications'

                            ? Promise.resolve({ state: Notification.permission })

                            : originalQuery(params)

                    );



                    // 6. 팝업 차단

                    window.getScreenDetails = undefined;

                    navigator.registerProtocolHandler = function(){};

                    if(window.Notification) { Notification.requestPermission = async () => 'denied'; }

                    const originalOpen = window.open;

                    window.open = function(url, ...args) {

                        if(typeof url === 'string' && !url.startsWith('http')) return null;

                        return originalOpen(url, ...args);

                    };



                    // 7. API 패킷 낚아채기 (전체 상품 데이터)

                    window.feedApiData = {};

                    const originalFetch = window.fetch;

                    window.fetch = async function(...args) {

                        const res = await originalFetch.apply(this, args);

                        const clone = res.clone();

                        clone.json().then(data => {

                            if(data && data.result && data.result.goodsList) {

                                data.result.goodsList.forEach(g => {

                                    if(g.goods_id) {

                                        window.feedApiData[g.goods_id] = g;

                                        if(g.title) {

                                            const shortText = g.title.replace(/\s+/g, '').substring(0, 30);

                                            window.feedApiData[shortText] = g;

                                        }

                                    }

                                });

                            }

                        }).catch(e => {});

                        return res;

                    };

                    const XHR = XMLHttpRequest.prototype;

                    const send = XHR.send;

                    const open = XHR.open;

                    XHR.open = function(method, url) {

                        this._url = url;

                        return open.apply(this, arguments);

                    };

                    XHR.send = function() {

                        this.addEventListener('load', function() {

                            if(this.getResponseHeader('content-type') && this.getResponseHeader('content-type').includes('json')) {

                                try {

                                    const data = JSON.parse(this.responseText);

                                    if(data && data.result && data.result.goodsList) {

                                        data.result.goodsList.forEach(g => {

                                            if(g.goods_id) {

                                                window.feedApiData[g.goods_id] = g;

                                                if(g.title) {

                                                    const shortText = g.title.replace(/\s+/g, '').substring(0, 30);

                                                    window.feedApiData[shortText] = g;

                                                }

                                            }

                                        });

                                    }

                                } catch(e) {}

                            }

                        });

                        return send.apply(this, arguments);

                    };

                """)



                # ===== QR 濡쒓렇장)濡쒖쭅 =====

                LOGIN_URL = "https://www.szwego.com/static/index.html?t=1712852296766#"

                if not has_auth:

                    self.add_log(f"[2] 웨이상 로그인 전용 페이지로 접속합니다.")

                    try:

                        page.goto(LOGIN_URL, timeout=60000)

                    except Exception as e:

                        self.add_log(f"❌ 로그인 페이지 접속 실패: {e}", "ERROR")

                        return



                    self.add_log("❗ 브라우저 화면에서 QR 코드를 추출 중입니다...")

                    try:

                        page.wait_for_selector(".login-qrcode img", timeout=10000)

                        qr_element = page.locator(".login-qrcode")

                        qr_bytes = qr_element.screenshot()

                        qr_b64 = base64.b64encode(qr_bytes).decode('utf-8')



                        if self.qr_callback:

                            self.qr_callback(f"data:image/png;base64,{qr_b64}")



                        self.add_log("웹 화면(UI)에 띄워진 QR 코드를 스마트폰 위챗/미상앨범으로 스캔해주세요.", "INFO")

                        self.add_log("⏳ 스캔 완료를 대기합니다 (최대 3분)...", "INFO")



                        page.wait_for_url(lambda url: "pc_login" not in url, timeout=180000)

                        self.add_log("✅ QR 로그인 완료! 안정화를 위해 3초 대기합니다.")

                        page.wait_for_timeout(3000)

                        context.storage_state(path=self.auth_state_path)

                        self.add_log("웨이상 로그인 세션(auth_state.json)을 저장했습니다.")



                        if self.qr_callback:

                            self.qr_callback(None)



                    except Exception as e:

                        self.add_log(f"❌ 로그인 대기 시간 초과 또는 QR 코드 로딩 실패: {e}", "ERROR")

                        return

                else:

                    self.add_log("[2] 기존 로그인 정보를 사용합니다.")



                # ===== 업체 AI 프로파일 규칙 로드 =====

                ai_vendor_rules = {}

                ai_vendor_rules_by_id = {}

                try:

                    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

                    vendor_profile_path = os.path.join(project_root, "weishang_vendors.json")

                    with open(vendor_profile_path, "r", encoding="utf-8") as f:

                        for v in json.load(f):

                            if "url" in v:

                                ai_vendor_rules[_normalize_vendor_url(v["url"])] = v

                            vendor_id_for_rule = v.get("id") or _extract_vendor_id(v.get("url", ""))

                            if vendor_id_for_rule:

                                ai_vendor_rules_by_id[vendor_id_for_rule] = v

                    self.add_log(f"🧠 업체 AI 규칙 파일 로드 완료: {len(ai_vendor_rules_by_id)}개 ({vendor_profile_path})", "INFO")

                except Exception as e:

                    self.add_log(f"⚠️ 업체 AI 규칙 파일을 읽지 못했습니다: {e}", "WARNING")



                for url_idx, vendor_url in enumerate(vendor_urls, 1):

                    if self.stop_flag:

                        break



                    # 현재 업체에 매칭되는 AI 규칙 조회

                    self.add_log(f"[디버그] vendor_url={vendor_url}", "INFO")

                    vendor_lookup_key = _normalize_vendor_url(vendor_url)

                    vendor_lookup_id = _extract_vendor_id(vendor_url)

                    self.add_log(f"[디버그] extracted vid={vendor_lookup_id}", "INFO")

                    _match_by_url = ai_vendor_rules.get(vendor_lookup_key)

                    _match_by_id = ai_vendor_rules_by_id.get(vendor_lookup_id)

                    current_vendor_ai_rules = _match_by_url or _match_by_id or {}

                    self.add_log(f"[디버그] lookup_key={vendor_lookup_key}, lookup_id={vendor_lookup_id[-12:]}, url_match={'Y' if _match_by_url else 'N'}, id_match={'Y' if _match_by_id else 'N'}", "INFO")

                    if current_vendor_ai_rules:

                        self.add_log(

                            f"🧠 업체 AI 규칙 적용: {current_vendor_ai_rules.get('name') or vendor_lookup_id or vendor_lookup_key} "

                            f"| {current_vendor_ai_rules.get('category', '미분류')} | {current_vendor_ai_rules.get('posting_pattern', '패턴미상')}",

                            "INFO"

                        )

                    else:

                        self.add_log(f"ℹ️ 업체 AI 규칙 없음: {vendor_lookup_id or vendor_url}", "INFO")

                    current_vendor_skip_conditions = current_vendor_ai_rules.get("skip_conditions", [])

                    current_vendor_recommended_style = current_vendor_ai_rules.get("recommended_style", "")

                    current_vendor_bundle_logic = current_vendor_ai_rules.get("bundle_logic", "")

                    current_vendor_boundary_signals = current_vendor_ai_rules.get("boundary_signals", [])

                    current_vendor_avg_images = current_vendor_ai_rules.get("avg_images_per_product", 0)

                    current_vendor_profile_rules = current_vendor_ai_rules.get("profile_rules", "")

                    current_vendor_post_structure = current_vendor_ai_rules.get("post_structure", "")

                    current_vendor_grouping_rules = current_vendor_ai_rules.get("grouping_rules", "")

                    current_vendor_matching_rules = current_vendor_ai_rules.get("matching_rules", "")

                    current_vendor_pricing_pattern = current_vendor_ai_rules.get("pricing_pattern", "")

                    current_vendor_posting_pattern = current_vendor_ai_rules.get("posting_pattern", "")

                    is_split_posting_vendor = "분할" in str(current_vendor_posting_pattern)

                    is_single_posting_vendor = "단일" in str(current_vendor_posting_pattern)

                    vendor_expected_images = _safe_int(current_vendor_avg_images, 0)

                    vendor_image_soft_cap = max(12, min(40, int(vendor_expected_images * 2.2))) if vendor_expected_images else 30



                    # 봇 AI 분석 카테고리 (최우선 적용) 및 카테고리별 번역 양식 로드

                    current_vendor_ai_category = current_vendor_ai_rules.get("category", "")

                    try:

                        from category_templates import get_template_for_category

                    except ImportError:

                        def get_template_for_category(c): return ""



                    # ===== 대상 URL 접속 (Self-Healing: 자동 재시도 3회) =====

                    self.add_log(f"[3] ({url_idx}/{len(vendor_urls)}) 업체 앨범 진입 시도: {vendor_url}")

                    if not self._retry_goto(page, vendor_url):

                        self.add_log("❌ 업체 URL 접속 실패. 다음 업체로 건너뜁니다.", "ERROR")

                        continue  # 다음 업체 진행

                    self.add_log(f"[3-1] ✅ goto 완료. 현재 URL: {page.url}")



                    self.add_log("[3-2] 페이지 안정화 대기 (네트워크 및 DOM 로딩)...")

                    try:

                        page.wait_for_load_state("networkidle", timeout=30000)

                    except Exception:

                        pass



                    self.current_vendor_title = page.title()

                    self.add_log(f"[3-3] 현재 페이지 타이틀: {self.current_vendor_title}")



                    try:

                        page.wait_for_selector(".album-list, .goods-list, .goods-item, .album-item, div[class*='normalItemContent'], div[class*='item'], div[class*='goods'], .error-page", state="attached", timeout=5000)

                        self.add_log("[3-4] ✅ 페이지 주요 요소 로딩 완료")

                    except Exception as e:

                        self.add_log(f"[3-4] ⚠️ 주요 요소 대기 초과(진행): {e}", "WARNING")



                    # ====== 템플릿 전환 ======

                    self.add_log("[4] 대형 이미지/목록 뷰(多图) 전환 시도...")

                    try:

                        try:
                            page.wait_for_selector("i.icon-liebiao, i.icon-sanlie, i[class*='icon-list'], i[class*='icon-grid'], div[class*='highightFrame'], div[class*='tiqeg']", state="visible", timeout=3000)
                        except Exception:
                            page.wait_for_timeout(2000)

                        

                        # 1단계: 팝업 열기 (이미 열려있는지 확인 후, 안 열려있으면 그리드 아이콘 클릭)

                        popup_status = page.evaluate("""() => {

                            let checkEls = document.querySelectorAll("div, span, li, p");

                            for (let el of checkEls) {

                                if (el.innerText && el.innerText.trim() === "多图" && el.offsetWidth > 0) {

                                    return 'already_open';

                                }

                            }

                            

                            // 그리드 아이콘(뷰 전환 버튼) 찾기

                            // 보통 필터 아이콘(깔때기 모양) 왼쪽이나 우측 상단에 위치

                            let gridIcons = document.querySelectorAll("i.icon-liebiao, i.icon-sanlie, i[class*='icon-list'], i[class*='icon-grid'], div[class*='highightFrame'], div[class*='tiqeg']");

                            if (gridIcons.length > 0) {

                                gridIcons[0].click();

                                return 'opened';

                            }

                            

                            // 아이콘 클래스로 못 찾을 경우, 아이콘 영역을 우측 영역에서 탐색

                            let topBar = document.querySelector(".album-list, .goods-list")?.previousElementSibling;

                            if (topBar) {

                                let icons = topBar.querySelectorAll("i, svg, img");

                                if (icons.length > 0) {

                                    icons[0].click();

                                    return 'opened';

                                }

                            }

                            return 'not_found';

                        }""")

                        

                        if popup_status == 'opened':

                            self.add_log("  - 뷰 전환 팝업 열기 성공, 애니메이션 대기 중...")

                            try:
                                page.wait_for_selector("text=多图, text=大图", state="visible", timeout=1500)
                            except Exception:
                                page.wait_for_timeout(1000)

                            

                        # 2단계: "多图" 클릭 (목록뷰 4번째 옵션)

                        list_clicked = page.evaluate("""() => {

                            let els = document.querySelectorAll("div, span, li, p");

                            

                            // 1순위: "多图" 정확히 매칭 (사용자 요청)

                            for (let el of els) {

                                if (el.offsetWidth > 0 && el.offsetHeight > 0 && el.innerText) {

                                    if (el.innerText.trim() === "多图") {

                                        el.click();

                                        return true;

                                    }

                                }

                            }

                            

                            // 2순위: "大图" 매칭 (차선책)

                            for (let el of els) {

                                if (el.offsetWidth > 0 && el.offsetHeight > 0 && el.innerText) {

                                    let t = el.innerText.trim();

                                    if (t === "大图" || t.includes("大图模式")) {

                                        el.click();

                                        return true;

                                    }

                                }

                            }

                            

                            // 3순위: 이미지 src 매칭

                            let imgTarget = document.querySelector("img[src*='duotu.png'], img[src*='icon_list_template_duotu']");

                            if (imgTarget && imgTarget.offsetWidth > 0) {

                                let clickable = imgTarget.closest('div, li, a, button') || imgTarget;

                                clickable.click();

                                return true;

                            }

                            

                            return false;

                        }""")

                        

                        if list_clicked:

                            self.add_log("  ✅ 다중 이미지(多图)/대형 뷰 모드 활성화 완료")

                            try:
                                page.wait_for_selector("div[class*='normalItemContent'], div[class*='item'], div[class*='goods']", state="attached", timeout=2500)
                            except Exception:
                                page.wait_for_timeout(1500)

                        else:

                            self.add_log("  ⚠️ '多图' 전환 아이콘 못 찾음 (기본 뷰 유지)", "WARNING")

                    except Exception as e:

                        self.add_log(f"⚠️ 뷰 전환 오류 (무시): {e}", "WARNING")

                    self.add_log(f"🎉 ({url_idx}/{len(vendor_urls)}) 업체 수집을 본격적으로 시작합니다...", "INFO")

                    try:
                        page.wait_for_selector("div[class*='normalItemContent']", state="visible", timeout=2500)
                    except Exception:
                        page.wait_for_timeout(2000)



                    # ?꾩옱 HTML?먯꽌 ?꾩씠장)媛쒖닔 ?ъ쟾 ?뺤씤

                    html_check = page.content()

                    soup_check = BeautifulSoup(html_check, "html.parser")

                    items_check = soup_check.find_all('div', class_=lambda c: c and 'normalItemContent' in c)

                    self.add_log(f"[디버그] 현재 페이지에서 감지된 아이템 수: {len(items_check)}", "INFO")



                    processed_count = 0

                    seen_items = set()

                    no_new_scroll_count = 0  # 무한 루프 방어: 연속 N회 새 아이템 없으면 탈출

                    # ?뵕 ?ъ뒪장)洹몃９장)踰꾪띁: ?④? ?녿뒗 ?ъ뒪?낆쓽 ?대?吏/?띿뒪?몃? ?꾩떆 ?장)

                    # → ?ㅼ쓬장)?④? ?덈뒗 ?ъ뒪?낆씠 ?섏삤硫장)장)쒗뭹?쇰줈 ?⑹궛

                    _group_img_buf = []   # 이미지 URL 버퍼

                    _group_txt_buf = []   # 텍스트 버퍼

                    _GROUP_BUF_MAX = 4    # 버퍼 최대 사이즈



                    _pending_product = None  # {"img_urls": [...], "raw_text": "...", "has_price": bool, "has_code": match}

                    _qr_candidate_urls = set()  # QR 공유 카드 후보 URL 집합



                    # 카테고리 추측 함수

                    def _guess_category(name, raw=""):

                        """1순위: 업체명(한국어)키워드, 2순위: 본문 중국어 키워드"""

                        if not name and not raw: return ""

                        n = (name or "").replace(" ", "")

                        if any(k in n for k in ["신발", "구두", "스니커즈", "맥스", "부츠", "슈즈", "남신", "여신"]): return "신발"

                        if "가방" in n or ("백" in n and "백화점" not in n): return "가방"

                        if "지갑" in n: return "지갑"

                        if "시계" in n or "워치" in n: return "시계"

                        if "골프" in n: return "골프"

                        if "아동" in n or "키즈" in n: return "아동복"

                        if any(k in n for k in ["악세", "벨트", "스카프", "목걸이", "반지", "주얼리", "귀걸이"]): return "악세사리"

                        if any(k in n for k in ["여성복", "여원피스", "원피스"]): return "의류"

                        if any(k in n for k in ["남성복", "남원피스", "남성의류"]): return "의류"

                        if any(k in n for k in ["패딩", "코트", "무스너클", "바람막이"]): return "아우터"

                        if raw:

                            cn = raw

                            cn_lower = cn.lower()

                            if any(k in cn for k in ["包", "提包", "肩包", "挎包", "钱包", "拿包", "迷你包"]): return "가방"

                            if "woc" in cn_lower or "mini bag" in cn_lower or "flap bag" in cn_lower: return "가방"

                            if ("mini" in cn_lower) and any(k in cn for k in ["尺", "小号", "大号"]): return "가방"

                            if any(k in cn for k in ["鞋", "运动鞋", "休闲鞋", "高跟鞋", "乐福鞋", "老爹鞋"]): return "신발"

                            if any(k in cn for k in ["表", "手表", "机芯", "机械表"]): return "시계"

                            if any(k in cn for k in ["镜", "太阳镜", "墨镜", "项链", "戒指", "耳环"]): return "악세사리"

                        return ""



                    def _extract_price(text, v_name, v_cat, ai_rules):
                        if ai_rules.get("has_price") is False: return "0"
                        
                        def pre_clean_product_codes(raw_text: str) -> str:
                            clean_text = raw_text
                            clean_text = re.sub(
                                r'(?:货号|款号|编号|sku|搜索码|搜素码)\s*[:：-]?\s*[A-Za-z0-9_-]{5,15}',
                                '[PRODUCT_CODE]',
                                clean_text,
                                flags=re.IGNORECASE
                            )
                            clean_text = re.sub(
                                r'\b\d{7,}\b',
                                '[LONG_NUMBER]',
                                clean_text
                            )
                            return clean_text
                        
                        text = pre_clean_product_codes(text)
                        
                        _custom_price_regex = ai_rules.get("price_regex", "")
                        _price_decoder = ai_rules.get("price_decoder", "")
                        _price_offset = ai_rules.get("price_offset", 0)
                        
                        if _custom_price_regex:
                            _matches = list(re.finditer(_custom_price_regex, text, re.IGNORECASE))
                            for _m in _matches:
                                _str = next((g for g in _m.groups() if g and any(c.isdigit() for c in g)), _m.group(0)) if _m.groups() else _m.group(0)
                                _pn = re.findall(r'\d+', _str)
                                if _pn:
                                    val = int(_pn[0])
                                    if _price_offset: val += int(_price_offset)
                                    return str(val)
                            return "-"
                        
                        patterns = {
                            "emoji_symbol": r'(¥|￥|💰|💵|💸|💴|💲|🪙|🏷️|🛍️|元|块|价|现价|特价|活动价|折后价)[ \t]*[:：-]*[ \t]*([\d\.,]+)',
                            "alpha_code": r'(?:^|\s|[^A-Za-z0-9])([A-Za-z]{1,4})[-:_\t ]*(\d{3,4})(?:$|\s|[^A-Za-z0-9])',
                            "date_code": r'(?:^|\s|[^A-Za-z0-9])(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])(\d{3,4})(?:$|\s|[^A-Za-z0-9])',
                            "suffix_code": r'\b(\d{2,4})[ \t]*(?:元|块|起)\b',
                            "fallback_num": r'(?:^|\s|[^A-Za-z0-9])(\d{2,4})(?:$|\s|[^A-Za-z0-9])'
                        }
                        
                        candidates = []
                        
                        for ptype, pat in patterns.items():
                            for m in re.finditer(pat, text, re.IGNORECASE):
                                # 캡처 그룹이 있는 정규식이면 가격이 포함된 마지막 그룹을 추출 대상으로 지정
                                if m.groups():
                                    matched_str = m.groups()[-1] if m.groups()[-1] else m.group(0)
                                else:
                                    matched_str = m.group(0)
                                
                                nums = re.findall(r'\d+', matched_str)
                                if not nums: continue
                                val = int(nums[0])
                                
                                if _price_decoder == "sandwich" and len(str(val)) >= 3:
                                    try: val = int(str(val)[1:-1])
                                    except: pass
                                if _price_offset: val += int(_price_offset)
                                
                                cat_hint = v_cat or _guess_category("", text) or ""
                                min_val = 50 if all(x not in cat_hint for x in ["악세","잡화","반지","목걸이","귀걸이"]) else 30
                                if v_name and "돼지" in v_name: min_val = 10
                                
                                if not (min_val <= val <= 3000):
                                    continue
                                
                                score = 10
                                if ptype == "emoji_symbol":
                                    if any(x in matched_str for x in ["现价", "特价", "活动", "折后"]):
                                        score = 120
                                    else:
                                        score = 100
                                elif ptype == "alpha_code":
                                    score = 80
                                elif ptype == "suffix_code":
                                    score = 60
                                elif ptype == "date_code":
                                    score = 50
                                
                                c_str = text[max(0, m.start()-15):min(len(text), m.end()+15)].lower()
                                if re.search(r'(cm|mm|kg|size|사이즈|가슴|길이|기장|어깨|소매|둘레|반품|허리|신발|발볼|尺寸|尺码|厘米|规格)', c_str):
                                    if ptype == "fallback_num":
                                        score -= 200  # 기호 없는 일반 숫자는 엄격히 차단
                                    else:
                                        score -= 30   # 확실한 가격 코드들은 감점만 약하게 적용
                                
                                if re.search(r'\d+\s*g\b', c_str):
                                    if ptype == "fallback_num":
                                        score -= 200
                                    else:
                                        score -= 30
                                
                                if score > 0:
                                    candidates.append((val, score, m.start()))
                        
                        if candidates:
                            candidates.sort(key=lambda x: (x[1], x[2]), reverse=True)
                            return str(candidates[0][0])
                        
                        return "-"
                    rules_text = ""

                    try:

                        with open("양식적용 프로젝트규칙1.txt", "r", encoding="utf-8") as f:

                            rules_text = f.read()

                    except Exception:

                        rules_text = "기본 번역 포맷을 사용합니다."



                    _date_boundary_str = None

                    _stop_crawling_by_date = False



                    while not _stop_crawling_by_date and not self.stop_flag:

                        html = page.content()

                        soup = BeautifulSoup(html, "html.parser")

                        items = soup.find_all('div', class_=lambda c: c and ('normalItemContent' in c or 'w-1-3' in c))



                        found_new = False

                        for item in items:

                            if self.stop_flag or _stop_crawling_by_date: break

                            

                            _time_elem = item.find(class_=lambda c: c and 'time' in str(c).lower())

                            _raw_time = _time_elem.get_text(strip=True) if _time_elem else ""

                            if "前" in _raw_time or "今天" in _raw_time or "刚刚" in _raw_time:

                                _item_date = "오늘"

                            elif "昨天" in _raw_time:

                                _item_date = "어제"

                            elif "前天" in _raw_time:

                                _item_date = "그제"

                            else:

                                _item_date = _raw_time.split()[0] if _raw_time else "알수없음"



                            if _date_boundary_str is None:

                                _date_boundary_str = _item_date



                            if processed_count >= target_count:

                                self.add_log(f"  🛑 목표 수량({target_count}개) 도달. 크롤링 종료.", "INFO")

                                _stop_crawling_by_date = True

                                break

                            # ----- [중복 수집 차단 필터] -----
                            import re
                            goods_id = None
                            shop_id = None
                            
                            html_str = str(item)
                            m_goods = re.search(r'goods_id(?:&quot;|["\':\s=;])+([a-zA-Z0-9_-]{8,})', html_str)
                            if m_goods: goods_id = m_goods.group(1)
                            
                            m_shop = re.search(r'shop_id(?:&quot;|["\':\s=;])+([a-zA-Z0-9_-]+)', html_str)
                            if m_shop: shop_id = m_shop.group(1)

                            data_info_str = item.get('data-search-bury-info')
                            if not data_info_str:
                                child = item.find(attrs={"data-search-bury-info": True})
                                if child:
                                    data_info_str = child.get('data-search-bury-info')
                            
                            if data_info_str:
                                try:
                                    data_info = json.loads(data_info_str.replace('&quot;', '"'))
                                    goods_id = goods_id or data_info.get('goods_id')
                                    shop_id = shop_id or data_info.get('shop_id')
                                except: pass

                            if not goods_id or not shop_id:
                                for a in item.find_all('a', href=True):
                                    href = a.get('href', '')
                                    if 'theme_detail' in href:
                                        parts = href.split('/')
                                        if len(parts) >= 3:
                                            goods_id = goods_id or parts[-1].split('?')[0]
                                            shop_id = shop_id or parts[-2]
                                            break
                            
                            # 중복 여부 판정 키 생성 (goods_id 우선, 없으면 텍스트 해시)
                            dup_key = goods_id if goods_id else None
                            if not dup_key:
                                texts_temp = item.find_all(string=True)
                                raw_text_temp = "".join([t.strip() for t in texts_temp if t.strip()]).strip()
                                raw_text_temp = re.sub(r'(?:🆕|尺寸图|高品质)?\s*下载\s*编辑\s*转发', '', raw_text_temp)
                                raw_text_temp = re.sub(r'下载\s*编辑\s*转发', '', raw_text_temp)
                                raw_text_temp = re.sub(r'download\s*Edit\s*Forwarding', '', raw_text_temp, flags=re.IGNORECASE)
                                raw_text_temp = re.sub(r'转发\s*编辑\s*下载', '', raw_text_temp).strip()
                                dup_key = raw_text_temp[:80] if raw_text_temp else None

                            if dup_key:
                                if dup_key in seen_items:
                                    # 이미 수집했거나 처리 중인 아이템이면 루프를 건너뜀 (크롤링 속도 대폭 향상 및 중복 방지)
                                    continue
                                else:
                                    seen_items.add(dup_key)
                                    found_new = True  # 완전히 새로운 아이템 객체가 앨범 목록상에 등장했으므로 휠 스크롤 감시 통과 처리 (조기 종료 예방)



                            is_grid = 'w-1-3' in item.get('class', [])



                            texts = item.find_all(string=True)

                            raw_text = " ".join([t.strip() for t in texts if t.strip()])

                            # 불필요한 웨이상 UI 버튼 텍스트 강력 제거

                            import re

                            raw_text = re.sub(r'(?:🆕|尺寸图|高品质)?\s*下载\s*编辑\s*转发', '', raw_text)

                            raw_text = re.sub(r'下载\s*编辑\s*转发', '', raw_text)

                            raw_text = re.sub(r'download\s*Edit\s*Forwarding', '', raw_text, flags=re.IGNORECASE)

                            raw_text = re.sub(r'转发\s*编辑\s*下载', '', raw_text)

                            raw_text = re.sub(r'(?:下载|编辑|转发)\s*(?:下载|编辑|转发)\s*(?:下载|编辑|转发)', '', raw_text)

                            raw_text = raw_text.strip()

                            

                            # 초기화: 필터용 블랙리스트

                            absolute_blacklist = []

                            # ===== [사용자 요청] 텍스트 추출 (클립보드 사용 안 함) =====

                            # raw_text 이미 위에서 얻음, 여기서 불필요한 QR 코드·앨범 초대 문구 삭제

                            for blk in absolute_blacklist:

                                raw_text = raw_text.replace(blk, "")

                            raw_text = raw_text.strip()

                            self.add_log(f"  📋 본문 텍스트 추출 완료 ({len(raw_text)}자)", "INFO")



                            # [議곌굔 0] 珥덇퀬?꾪솕 遺덊븘장)?ъ뒪장)?꾪꽣留?(3?④퀎)

                            # ?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧장)



                            # --- 1?④퀎: 臾댁“嫄장)ㅽ궢 (?④?/肄붾뱶 ?좊Т? ?곴장)놁씠 100% ?먭린) ---

                            # QR肄붾뱶, 怨듭쑀 珥덈?, → ?띾낫, ?꾩콟 ?꾩슜 UI ?띿뒪장) ?멸낏?곸씤 怨듭?/?띾낫 →

                            absolute_blacklist = [
                                "二维码", "扫码", "扫一扫", "转发朋友圈",
                                "秘密基地",
                                "加微信", "加我", "联系方式",
                                "关注", "点赞", "收藏", "评论",
                                "接单", "物流", "火龙",
                                "特价福利", "优惠活动", "活动来袭", "年终馈赠"
                            ]



                            # AI가 분석한 업체 전용 무조건 제외 조건 추가

                            if current_vendor_skip_conditions:

                                absolute_blacklist.extend(current_vendor_skip_conditions)



                            skip_reason = next((abk for abk in absolute_blacklist if abk in raw_text), None)

                            if skip_reason:

                                self.add_log(f"  🚫 [필터1: {skip_reason}] 무조건 스킵: {raw_text[:25]}...", "WARNING")

                                continue



                            # ===== [신규 필터] 텍스트 길이 필터 (5자 미만) =====

                            # 단, "尺码表"/"模特图" 등 사이즈표/모델컷은 이미지를 이전 대기상품에 병합

                            _is_size_chart = any(kw in raw_text for kw in ["尺码表", "尺码", "模特图", "模特", "size"])

                            if len(raw_text.strip()) < 5:

                                if _is_size_chart and _pending_product:

                                    # 사이즈표/모델컷 이미지를 추출하여 대기상품에 병합

                                    _sc_imgs = []

                                    for _sc_img in item.find_all('img'):

                                        _sc_src = _sc_img.get('data-src') or _sc_img.get('src')

                                        if _sc_src and not _sc_src.endswith('gif') and 'data:image' not in _sc_src:

                                            _sc_clean = "https:" + _sc_src.split("?")[0] if _sc_src.split("?")[0].startswith("//") else _sc_src.split("?")[0]

                                            _sc_imgs.append(_sc_clean)

                                    if _sc_imgs:

                                        _pending_product["img_urls"].extend(_sc_imgs)

                                        self.add_log(f"  📏 [사이즈표 병합] {raw_text.strip()} → 대기상품에 {len(_sc_imgs)}장 추가 (총 {len(_pending_product['img_urls'])}장)", "INFO")

                                    continue

                                else:

                                    self.add_log(f"  🚫 [필터: 길이] 텍스트가 5자 미만이라 스킵: {raw_text[:25]}...", "WARNING")

                                    continue



                            # ===== [신규 필터] 단가 표기 필터 (필수: 없으면 무조건 스킵) =====

                            has_price_indicator = (any(pt in raw_text for pt in ["¥", "元", "块", "价"])

                                        or re.search(r'[pP]\s*\d+', raw_text)

                                        or re.search(r'[wW]\s*\d+', raw_text)

                                        or re.search(r'[qQ]\s*\d+', raw_text)

                                        or re.search(r'\b\d{2,4}\b', raw_text))

                            if not has_price_indicator:

                                self.add_log(f"  🚫 [필터: 단가] 단가 표기가 없어 스킵: {raw_text[:25]}...", "WARNING")

                                continue



                            # ===== [신규 필터] 사이즈 표기 필터 (필수: 없으면 무조건 스킵) =====

                            has_size_indicator = (

                                re.search(r'\b[sSmMlLxXfF]{1,4}\b', raw_text) or

                                re.search(r'\b(?:2[6-9]|3[0-9]|4[0-5])\b', raw_text) or

                                any(s in raw_text for s in ["尺码", "码数", "胸围", "衣长", "肩宽", "裤长", "尺寸", "均码", "内长", "腰围", "码", "号"])

                            )

                            if not has_size_indicator:

                                self.add_log(f"  🚫 [필터: 사이즈] 사이즈 표기가 없어 스킵: {raw_text[:25]}...", "WARNING")

                                continue



                            has_price = has_price_indicator

                            has_code = re.search(r'[a-zA-Z]+\d+|\d+[a-zA-Z]+', raw_text)



                            # 불필요한 이미지(댓글/공유 → 클릭 → QR코드 → 바로가기사진 DOM에서 제거

                            for excluded in item.find_all('div', class_=lambda c: c and any(sub in c.lower() for sub in ['comment', 'share', 'footer', 'qr', 'qrcode'])):

                                excluded.decompose()

                            for excluded in item.find_all('img', class_=lambda c: c and any(sub in c.lower() for sub in ['avatar', 'head', 'logo', 'icon', 'qr', 'qrcode', 'thumb'])):

                                excluded.decompose()



                            # 이미지 URL 및 상품 ID 초기화

                            img_urls = []  # 반드시 초기화 (UnboundLocalError 방지)

                            if not img_urls:

                                img_urls = []

                            if goods_id is None:
                                goods_id = None
                                shop_id = None
                                
                                html_str = str(item)
                                m_goods = re.search(r'goods_id(?:&quot;|["\':\s=;])+([a-zA-Z0-9_-]{8,})', html_str)
                                if m_goods: goods_id = m_goods.group(1)
                                
                                m_shop = re.search(r'shop_id(?:&quot;|["\':\s=;])+([a-zA-Z0-9_-]+)', html_str)
                                if m_shop: shop_id = m_shop.group(1)
    
                                data_info_str = item.get('data-search-bury-info')
    
                                if not data_info_str:
                                    child = item.find(attrs={"data-search-bury-info": True})
                                    if child:
                                        data_info_str = child.get('data-search-bury-info')
    
                                if data_info_str:
                                    try:
                                        data_info = __import__('json').loads(data_info_str.replace('&quot;', '"'))
                                        goods_id = goods_id or data_info.get('goods_id')
                                        shop_id = shop_id or data_info.get('shop_id')
                                    except: pass
    
                                if not goods_id or not shop_id:
                                    # Fallback: look for a theme_detail link
                                    for a in item.find_all('a', href=True):
                                        href = a.get('href', '')
                                        if 'theme_detail' in href:
                                            parts = href.split('/')
                                            if len(parts) >= 3:
                                                goods_id = goods_id or parts[-1].split('?')[0]
                                                shop_id = shop_id or parts[-2]
                                                break
    
                                # DEBUG DUMP
                                if not goods_id:
                                    with open("item_dump.html", "w", encoding="utf-8") as f:
                                        f.write(str(item))
    
                                # 중복 체크는 최상단에서 처리했지만, 새로 발견된 goods_id가 있다면 업데이트
                                seen_items.add(goods_id if goods_id else raw_text[:50])



                            # ====== [변경] 본문 사진 전체 스캔 (썸네일 미사용) ======

                            for img in item.find_all('img'):

                                src = img.get('data-src') or img.get('src')

                                if not src and img.get('srcset'):

                                    src = img.get('srcset').split(',')[0].split()[0]

                                if src:

                                    clean_src = src.split('?')[0]

                                    if clean_src.startswith("//"): clean_src = "https:" + clean_src

                                    if any(kw in clean_src.lower() for kw in ['thumb', 'qr', 'qrcode', 'avatar', 'icon', 'logo']):

                                        continue

                                    if clean_src not in img_urls:

                                        img_urls.append(clean_src)



                            for div in item.find_all(style=True):

                                style = div['style']

                                match = re.search(r'url\([\'"]?(.*?)[\'"]?\)', style)

                                if match:

                                    src = match.group(1).split('?')[0]

                                    if src.startswith("//"): src = "https:" + src

                                    if any(kw in src.lower() for kw in ['thumb', 'qr', 'qrcode', 'avatar', 'icon', 'logo']):

                                        continue

                                    if src not in img_urls:

                                        img_urls.append(src)



                            # DOM 스캔을 통한 이미지 확보는 조용히(백그라운드) 처리합니다.

                            # (실제 원본 다운로드 버튼 클릭이 우선이며, 실패할 경우에만 사용됨)

                            

                            # API 패킷 복구를 통한 goods_id 복원만 유지하고 imgs 추출은 제거.

                            short_text = re.sub(r'\s+', '', raw_text)[:30]

                            try:

                                matched_data = None

                                if goods_id:

                                    matched_data = page.evaluate(f"window.feedApiData['{goods_id}'] || null")

                                if not matched_data:

                                    matched_data = page.evaluate(f"window.feedApiData['{short_text}'] || null")

                                    

                                if matched_data:

                                    if not goods_id:

                                        goods_id = matched_data.get('goods_id')

                                        shop_id = matched_data.get('shop_id')

                                        self.add_log(f"  🎯 [API 패킷 복구] DOM에서 누락된 goods_id 복원 성공 ({goods_id[-6:] if goods_id else 'N/A'})", "SUCCESS")

                            except Exception:

                                pass



                            # ===== [변경] 팝업 진입 임시 중지 및 리스트에서 직접 다운로드 버튼 클릭 =====

                            _item_idx = items.index(item) if item in items else -1

                            if _item_idx >= 0:

                                pw_item = page.locator('[class*="normalItemContent"], .w-1-3').nth(_item_idx)

                                dl_btn = pw_item.locator('.wsxc_download').first

                                if dl_btn.count() == 0:

                                    dl_btn = pw_item.locator('text="下载", text="download"').first



                                if dl_btn.count() > 0:

                                    self.add_log(f"  📥 [리스트 직접 다운로드] 다운로드 버튼 클릭 시도 (아이템 #{_item_idx})", "INFO")

                                    try:

                                        downloads_collected = []

                                        def handle_download(d):

                                            downloads_collected.append(d)

                                            

                                        page.on("download", handle_download)

                                        dl_btn.evaluate("el => el.click()")

                                        

                                        # 웨이상 자체 광고 팝업("PC버전 다운로드 권유")이 뜨면 닫아줌

                                        try:

                                            continue_btn = page.wait_for_selector('text=继续下图', timeout=3000)

                                            if continue_btn:

                                                continue_btn.click()

                                        except:

                                            pass

                                            

                                        # 다운로드가 서버에서 준비되어 시작될 때까지 최대 15초 대기

                                        for _ in range(30):

                                            if downloads_collected:

                                                break

                                            page.wait_for_timeout(500)

                                            

                                        # 첫 다운로드가 시작되었다면, 낱장으로 여러 개가 떨어질 수 있으므로 3초 더 대기

                                        if downloads_collected:

                                            page.wait_for_timeout(3000)

                                            

                                        page.remove_listener("download", handle_download)

                                        

                                        if downloads_collected:

                                            import os

                                            import zipfile

                                            local_files = []

                                            for d in downloads_collected:

                                                try:

                                                    filename = d.suggested_filename

                                                    save_path = os.path.join(dest_dir, f"dl_{_item_idx}_{filename}")

                                                    d.save_as(save_path)

                                                    

                                                    if filename.lower().endswith('.zip'):

                                                        extract_dir = os.path.join(dest_dir, f"ext_{_item_idx}_{goods_id or 'item'}")

                                                        os.makedirs(extract_dir, exist_ok=True)

                                                        with zipfile.ZipFile(save_path, 'r') as zip_ref:

                                                            zip_ref.extractall(extract_dir)

                                                        extracted = [os.path.join(extract_dir, f) for f in os.listdir(extract_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]

                                                        local_files.extend(extracted)

                                                        try: os.remove(save_path)

                                                        except: pass

                                                    else:

                                                        if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):

                                                            local_files.append(save_path)

                                                except Exception as dl_err:

                                                    self.add_log(f"  ⚠️ 개별 파일 다운로드 중 오류: {dl_err}", "WARNING")

                                                    

                                            if local_files:

                                                img_urls = local_files

                                                self.add_log(f"  ✅ [다운로드 완료] 로컬 고화질 원본 사진 {len(local_files)}장 확보 완료!", "SUCCESS")

                                        else:

                                            self.add_log(f"  ⚠️ 직접 다운로드 실패. 화면 스캔 사진({len(img_urls)}장)으로 대체합니다.", "WARNING")

                                            

                                    except Exception as e:

                                        self.add_log(f"  ⚠️ [리스트 직접 다운로드 실패]: {e} → 화면 스캔 사진({len(img_urls)}장)으로 대체합니다.", "WARNING")

                                        try: page.remove_listener("download", handle_download)

                                        except: pass

                                else:

                                    self.add_log(f"  ⚠️ [다운로드 버튼 없음] 화면 스캔 사진({len(img_urls)}장)으로 대체합니다.", "WARNING")

                                    self.add_log(f"  ⚠️ [리스트 다운로드] 다운로드 버튼을 찾을 수 없음 (아이템 #{_item_idx})", "WARNING")



                            if not img_urls: # DOM 추출도 실패했을 경우 대비 

                                for img in item.find_all('img'):

                                    src = img.get('data-src') or img.get('src')

                                    if src and not src.endswith('gif') and 'data:image' not in src and 'addCart' not in src and 'qr' not in src.lower() and 'wxacode' not in src.lower() and 'qrcode' not in src.lower() and 'share_card' not in src.lower() and 'share_img' not in src.lower():

                                        clean_src = "https:" + src.split("?")[0] if src.split("?")[0].startswith("//") else src.split("?")[0]

                                        img_urls.append(clean_src)

                                for tag in item.find_all(style=lambda s: s and 'background-image' in s.lower()):

                                    style = tag.get('style')

                                    match = re.search(r'url\([\'"]?(.*?)[\'"]?\)', style)

                                    if match:

                                        src = match.group(1)

                                        if src and not src.endswith('gif') and 'data:image' not in src and 'qr' not in src.lower():

                                            clean_src = "https:" + src.split("?")[0] if src.split("?")[0].startswith("//") else src.split("?")[0]

                                            img_urls.append(clean_src)



                            img_urls = list(dict.fromkeys(img_urls))





                            # [수정됨] 마지막 이미지가 QR 공유 카드이면 제거



                            if img_urls:



                                _last_url = img_urls[-1].lower()



                                _qr_patterns = ["qr", "qrcode", "wxacode", "share_card", "share_img", "erweima"]



                                if any(qp in _last_url for qp in _qr_patterns):



                                    img_urls.pop()



                                    self.add_log("  🗑️ QR 공유 카드 이미지 자동 제거 (마지막 사진)", "INFO")



                            self.add_log(f"  📸 이미지 추출 완료: {len(img_urls)}장 (goods_id={goods_id[-6:] if goods_id else 'N/A'})", "INFO")

                            

                            # ?대?吏 異붿텧 ?ㅽ뙣 → (?꾩쭅 濡쒕뵫 以? seen_items ?깅줉?섏? ?딄퀬 ?⑥뒪?섏뿬 ?ㅼ쓬 猷⑦봽장)?ъ떆장) 

                            if not img_urls:

                                continue

                            

                            # ????? [怨좊룄?붾맂 상품 寃쎄퀎(Boundary) ?쒕㎤장)?먮퀎 ?붿쭊 v2] ????? 

                            # ?듭떖 ?먯튃: 癒쇱? "蹂댁땐 ?ъ뒪?낆씤가?"瑜장)먮퀎?섍퀬, 蹂댁땐장)?꾨땺 ?뚮쭔 硫붿씤?쇰줈 ?먮퀎 

                            

                            main_keywords = ["主图", "正面", "侧面", "背面", "全景", "整体", "外观", "模特图", "上身图", "第一眼", "主打", "首图", "展示", "大图", "特写"]

                            supplement_keywords = ["细节", "实拍", "大货", "五金", "内里", "拉链", "底面", "走线", "包装", "视频", "上身效果", "模特", "继续", "质感"]

                            

                            # AI 프로파일링에서 제공한 업체 고유 경계 키워드 주입

                            if current_vendor_boundary_signals:

                                main_keywords = list(set(main_keywords + current_vendor_boundary_signals))

                            # AI ?꾨줈?뚯씪留곸뿉장)?쒓났장)蹂댁땐 ?ъ뒪장)?ㅼ썙장)二쇱엯 

                            current_vendor_supplement_patterns = current_vendor_ai_rules.get("supplement_patterns", [])

                            if current_vendor_supplement_patterns:

                                supplement_keywords = list(set(supplement_keywords + current_vendor_supplement_patterns))

                            

                            is_main_desc = any(mk in raw_text for mk in main_keywords)

                            is_supplement = any(sk in raw_text for sk in supplement_keywords)

                            vendor_rule_blob = " ".join(str(v) for v in [

                                current_vendor_posting_pattern,

                                current_vendor_grouping_rules,

                                current_vendor_matching_rules,

                                current_vendor_post_structure,

                                current_vendor_pricing_pattern,

                            ] if v)

                            text_is_short = len(raw_text.strip()) < 35

                            has_boundary_signal = is_main_desc or _has_any_keyword(raw_text, current_vendor_boundary_signals)

                            has_supplement_signal = is_supplement or _has_any_keyword(raw_text, current_vendor_supplement_patterns)

                            rule_prefers_split_on_price = has_price and any(k in vendor_rule_blob for k in ["가격", "단가", "금액", "price", "价格"])

                            rule_prefers_merge_detail = any(k in vendor_rule_blob for k in ["보충", "상세", "디테일", "사이즈표", "모델컷", "제품컷", "추가컷"])

                            

                            # --- AI 비전 기반 궤적/경계(Boundary) 판별 로직 --- 

                            is_main_product = True

                            

                            # [추가] 색상별 포스팅 병합 안함 옵션

                            if settings.get('disable_grouping', False):

                                is_main_product = True

                                self.add_log("  🎨 [설정] 색상/분할 무관 개별 수집 옵션 활성화 → 항상 새 상품으로 분리", "INFO")

                            elif _pending_product is None:

                                is_main_product = True

                            elif not img_urls:

                                is_main_product = False

                                self.add_log("  🔍 [경계판별] 무사진 포스팅 발견 → 직전 상품 텍스트에 강제 병합", "INFO")

                            elif is_single_posting_vendor and (has_boundary_signal or has_price or has_code):

                                is_main_product = True

                                self.add_log("  🔍 [AI업체규칙] 단일상품형 업체의 새 상품 신호 → 새 상품으로 분리", "INFO")

                            elif rule_prefers_split_on_price and not has_supplement_signal:

                                is_main_product = True

                                self.add_log("  🔍 [AI업체규칙] 가격/단가 신호가 새 상품 기준 → 새 상품으로 분리", "INFO")

                            else:

                                current_first_img = img_urls[0]

                                pending_first_img = _pending_product.get("img_urls", [None])[0]

                                

                                if pending_first_img:

                                    # ===== [최적화] 업체 규칙 기반 조기 판별 (비전 AI 생략 가능) =====

                                    _rule_decided = False

                                    

                                    # Case 1: 분할형 업체 + 명확한 보충컷 신호 → AI 없이 병합

                                    if is_split_posting_vendor and has_supplement_signal and not has_boundary_signal:

                                        is_visually_same = True

                                        _rule_decided = True

                                        self.add_log("  ⚡ [규칙 기반 판별] 분할형 업체 + 보충컷 신호 → AI 생략, 직접 병합", "INFO")

                                    

                                    # Case 2: 분할형 업체 + 짧은 텍스트 + 가격/코드 없음 → AI 없이 병합

                                    elif is_split_posting_vendor and text_is_short and not has_price and not has_code and rule_prefers_merge_detail:

                                        is_visually_same = True

                                        _rule_decided = True

                                        self.add_log("  ⚡ [규칙 기반 판별] 분할형 업체 + 짧은 보충글 → AI 생략, 직접 병합", "INFO")

                                    

                                    # Case 3: 가격+코드+경계신호 모두 있음 → 확실한 새 상품

                                    elif has_price and has_code and has_boundary_signal:

                                        is_visually_same = False

                                        _rule_decided = True

                                        self.add_log("  ⚡ [규칙 기반 판별] 가격+코드+경계신호 → AI 생략, 새 상품 확정", "INFO")

                                    

                                    # 규칙으로 판별 불가 시에만 비전 AI 호출

                                    if not _rule_decided:

                                        if settings.get('skip_vision', False):

                                            self.add_log("  ⚡ [초고속 모드] 비전 AI 판별을 건너뛰고 텍스트/규칙만으로 병합을 시도합니다.", "INFO")

                                            is_visually_same = None

                                        else:

                                            self.add_log("  👁️ [비전 판별 요청] 앞 포스팅의 사진과 동일 상품(보충컷/모델컷)인지 교차 검증합니다...", "INFO")

                                            is_visually_same = _verify_same_product_visually(pending_first_img, current_first_img)

                                    

                                    if is_visually_same is True:

                                        is_main_product = False

                                        self.add_log("  ✅ [경계판별-AI매칭 성공] 앞 포스팅과 동일한 상품(디자인 일치) → 보충컷으로 병합합니다.", "INFO")





                                        # [수정됨] 이미지 수 상한 기반 안전 분리 (30장 초과 시 강제 새 상품)



                                        # AI가 동일 상품이라 판정하더라도, 누적 이미지가 너무 많으면 분리



                                        if _pending_product and len(_pending_product.get("img_urls", [])) >= vendor_image_soft_cap:



                                            is_main_product = True



                                            self.add_log(f"  ✂️ [이미지 상한 분리] 누적 {len(_pending_product['img_urls'])}장/{vendor_image_soft_cap}장 → 강제 새 상품 분리", "WARNING")







                                    elif is_visually_same is False:

                                        is_main_product = True

                                        self.add_log("  ✂️ [경계판별-AI매칭 불일치] 사진상 다른 상품임 → 새 상품 포스팅으로 절단(분리)합니다.", "INFO")

                                    else:

                                        if is_split_posting_vendor and (has_supplement_signal or (rule_prefers_merge_detail and text_is_short and not has_price)):

                                            is_main_product = False

                                            self.add_log("  🔍 [AI업체규칙-휴리스틱] 분할형 업체의 보충/상세컷 신호 → 직전 상품에 병합", "INFO")

                                        elif (has_boundary_signal or has_price or has_code) and not (is_split_posting_vendor and rule_prefers_merge_detail and text_is_short):

                                            is_main_product = True

                                            self.add_log("  ✂️ [경계판별-휴리스틱] 상품 경계/가격/코드 신호 우선 적용 → 새 상품으로 분리", "INFO")

                                        elif has_supplement_signal or (rule_prefers_merge_detail and text_is_short):

                                            is_main_product = False

                                            self.add_log("  🔍 [경계판별-휴리스틱] 보충/상세 신호 → 직전 상품에 병합", "INFO")

                                        else:

                                            # Phase 4: 스마트 의미적(Semantic) 일치도 분석 (Pure Python)

                                            pending_text = _pending_product.get('original_chinese', '')

                                            # 공통 글자(단어)가 30% 이상 겹치면 유사 상품 보충으로 간주

                                            pending_chars = set(pending_text.replace(" ", ""))

                                            current_chars = set(raw_text.replace(" ", ""))

                                            overlap_ratio = 0

                                            if current_chars and pending_chars:

                                                overlap_ratio = len(pending_chars.intersection(current_chars)) / len(current_chars)

                                            

                                            if overlap_ratio >= 0.3:

                                                is_main_product = False

                                                self.add_log(f"  🔍 [경계판별-Semantic] 텍스트 유사도 {overlap_ratio*100:.0f}% 일치 → 직전 상품에 병합", "INFO")

                                            elif len(raw_text.strip()) < 10 and not re.search(r'[a-zA-Z0-9]+', raw_text):

                                                # 10자 미만이면서 영어/숫자 코드도 없으면 단순 보충글일 확률 높음

                                                is_main_product = False

                                                self.add_log("  🔍 [경계판별-휴리스틱] 매우 짧은 단순글(<10자) → 직전 상품에 병합", "INFO")

                                            else:

                                                is_main_product = True

                                                self.add_log(f"  🔍 [경계판별-휴리스틱] 비전판별 불가 및 의미적 연관성 낮음 → 새 상품으로 분리", "INFO")

                                else:

                                    is_main_product = True

                                

                                # ?湲장)곹뭹장)?녿뒗 (泥장)곹뭹?닿굅장)諛⑷툑 ?깅줉장)吏곹썑) 寃쎌슦 → 사진장)2장)?댁긽?대㈃ 硫붿씤?쇰줈 ?쒖옉 

                                # ?€湲장)곹뭹장)?녿뒗 (泥장)곹뭹?닿굅장)諛⑷툑 ?깅줉장)吏곹썑) 僎쎌슦 → 사진장)2장)?댁긽?대㈃ 硫붿씤?쇰줈 ?쒖옉 

                                if _pending_product is None and len(img_urls) >= 4:

                                    is_main_product = True

                                    

                                self.add_log(f"  🔍 [경계판별] 메인={is_main_product} | 패턴={current_vendor_posting_pattern or '-'} | 보충={has_supplement_signal} | 경계={has_boundary_signal} | 가격={has_price} | 코드={'Y' if has_code else 'N'} | 텍스트={len(raw_text)}자 | 사진={len(img_urls)}장 | 대기={'Y' if _pending_product else 'N'}", "INFO")

                                # ===== [초고도화] 브랜드/모델/가격/색상 불일치에 의한 강제 분리 로직 =====
                                if not is_main_product and _pending_product is not None:
                                    pending_text = _pending_product.get("raw_text", "")
                                    current_text = raw_text

                                    # 1. 브랜드 추출 및 비교
                                    brands = {
                                        "Cartier": ["卡地亚", "cartier", "Cartier"],
                                        "Montblanc": ["万宝龙", "montblanc", "Montblanc", "MB"],
                                        "Bottega": ["宝缇嘉", "보테가", "bottega", "Bottega", "BV", "宝缇"],
                                        "Chanel": ["香奈儿", "chanel", "Chanel"],
                                        "LV": ["路易威登", "lv", "LV", "Louis Vuitton"],
                                        "Gucci": ["古驰", "gucci", "Gucci"],
                                        "Prada": ["普拉达", "prada", "Prada"],
                                        "Dior": ["迪奥", "dior", "Dior"],
                                        "YSL": ["圣罗兰", "ysl", "YSL", "Saint Laurent"],
                                        "Hermes": ["爱马仕", "hermes", "Hermes"],
                                        "ThomBrowne": ["汤姆布朗", "thombrowne", "Thom Browne"],
                                        "Celine": ["思琳", "celine", "Celine"],
                                        "Fendi": ["芬迪", "fendi", "Fendi"],
                                        "Balenciaga": ["巴黎世家", "balenciaga", "Balenciaga"],
                                        "MiuMiu": ["miumiu", "Miu Miu", "缪缪"],
                                        "Rolex": ["劳力士", "rolex", "Rolex"],
                                        "Omega": ["欧米茄", "omega", "Omega"],
                                    }

                                    def get_brands(text):
                                        found = set()
                                        for brand_key, keywords in brands.items():
                                            for kw in keywords:
                                                if kw.lower() in text.lower():
                                                    found.add(brand_key)
                                                    break
                                        return found

                                    pending_brands = get_brands(pending_text)
                                    current_brands = get_brands(current_text)

                                    brand_mismatch = False
                                    if pending_brands and current_brands:
                                        if not pending_brands.intersection(current_brands):
                                            brand_mismatch = True

                                    # 2. 모델 번호(품번) 추출 및 비교
                                    model_patterns = [
                                        r'(?:型号|货号|款号|编号|编码|SKU|码数)\s*[：:]\s*([a-zA-Z0-9#-]{4,15})',
                                        r'#\s*([a-zA-Z0-9#-]{5,15})',
                                    ]

                                    def get_models(text):
                                        found = set()
                                        for pattern in model_patterns:
                                            matches = re.findall(pattern, text)
                                            for m in matches:
                                                if len(m.strip()) >= 4:
                                                    found.add(m.strip().upper())
                                        extra_codes = re.findall(r'\b[a-zA-Z]+\d+\w*\b|\b\d+[a-zA-Z]+\w*\b', text)
                                        for c in extra_codes:
                                            if len(c.strip()) >= 4:
                                                found.add(c.strip().upper())
                                        return found

                                    pending_models = get_models(pending_text)
                                    current_models = get_models(current_text)

                                    model_mismatch = False
                                    if pending_models and current_models:
                                        if not pending_models.intersection(current_models):
                                            model_mismatch = True

                                    # 3. 가격 비교
                                    def extract_raw_price(text):
                                        m = re.search(r'(?:¥|元|p|w|q|P|W|Q|价)\s*(\d{2,4})\b', text)
                                        if m:
                                            return int(m.group(1))
                                        numbers = re.findall(r'\b\d{2,4}\b', text)
                                        if numbers:
                                            return int(numbers[0])
                                        return None

                                    pending_price = extract_raw_price(pending_text)
                                    current_price = extract_raw_price(current_text)

                                    price_mismatch = False
                                    if pending_price is not None and current_price is not None:
                                        if pending_price != current_price:
                                            price_mismatch = True

                                    # 4. 색상 비교 (특히 merge_same_product 모드일 때 색상 다르면 분리)
                                    colors = {
                                        "black": ["黑色", "经典黑", "纯黑", "黑"],
                                        "brown": ["榛果棕色", "榛果棕", "咖啡色", "咖啡", "棕色", "棕", "榛果", "褐色", "驼色"],
                                        "white": ["白色", "纯白", "白"],
                                        "red": ["红色", "红", "大红", "酒红", "粉红"],
                                        "blue": ["蓝色", "蓝", "藏青", "深蓝"],
                                        "grey": ["灰色", "灰"],
                                        "green": ["绿色", "绿", "墨绿"],
                                        "yellow": ["黄色", "黄", "杏色", "橙色"],
                                        "gold": ["金色", "金"],
                                        "silver": ["silver", "银色", "银"],
                                    }

                                    def get_colors(text):
                                        found = set()
                                        for color_key, keywords in colors.items():
                                            for kw in keywords:
                                                if kw in text:
                                                    found.add(color_key)
                                                    break
                                        return found

                                    pending_colors = get_colors(pending_text)
                                    current_colors = get_colors(current_text)

                                    color_mismatch = False
                                    grouping_mode = settings.get("grouping_mode", "merge_color_options")
                                    if grouping_mode == "merge_same_product" and pending_colors and current_colors:
                                        if not pending_colors.intersection(current_colors):
                                            color_mismatch = True

                                    # 최종 강제 분리 여부 결정
                                    force_split = False
                                    split_reason = ""

                                    if brand_mismatch:
                                        force_split = True
                                        split_reason = f"브랜드 불일치 (직전: {pending_brands} vs 현재: {current_brands})"
                                    elif model_mismatch:
                                        force_split = True
                                        split_reason = f"모델 품번 불일치 (직전: {pending_models} vs 현재: {current_models})"
                                    elif price_mismatch:
                                        force_split = True
                                        split_reason = f"가격(단가) 불일치 (직전: {pending_price} vs 현재: {current_price})"
                                    elif color_mismatch:
                                        force_split = True
                                        split_reason = f"색상 불일치 & 색상개별옵션설정 (직전: {pending_colors} vs 현재: {current_colors})"

                                    if force_split:
                                        is_main_product = True
                                        self.add_log(f"  ✂️ [초고도화 강제 분리] {split_reason} → 이전 대기상품을 확정하고 새 상품으로 등록합니다.", "WARNING")


                            # ===== 2. 색상/모델 변경 감지 (First Principles: Text Template Diffing) =====

                            if not is_main_product:

                                model_changed = False

                                

                                if _group_txt_buf and _group_img_buf:

                                    import difflib

                                    # 직전 포스팅(같은 상품으로 묶인 가장 최근 글)의 텍스트와 비교

                                    prev_text = _group_txt_buf[-1]

                                    

                                    # 공백 제거 후 비교하여 순수 텍스트 템플릿의 유사도 측정

                                    current_clean = raw_text.replace(" ", "").replace("\n", "")

                                    prev_clean = prev_text.replace(" ", "").replace("\n", "")

                                    

                                    if len(current_clean) > 0 and len(prev_clean) > 0:

                                        # 1. 템플릿 복붙 교체 패턴 (75% ~ 99% 유사도)

                                        ratio = difflib.SequenceMatcher(None, current_clean, prev_clean).ratio()

                                        

                                        # 2. 아주 짧은 텍스트 (예: "화이트", "블랙" 등 단어 1~3개만 올리는 경우)

                                        is_short_diff = (len(current_clean) <= 6 and len(prev_clean) <= 6 and current_clean != prev_clean)

                                        

                                        if (0.75 <= ratio < 0.99) or is_short_diff:

                                            model_changed = True

                                            self.add_log(f"  🔀 [색상/옵션 분할 감지] 텍스트 템플릿 매칭 (유사도 {ratio*100:.0f}%) → 새로운 색상 포스팅으로 분할", "WARNING")

                                

                                # 사진 수가 너무 많아지면 안전장치로 강제 분할 (20장)

                                if _group_img_buf and len(_group_img_buf) >= 20:

                                    model_changed = True

                                    self.add_log(f"  🔀 [안전 분할] 한 제품에 사진 {len(_group_img_buf)}장 초과 누적 → 강제 분할", "WARNING")

                                

                                if model_changed:

                                    _flush_img_urls = list(dict.fromkeys(_group_img_buf))

                                    _flush_raw_text = "\n".join(_group_txt_buf) if _group_txt_buf else ""

                                    _group_img_buf = []

                                    _group_txt_buf = []

                                    

                                    if len(_flush_img_urls) >= 4 and _flush_raw_text:

                                        processed_count += 1

                                        _f_title = _flush_raw_text[:30].strip()

                                        _f_code = trans_options.get("prefix", "AUTO") if trans_options else "AUTO"

                                        _f_translated = ""

                                        

                                        if translator and trans_options and trans_options.get("enable"):

                                            try:

                                                # 移댄뀒怨좊━ ?곗꽑?쒖쐞: AI遺꾩꽍 > ?ㅼ썙?쒖텛痢?> ?꾨줎장)?꾩뿭?ㅼ젙 

                                                _guessed = _guess_category(getattr(self, "current_vendor_title", ""), _flush_raw_text)

                                                cat = current_vendor_ai_category or _guessed or trans_options.get("category", "남성의류")

                                                

                                                # ?넅 移댄뀒怨좊━蹂장)꾩슜 踰덉뿭 ?묒떇 二쇱엯 

                                                _cat_template = get_template_for_category(cat)

                                                

                                                _ai_hints_str = ""

                                                if current_vendor_recommended_style:

                                                    _ai_hints_str += f"\n- [AI 톤앤매너 권장]: {current_vendor_recommended_style}"

                                                if current_vendor_bundle_logic:

                                                    _ai_hints_str += f"\n- [상품 구성 안내]: {current_vendor_bundle_logic}"

                                                if current_vendor_ai_rules.get("posting_pattern"):

                                                    _ai_hints_str += f"\n- [업체 포스팅 패턴]: {current_vendor_ai_rules.get('posting_pattern')}"

                                                if current_vendor_ai_rules.get("analysis_reason"):

                                                    _ai_hints_str += f"\n- [기타 분석 내용]: {current_vendor_ai_rules.get('analysis_reason')}"

                                                if current_vendor_post_structure:

                                                    _ai_hints_str += f"\n- [업체 글 구성 규칙]: {current_vendor_post_structure}"

                                                if current_vendor_profile_rules:

                                                    _ai_hints_str += f"\n- [업체별 최우선 작성 규칙]: {current_vendor_profile_rules}"

                                                if current_vendor_pricing_pattern:

                                                    _ai_hints_str += f"\n- [단가/가격 표기 패턴]: {current_vendor_pricing_pattern}"

                                                if current_vendor_grouping_rules:

                                                    _ai_hints_str += f"\n- [상품 묶음 판단 규칙]: {current_vendor_grouping_rules}"

                                                if current_vendor_matching_rules:

                                                    _ai_hints_str += f"\n- [동일 상품 판별 규칙]: {current_vendor_matching_rules}"

                                                

                                                if _ai_hints_str:

                                                    _ai_hints_str = (

                                                        "\n\n[해당 업체 AI 분석 기반 작성 지침]"

                                                        f"{_ai_hints_str}"

                                                        "\n위 지침을 자연스럽게 반영해 상품글을 작성하고 번역하세요."

                                                    )

                                                    

                                                _fp = f"아래 중국어 상품 정보를 한국어 프리미엄 쇼핑몰 형식으로 번역해줘. 카테고리: {cat}.\n\n{_cat_template}{_ai_hints_str}\n\n원문:\n{_flush_raw_text}"

                                                _fres = translator.models.generate_content(model='gemini-2.5-flash-lite', contents=[_fp])

                                                if _fres and _fres.text:

                                                    _f_title = [l.strip() for l in _fres.text.split("\n") if l.strip()][0][:40]

                                                    _f_translated = _fres.text

                                            except Exception as e:

                                                self.add_log(f"    ⚠️ 분리 상품 번역 실패: {e}", "WARNING")

                                        

                                        safe_title_f = sanitize_path_component((_f_title or "item").strip())

                                        item_dir_f = os.path.join(dest_dir, f"{processed_count}_{safe_title_f}")

                                        os.makedirs(item_dir_f, exist_ok=True)

                                        local_imgs_f = self._download_images_parallel(_flush_img_urls, item_dir_f, prefix="", min_size=0)

                                        

                                        import datetime

                                        if self.add_product_func and local_imgs_f:

                                            self.add_product_func({

                                                "title": _f_title, "product_code": _f_code, "sale_price": "", "price_input": "-",

                                                "price_detected": False,

                                                "raw_description": _f_translated or _flush_raw_text, "original_chinese": _flush_raw_text,

                                                "vendor_name": getattr(self, "current_vendor_title", "UnknownVendor"),

                                                "vendor_id": vendor_lookup_id,

                                                "vendor_url": vendor_url,

                                                "vendor_profile_key": vendor_lookup_key,

                                                "vendor_category": current_vendor_ai_category,

                                                "image_urls": [], "image_server_urls": [], "local_image_dir": item_dir_f, "image_files": local_imgs_f,

                                                "local_image_paths": [os.path.join(item_dir_f, img) for img in local_imgs_f],

                                                "calc_log": "",

                                                "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                                            })

                                            self.add_log(f"  ✂️ 분리된 이전 모델 등록 완료: {_f_title} (사진 {len(local_imgs_f)}장)", "SUCCESS")

                                

                                # ?꾩옱 異붿텧장)?대?吏€瑜장)€湲장)곹뭹 or 踰꾪띁장)?€장) 

                                if _pending_product is not None:

                                    # ?€湲장)곹뭹장)?덉쑝硫?嫄곌린장)吏곸젒 ?⑹궛 (?듭떖: 紐⑤뜽而장)장)뷀뀒?쇱쓣 ?⑹묠) 

                                    img_urls = [u for u in img_urls if u not in _qr_candidate_urls]

                                    if img_urls: _pending_product["img_urls"].extend(img_urls)

                                    if raw_text: _pending_product["raw_text"] += "\n" + raw_text



                                    self.add_log(f"  -> [대기상품에 병합] 보충 {len(img_urls)}장 추가, 총 {len(_pending_product['img_urls'])}장", "SUCCESS")

                                else:

                                    # ?€湲장)곹뭹 ?놁쑝硫?湲곗〈 踰꾪띁장)?€장) 

                                    if img_urls: _group_img_buf.extend(img_urls)

                                    if raw_text: _group_txt_buf.append(raw_text)

                                    while len(_group_img_buf) > 40: _group_img_buf.pop(0)

                                    if len(_group_txt_buf) > 10: _group_txt_buf.pop(0)

                                    self.add_log(f"  -> [그룹 버퍼] 그룹버퍼 업데이트(이미지 {len(_group_img_buf)}장, 텍스트 {len(_group_txt_buf)}개)", "INFO")

                                

                                found_new = True  # 踰꾪띁장)蹂묓빀?섎뜑?쇰룄 '장)장)ぉ 諛쒓껄'?쇰줈 ?몄뇩 → 臾댄븳 ?ㅽ겕濡?諛⑹? 

                                continue

                            # ?봽 吏€장)?깅줉 ?⑦꽩: 硫붿씤 상품장)利됱떆 ?깅줉?섏? ?딄퀬 _pending_product장)?€장) 



                            # ?ㅼ쓬 硫붿씤 상품장)장)장)?댁쟾 ?€湲장)곹뭹장)?뺤젙 ?깅줉 



                            # ?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧장) 



                            



                            # Step A: ?댁쟾 ?€湲장)곹뭹(pending)장)?덉쑝硫장)뺤젙 ?깅줉 



                            if _pending_product is not None:



                                _pend_imgs = list(dict.fromkeys(_pending_product["img_urls"]))



                                _pend_text = _pending_product["raw_text"]



                                



                                if len(_pend_imgs) >= 4 and _pend_text:





                                    _pending_product["img_urls"] = [u for u in _pending_product.get("img_urls", []) if u not in _qr_candidate_urls]



                                    self.add_log(f"  -> [신규등록 전 상품 확정: 총 {len(_pend_imgs)}장]", "SUCCESS")



                                    # ?€湲장)곹뭹장)硫붿씤 ?ㅽ듃由쇱뿉 二쇱엯 (?꾨옒 ?깅줉 濡쒖쭅장)?ъ궗?⑺븯湲장)꾪빐 img_urls/raw_text 援먯껜) 



                                    _flush_pending_imgs = _pend_imgs



                                    _flush_pending_text = _pend_text



                                    _flush_pending_price = _pending_product.get("has_price", False)



                                    _flush_pending_code = _pending_product.get("has_code", None)



                                    



                                    # ---- 상품 정보 최종 확정 ---- 



                                    _p_vendor_name = getattr(self, "current_vendor_title", "UnknownVendor")



                                    _p_price_word = "-"



                                    _p_final_price_input = "-"



                                    _p_final_product_code = trans_options.get("prefix", "AUTO") if trans_options else "AUTO"



                                    



                                    # 단가 추출 

                                    _p_final_price_input = _extract_price(_flush_pending_text, _p_vendor_name, current_vendor_ai_category, current_vendor_ai_rules)

                                    



                                    # [수정됨] 단가 누락 시에도 등록 진행 (단가는 "-"로 표시, 나중에 수동 입력 가능)



                                    if _p_final_price_input == "-" or _p_final_price_input == "0":



                                        self.add_log(f"  ⚠️ [단가 미감지] 단가를 자동 추출하지 못했습니다. '-' 상태로 등록합니다. (텍스트: {_flush_pending_text[:50]}...)", "WARNING")



                                    



                                    processed_count += 1



                                    



                                    # [신규 추가] 업체코드 명시: 영문자음+숫자



                                    _vendor_eng_initials = get_korean_initial(_p_vendor_name).lower()



                                    _p_final_product_code = f"{_vendor_eng_initials}{_p_final_price_input}"



                                    



                                    # 기존 상품 코드 추출 추가 



                                    _pc = re.search(r'(?:Item Number|Number|No|code|id.*?)\s*[:：-]?\s*([A-Za-z0-9]{5,10})', _flush_pending_text, re.IGNORECASE)



                                    if _pc:



                                        _p_final_product_code = f"{_p_final_product_code}-{_pc.group(1)}".strip()



                                    



                                    try:



                                        import pricing_logic



                                        base_fx = float(trans_options.get("naver_fx", 195.0)) if trans_options else 195.0



                                        guessed_cat = _guess_category(_p_vendor_name, _flush_pending_text)



                                        cat_p = current_vendor_ai_category or guessed_cat or (trans_options.get("category", "여성의류") if trans_options else "여성의류")



                                        try: cost_p = float(_p_final_price_input)



                                        except: cost_p = 0.0



                                        _p_title = f"{_p_vendor_name} 상품"



                                        _p_gen_code, _p_sale_price, _p_dg, _p_calc_log = pricing_logic.generate_product_code_and_price(



                                            _p_vendor_name, cost_p, cat_p, _p_title, _flush_pending_text, base_fx)



                                        _p_final_product_code = f"[{_vendor_eng_initials}{_p_final_price_input}] {_p_gen_code}"



                                        ai_hints_p = ""



                                        if current_vendor_recommended_style:



                                            ai_hints_p += f"\n[AI 추천 방향] {current_vendor_recommended_style}"



                                        if current_vendor_bundle_logic:



                                            ai_hints_p += f"\n[묶음 등록 권장] {current_vendor_bundle_logic}"

                                        if current_vendor_post_structure:



                                            ai_hints_p += f"\n[업체 글 구성 규칙] {current_vendor_post_structure}"

                                        if current_vendor_profile_rules:



                                            ai_hints_p += f"\n[업체별 최우선 작성 규칙] {current_vendor_profile_rules}"

                                        if current_vendor_pricing_pattern:



                                            ai_hints_p += f"\n[단가/가격 표기 패턴] {current_vendor_pricing_pattern}"

                                        if current_vendor_grouping_rules:



                                            ai_hints_p += f"\n[상품 묶음 판단 규칙] {current_vendor_grouping_rules}"

                                        if current_vendor_matching_rules:



                                            ai_hints_p += f"\n[동일 상품 판별 규칙] {current_vendor_matching_rules}"



                                        _p_final_text = f"[중국어 원문]\n{_flush_pending_text}\n\n{_p_final_product_code}\n생성 {_p_dg}\n{ai_hints_p}"



                                        _p_final_sale_price = str(_p_sale_price)



                                    except Exception as _pe:



                                        self.add_log(f"  ⚠️ 대기상품 가격 계산 오류: {_pe}", "WARNING")



                                        _p_title = "item"



                                        _p_final_text = _flush_pending_text



                                        _p_final_sale_price = "0"



                                        _p_dg = ""



                                        _p_calc_log = ""



                                    



                                    if False:  # [수정됨] 단가 없어도 등록 진행 (기존: 단가 없으면 폐기)



                                        pass  # 이전: 단가가 없는 상품(병합본) 제외



                                    else:



                                        # ===== [20장 초과 스마트 분할] =====

                                        _split_parts = [_flush_pending_imgs]  # 기본: 분할 없이 그대로

                                        if len(_flush_pending_imgs) > 20:

                                            try:

                                                from backend.platforms.weishang.image_organizer import organize_product_images

                                                _split_parts = organize_product_images(

                                                    _flush_pending_imgs, translator, self._safe_ai_call, self.add_log

                                                )

                                            except Exception as _split_err:

                                                self.add_log(f"  ⚠️ [스마트 분할] 오류: {_split_err} → 20장 단순 자르기", "WARNING")

                                                _split_parts = [_flush_pending_imgs[:20], _flush_pending_imgs[20:]] if len(_flush_pending_imgs) > 20 else [_flush_pending_imgs]



                                        for _part_idx, _part_imgs in enumerate(_split_parts):

                                            _part_suffix = f" ({_part_idx+1}/{len(_split_parts)})" if len(_split_parts) > 1 else ""

                                            _p_safe = sanitize_path_component((_p_title or "item").strip())



                                            _p_dir = os.path.join(dest_dir, f"{processed_count}_{_p_safe}")



                                            os.makedirs(_p_dir, exist_ok=True)



                                            _p_local = self._download_images_parallel(_part_imgs, _p_dir, prefix="", min_size=5120)



                                        



                                            import datetime



                                            if self.add_product_func and _p_local:



                                                self.add_product_func({



                                                    "title": _p_title + _part_suffix, "product_code": _p_final_product_code,



                                                    "sale_price": _p_final_sale_price, "price_input": _p_final_price_input,



                                                    "price_detected": bool(_p_final_price_input and _p_final_price_input != "-"),



                                                    "raw_description": _p_final_text, "original_chinese": _flush_pending_text,



                                                    "vendor_name": _p_vendor_name,

                                                    "vendor_id": vendor_lookup_id,

                                                    "vendor_url": vendor_url,

                                                    "vendor_profile_key": vendor_lookup_key,

                                                    "vendor_category": current_vendor_ai_category,



                                                    "image_urls": [], "image_server_urls": [], "local_image_dir": _p_dir,



                                                    "image_files": _p_local,



                                                    "local_image_paths": [os.path.join(_p_dir, img) for img in _p_local],



                                                    "calc_log": _p_calc_log,



                                                    "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")



                                                })



                                            self.add_log(f"  👉 {processed_count}/{target_count} 완료 (대기상품 등록{_part_suffix}): {_p_title} (사진 {len(_p_local)}장)", "SUCCESS")

                                            if len(_split_parts) > 1 and _part_idx < len(_split_parts) - 1:

                                                processed_count += 1  # 분할 파트는 각각 카운트





                                    # 날짜 단위 크롤링에서는 갯수 도달만으로 즉시 중단하지 않음

                                    # if processed_count >= target_count:

                                    #     _pending_product = None

                                    #     break



                                else:



                                    self.add_log(f"  ⚠️ 이전 대기상품 조건 미달(사진 {len(_pend_imgs)}장). 폐기.", "WARNING")



                            



                            # Step B: ?꾩옱 硫붿씤 상품장)장)?€湲장)곹뭹?쇰줈 ?ㅼ젙 



                            _pending_product = {



                                "img_urls": list(img_urls),



                                "raw_text": raw_text,



                                "has_price": has_price,



                                "has_code": has_code,



                                "vendor_id": vendor_lookup_id,



                                "vendor_url": vendor_url,



                                "vendor_profile_key": vendor_lookup_key,



                                "vendor_category": current_vendor_ai_category



                            }



                            



                            # 踰꾪띁 珥덇린장)(?€湲장)곹뭹장)?대? ?ы븿장) 



                            _group_img_buf = []



                            _group_txt_buf = []



                            



                            self.add_log(f"  -> [대기상품 등록] 사진 {len(img_urls)}장 + 텍스트 대기 중 (다음은 보충 사진 병합 대기)", "INFO")



                            found_new = True  # 踰꾪띁장)蹂묓빀?섎뜑?쇰룄 '장)장)ぉ 諛쒓껄'?쇰줈 ?몄뇩 → 臾댄븳 ?ㅽ겕濡?諛⑹? 

                            continue

                            # 실제 상품 등록은 Pending Flush 경로에서 처리됩니다.







                        # [수정됨] for 루프 끝: pending 상품 즉시 등록



                        if _pending_product is not None and not found_new:



                            _pend_imgs_f = list(dict.fromkeys(_pending_product["img_urls"]))

                            _pend_imgs_f = [u for u in _pend_imgs_f if u not in _qr_candidate_urls]





                            _pend_text_f = apply_forbidden_words(_pending_product["raw_text"])



                            if len(_pend_imgs_f) >= 4 and _pend_text_f and not _stop_crawling_by_date:



                                self.add_log(f"  ✅ [즉시 등록] 대기 상품 등록 (사진 {len(_pend_imgs_f)}장)", "SUCCESS")



                                _pv = getattr(self, "current_vendor_title", "UnknownVendor")



                                _pp = "-"



                                _pp = _extract_price(_pend_text_f, _pv, current_vendor_ai_category, current_vendor_ai_rules)



                                processed_count += 1



                                _vi = get_korean_initial(_pv).lower()



                                try:



                                    import pricing_logic, datetime



                                    _bfx = float(trans_options.get("naver_fx", 195.0)) if trans_options else 195.0



                                    _gc = _guess_category(_pv, _pend_text_f)



                                    _cp = current_vendor_ai_category or _gc or (trans_options.get("category", "여성의류") if trans_options else "여성의류")



                                    try: _cv = float(_pp)



                                    except: _cv = 0.0



                                    _pt = f"{_pv} 상품"



                                    _pgc, _psp, _pdg, _pcl = pricing_logic.generate_product_code_and_price(_pv, _cv, _cp, _pt, _pend_text_f, _bfx)



                                    _pc = f"[{_vi}{_pp}] {_pgc}"



                                    _pft = f"[중국어원문]\n{_pend_text_f}\n\n{_pc}\n생성 {_pdg}"



                                    _ps = str(_psp)



                                except Exception:



                                    _pt = "item"; _pft = _pend_text_f; _ps = "0"; _pc = f"{_vi}{_pp}"; _pcl = ""



                                _psf = sanitize_path_component((_pt or "item").strip())



                                _pdr = os.path.join(dest_dir, f"{processed_count}_{_psf}")



                                os.makedirs(_pdr, exist_ok=True)



                                _pl = self._download_images_parallel(_pend_imgs_f, _pdr, prefix="", min_size=5120)



                                import datetime as _dt



                                if self.add_product_func and _pl:



                                    self.add_product_func({"title": _pt, "product_code": _pc, "sale_price": _ps, "price_input": _pp, "price_detected": bool(_pp and _pp != "-"), "raw_description": _pft, "original_chinese": _pend_text_f, "vendor_name": _pv, "vendor_id": vendor_lookup_id, "vendor_url": vendor_url, "vendor_profile_key": vendor_lookup_key, "vendor_category": current_vendor_ai_category, "image_urls": [], "image_server_urls": [], "local_image_dir": _pdr, "image_files": _pl, "local_image_paths": [os.path.join(_pdr, img) for img in _pl], "calc_log": _pcl, "created_at": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")})



                                self.add_log(f"  👉 {processed_count}/{target_count} 완료(즉시): {_pt} ({len(_pl)}장)", "SUCCESS")



                                _pending_product = None



                                found_new = True







                        import random as _r

                        if not found_new:

                            no_new_scroll_count += 1

                            self.add_log(f"  ⚠️ [스크롤 감시] 새 아이템 없음 (연속 {no_new_scroll_count}/5회)", "WARNING")

                            if no_new_scroll_count >= 5:

                                self.add_log(f"  🛑 [무한루프 방어] 연속 {no_new_scroll_count}회 새 상품 미감지. 현재 업체 크롤링을 종료합니다.", "WARNING")

                                break

                            scroll_amt = _r.randint(800, 1200)

                            page.mouse.wheel(0, scroll_amt)

                            page.mouse.move(_r.randint(300, 900), _r.randint(200, 600))

                            wait_ms = _r.randint(1800, 3000)

                        else:

                            no_new_scroll_count = 0  # 새 아이템 발견 시 카운터 리셋

                            scroll_amt = _r.randint(400, 800)

                            page.mouse.wheel(0, scroll_amt)

                            wait_ms = _r.randint(2000, 4500)

                        self.add_log(f"  ⏱️ 다음 스크롤까지 {wait_ms/1000:.1f}초 대기 (봇 감지 방어)", "INFO")

                        page.wait_for_timeout(wait_ms)



                    # ?봽 猷⑦봽 醫낅즺 →  留덉?留장)€湲장)곹뭹 ?뚮윭장) 

                    if _pending_product is not None:

                        _pend_imgs = list(dict.fromkeys(_pending_product["img_urls"]))

                        _pend_text = _pending_product["raw_text"]

                        if len(_pend_imgs) >= 4 and _pend_text and not _stop_crawling_by_date:

                            self.add_log(f"  -> [마지막 잔여 상품 확정: 총 {len(_pend_imgs)}장]", "SUCCESS")

                            _p_vendor_name = getattr(self, "current_vendor_title", "UnknownVendor")

                            _p_price_input = "-"

                            _p_code = trans_options.get("prefix", "AUTO") if trans_options else "AUTO"

                            

                            _p_price_input = _extract_price(_pend_text, _p_vendor_name, current_vendor_ai_category, current_vendor_ai_rules)

                            

                            # [수정됨] 단가 누락 시에도 등록 진행

                            if _p_price_input == "-" or _p_price_input == "0":

                                self.add_log(f"  ⚠️ [단가 미감지] 마지막 잔여 상품 단가 미감지. '-' 상태로 등록합니다.", "WARNING")

                            

                            processed_count += 1

                            

                            # [신규 추가] 업체코드 명시: 영문자음+숫자

                            _vendor_eng_initials = get_korean_initial(_p_vendor_name).lower()

                            _p_code = f"{_vendor_eng_initials}{_p_price_input}"

                            

                            _pc = re.search(r'(?:Item Number|Number|No|code|id.*?)\s*[:：-]?\s*([A-Za-z0-9]{5,10})', _pend_text, re.IGNORECASE)

                            if _pc:

                                _p_code = f"{_p_code}-{_pc.group(1)}".strip()

                            

                            try:

                                base_fx = float(trans_options.get("naver_fx", 195.0)) if trans_options else 195.0

                                guessed_cat = _guess_category(_p_vendor_name, _pend_text)

                                cat_p = guessed_cat if guessed_cat else (trans_options.get("category", "여성의류") if trans_options else "여성의류")

                                try: cost_p = float(_p_price_input)

                                except: cost_p = 0.0

                                _p_title = f"{_p_vendor_name} 상품"

                                _p_gen_code, _p_sale_price, _p_dg, _p_calc_log = pricing_logic.generate_product_code_and_price(

                                    _p_vendor_name, cost_p, cat_p, _p_title, _pend_text, base_fx)

                                _p_code = f"[{_vendor_eng_initials}{_p_price_input}] {_p_gen_code}"

                                _p_final_text = f"[중국어 원문]\n{_pend_text}\n\n{_p_code}\n생성 {_p_dg}"

                                _p_sale = str(_p_sale_price)

                            except Exception as _pe:

                                _p_title = "item"

                                _p_final_text = _pend_text

                                _p_sale = "0"

                                _p_calc_log = ""

                            _p_safe = sanitize_path_component((_p_title or "item").strip())

                            _p_dir = os.path.join(dest_dir, f"{processed_count}_{_p_safe}")

                            os.makedirs(_p_dir, exist_ok=True)

                            _p_local = self._download_images_parallel(_pend_imgs, _p_dir, prefix="", min_size=5120)

                            import datetime

                            if self.add_product_func and _p_local:

                                self.add_product_func({

                                    "title": _p_title, "product_code": _p_code,

                                    "sale_price": _p_sale, "price_input": _p_price_input,

                                    "price_detected": bool(_p_price_input and _p_price_input != "-"),

                                    "raw_description": _p_final_text, "original_chinese": _pend_text,

                                    "vendor_name": _p_vendor_name,

                                    "vendor_id": vendor_lookup_id,

                                    "vendor_url": vendor_url,

                                    "vendor_profile_key": vendor_lookup_key,

                                    "vendor_category": current_vendor_ai_category,

                                    "image_urls": [], "image_server_urls": [], "local_image_dir": _p_dir,

                                    "image_files": _p_local,

                                    "local_image_paths": [os.path.join(_p_dir, img) for img in _p_local],

                                    "calc_log": _p_calc_log,

                                    "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                                })

                            self.add_log(f"  👉 {processed_count}/{target_count} 완료 (마지막 대기상품): {_p_title} (사진 {len(_p_local)}장)", "SUCCESS")

                        _pending_product = None



                    if self.stop_flag:

                        self.add_log("강제 수집 종료", "WARNING")

                    else:

                        self.add_log("수집 정상 완료!", "INFO")

                    

                    try:

                        from backend.database import get_db

                        get_db().update_vendor_crawl_history(

                            vendor_id=vendor_lookup_id,

                            vendor_name=getattr(self, "current_vendor_title", vendor_lookup_id),

                            last_crawled_date=_date_boundary_str if '_date_boundary_str' in locals() and _date_boundary_str else "알수없음",

                            crawled_count=processed_count

                        )

                    except Exception as e:

                        self.add_log(f"업체 히스토리 저장 실패: {e}", "WARNING")

        except Exception as e:

            self.add_log(f"❌ 웨이상 엔진 치명적 오류: {e}", "ERROR")

            self.add_log(traceback.format_exc(), "ERROR")

            try:

                import sys

                sys.path.append(os.path.dirname(os.path.abspath(__file__)))

                from error_dumper import save_playwright_error_dump

                if 'page' in locals() and page:

                    dump_path = save_playwright_error_dump(page, "weishang_fatal")

                    if dump_path:

                        self.add_log(f"📸 에러 캡처 완료: {dump_path}", "INFO")

            except Exception as dmp_err:

                self.add_log(f"⚠️ 에러 캡처 실패: {dmp_err}", "WARNING")

        finally:
            self.close_browser()
            self._shutdown_pools()



    def sync_vendors(self) -> list:

        import traceback, json, os

        from playwright.sync_api import sync_playwright



        vendors = {}

        target_url = "https://www.szwego.com/static/index.html?t=1712852296766#/followed" 







        try:
            self.playwright_mgr = sync_playwright().start()
            self.add_log("[동기화] 웨이상 팔로우 피드에서 상점 목록 추출 시작...")
            has_auth = os.path.exists(self.auth_state_path)
            if not has_auth:
                self.add_log("❌ 저장된 로그인 정보가 없습니다. 먼저 계정을 연결해주세요.", "ERROR")
                return []



                



                self.browser = self.playwright_mgr.chromium.launch(
                    headless=False,
                    args=[
                        "--no-sandbox",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-features=ProtocolHandlerRegistry,WindowManagement,LocalFonts",
                        "--disable-notifications",
                        "--disable-popup-blocking"
                    ]
                )
                browser = self.browser



                self.context = self.browser.new_context(
                    storage_state=self.auth_state_path,
                    viewport={"width": 1280, "height": 800}
                )
                context = self.context



                



                # 沅뚰븳 ?앹뾽("장)湲곌린장)다른 → 諛장)쒕퉬?ㅼ뿉 ?≪꽭장) →  諛⑹?/?먮룞?덉슜 



                try:



                    context.grant_permissions([



                        "clipboard-read", 



                        "clipboard-write", 



                        "notifications", 



                        "geolocation"



                    ], origin="https://www.szwego.com")



                except Exception as ex:



                    self.add_log(f"  👉 일부 사이트 권한 자동허용 실패 (무시됨): {ex}", "WARNING")







                self.page = self.context.new_page()
                page = self.page







                # 媛뺤젣 ?앹뾽 李⑤떒 ?ㅽ겕由쏀듃 二쇱엯 (?щ＼ ?ㅼ씠?곕툕 ?덉슜李?諛⑹?) 



                page.add_init_script("""



                    window.getScreenDetails = undefined;



                    navigator.registerProtocolHandler = function(){};



                    if(window.Notification) { Notification.requestPermission = async () => 'denied'; }



                    const originalOpen = window.open;



                    window.open = function(url, ...args) {



                        if(typeof url === 'string' && !url.startsWith('http')) return null;



                        return originalOpen(url, ...args);



                    };



                """)





                self.add_log("  👉 피드 페이지 접속 중 (최대 60초 대기)...")

                page.goto(target_url, timeout=60000, wait_until="domcontentloaded")

                

                try:

                    # ?먮┛ ?ㅽ듃?뚰겕 ?섍꼍장)?꾪빐 ?ㅼ젣 ?곸젏 紐⑸줉(移쒓뎄 由ъ뒪장)장)?뚮뜑留곷맆 ?뚭퉴吏 理쒕? 60珥장)湲? 

                    page.wait_for_selector(".followed__shop-item", timeout=60000)

                    self.add_log("  👉 상점 목록 로딩 완료! 내부 코드 분석을 시작합니다.")

                except Exception:

                    self.add_log("  👉 60초 내에 연락처 항목을 찾지 못했습니다. 네트워크가 매우 느리거나 상점이 없을 수 있습니다.", "WARNING")



                self.add_log("  👉 전체 목록 스크롤 중 (스크롤 당 2초씩 대기)...")

                for _ in range(15): 

                    # ?섏씠吏 ?꾩껜 諛?由ъ뒪장)?대? 而⑦뀒?대꼫 媛뺤젣 ?ㅽ겕濡? 

                    page.evaluate("""

                        window.scrollBy(0, 1500);

                        var documentItems = document.querySelectorAll('div');

                        for(var i=0; i<documentItems.length; i++) {

                            if(documentItems[i].scrollHeight > documentItems[i].clientHeight) {

                                documentItems[i].scrollTop += 1500;

                            }

                        }

                    """)

                    page.wait_for_timeout(2000)



                self.add_log("  👉 React DOM에서 상점 고유 ID를 분석합니다...")

                # React DOM(Fiber) 속성을 탐색해 상점 ID와 이름 추출

                extracted_data = page.evaluate("""() => {

                    const items = document.querySelectorAll('.followed__shop-item');

                    const data = [];

                    items.forEach(el => {

                        let shopId = null;

                        const reactInstKey = Object.keys(el).find(k => k.startsWith('__reactInternalInstance$'));

                        if(reactInstKey) {

                            let fiber = el[reactInstKey];

                            let depth = 0;

                            while(fiber && depth < 10) {

                                try {

                                    if(fiber.memoizedProps) {

                                        const propsStr = JSON.stringify(fiber.memoizedProps);

                                        // ?뺢퇋장) Szwego ?곸젏 怨좎쑀 ID 留ㅼ묶 ('_'濡장)쒖옉, ?곷Ц?レ옄 → 25장)?댁긽)

                                        const match = propsStr.match(/(_[A-Za-z0-9_\\-]{25,})/);

                                        if(match) {

                                            shopId = match[1];

                                            break;

                                        }

                                    }

                                } catch(e) {}

                                fiber = fiber.return;

                                depth++;

                            }

                        }

                        const nameNode = el.querySelector('.followed__shop-name');

                        const name = nameNode ? nameNode.innerText.trim() : null;

                        if(name && shopId) {

                            data.push({name: name, id: shopId});

                        }

                    });

                    return data;

                }""")

                

                # 以묐났 ?쒓굅 諛?由ъ뒪장)蹂장) 

                # 기존 저장된 업체 목록(AI 속성 보존) 읽어오기

                vendor_file = "weishang_vendors.json"

                existing_vendors = {}

                try:

                    if os.path.exists(vendor_file):

                        with open(vendor_file, "r", encoding="utf-8") as f:

                            for v in json.load(f):

                                if "id" in v:

                                    existing_vendors[v["id"]] = v

                except Exception as e:

                    self.add_log(f"⚠️ 기존 업체 목록 읽기 실패: {e}", "WARNING")



                new_add_count = 0

                for item in extracted_data:

                    vendor_id = item["id"]

                    if vendor_id in existing_vendors:

                        existing_vendors[vendor_id]["name"] = item["name"][:30]

                        existing_vendors[vendor_id]["url"] = f"https://www.szwego.com/static/index.html?t=1712852296766#/shop_detail/{vendor_id}"

                    else:

                        existing_vendors[vendor_id] = {

                            "id": vendor_id,

                            "name": item["name"][:30],

                            "url": f"https://www.szwego.com/static/index.html?t=1712852296766#/shop_detail/{vendor_id}"

                        }

                        new_add_count += 1



                vendor_list = list(existing_vendors.values())

                self.add_log(f"✅ 총 {len(vendor_list)}개의 업체 정보를 추출했습니다.", "INFO")

                if new_add_count > 0:

                    self.add_log(f"🌟 기존 AI 분석 정보를 보존하며, 새로운 업체 {new_add_count}개를 추가했습니다.", "INFO")

                else:

                    self.add_log("💡 새로 추가된 업체가 없습니다. 기존 AI 분석 정보가 안전하게 보존되었습니다.", "INFO")



                with open(vendor_file, "w", encoding="utf-8") as f:

                    json.dump(vendor_list, f, ensure_ascii=False, indent=2)



                return vendor_list



        except Exception as e:
            self.add_log(f"❌ 상점 정보 동기화 중 오류: {e}", "ERROR")
            self.add_log(traceback.format_exc(), "ERROR")
            return []
        finally:
            self.close_browser()



    def profile_vendor_style(self, vendor_url: str, api_key: str) -> str:

        """업체 페이지를 여러 번 스크롤하여 대량의 텍스트 본문(최소 10페이지 분량)을 수집하고, Gemini로 포스팅 스타일 규칙을 도출한다."""

        import traceback

        try:

            from google import genai

            translator = genai.Client(api_key=api_key)

        except ImportError:

            self.add_log("⚠️ 'google-genai' 모듈이 설치되지 않아 분석이 불가능합니다.", "WARNING")

            return ""



        vendor_id_for_log = vendor_url.split('/')[-1] if '/' in vendor_url else "Unknown"

        self.add_log(f"🧠 [AI 프로파일러] 업체[{vendor_id_for_log}] 포스팅 스타일 분석을 시작합니다.")

        collected_texts = []

        

        try:
            from playwright.sync_api import sync_playwright
            self.playwright_mgr = sync_playwright().start()
            has_auth = os.path.exists(self.auth_state_path)
            if not has_auth:
                self.add_log("❌ [AI 프로파일러] 로그인 세션(auth_state.json)이 없습니다. 로그인이 필요합니다.", "ERROR")
                return ""

            self.browser = self.playwright_mgr.chromium.launch(headless=False, args=["--no-sandbox", "--window-size=400,600", "--window-position=-32000,-32000"])
            browser = self.browser
            self.context = browser.new_context(storage_state=self.auth_state_path)
            context = self.context
            self.page = context.new_page()
            page = self.page

            self.add_log(f"🚀 [AI 프로파일러] 업체 URL 진입: {vendor_url}")
            page.goto(vendor_url, timeout=60000, wait_until="networkidle")
            self.add_log("✅ 페이지 접속 완료, 스크롤링 및 데이터 수집 시작...")

            if True:
                # ?쒗뵆由장)꾪솚 ?쒕∼?ㅼ슫 踰꾪듉 ?꾨Ⅴ湲?(紐⑸줉酉? 

                try:

                    page.wait_for_timeout(2000)

                    switcher_clicked = page.evaluate("""() => {

                        let queries = ["i.icon-sanlie", "i[class*='templateSwitcher']", "i.icon-liebiao", ".icon-menu", "div[class*='layout'] i"];

                        for (let q of queries) {

                            let el = document.querySelector(q);

                            if (el && window.getComputedStyle(el).display !== 'none') { el.click(); return true; }

                        }

                        return false;

                    }""")

                    page.wait_for_timeout(2000)

                except Exception:

                    pass



                # ?ㅻ쭏장)?ㅽ겕濡? 理쒕? 15장) → ?붿냼가 2장)?곗냽 → ?앷린硫?議곌린 醫낅즺 

                max_scrolls = 15

                no_new_count = 0

                prev_height = 0

                for i in range(max_scrolls):

                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

                    page.wait_for_timeout(3000)  # 3珥장)湲?(lazy loading ?덉젙 蹂댁옣) 

                    cur_height = page.evaluate("document.body.scrollHeight")

                    self.add_log(f"🔽 스크롤 다운 ({i+1}/{max_scrolls})")

                    if cur_height == prev_height:

                        no_new_count += 1

                        if no_new_count >= 2:

                            self.add_log(f"✅ 더 이상 새 포스팅이 없어 스크롤 조기 종료 ({i+1}회차)")

                            break

                    else:

                        no_new_count = 0

                    prev_height = cur_height



                # ?붿냼 異붿텧 (BeautifulSoup ?쒖슜?쇰줈 ?덉젙장)媛뺥솕) 

                from bs4 import BeautifulSoup

                html = page.content()

                soup = BeautifulSoup(html, "html.parser")

                items = soup.find_all('div', class_=lambda c: c and ('normalItemContent' in c or 'w-1-3' in c or 'goods-item' in c))

                

                self.add_log(f"📦 DOM 요소 {len(items)}개 감지됨, 텍스트 추출 중...")

                

                for idx, item in enumerate(items):

                    try:

                        texts = item.find_all(string=True)

                        raw_text = " ".join([t.strip() for t in texts if t.strip()])

                        raw_text = raw_text.replace("download Edit Forwarding", "").replace("转发 编辑 下载", "").strip()

                        

                        # ?듭떖: ?대?吏 ?μ닔장)?④퍡 ?곗텧?섏뿬 ?쒗장)?뚯븙 

                        img_count = len(item.find_all('img'))

                        

                        if (raw_text and len(raw_text) > 5) or img_count > 0:

                            post_info = f"[포스팅 {idx+1}] 사진 {img_count}장 | 본문: {raw_text}"

                            if post_info not in collected_texts:

                                collected_texts.append(post_info)

                    except Exception:

                        pass

                

                browser.close()



                if not collected_texts:

                    self.add_log("⚠️ [AI 프로파일러] 추출된 본문 텍스트가 없습니다.", "WARNING")

                    return ""



                self.add_log(f"📊 총 {len(collected_texts)}개의 고유 포스팅 원문 수집 완료. AI 분석을 의뢰합니다.")

                

                # ?꾨＼?꾪듃 ?앹꽦 

                max_samples = 100

                combined_text = "\n\n---\n\n".join(collected_texts[:max_samples])

                

                # 留뚯빟 湲몄씠가 ?덈Т 湲몃㈃ (Gemini 3.1 Pro장)??⑸웾 而⑦뀓?ㅽ듃 吏장) 

                if len(combined_text) > 60000:

                    combined_text = combined_text[:60000]



                profile_prompt = f"""당신은 중국 웨이상/도매 앨범을 분석해 자동 크롤링과 한국어 상품글 생성을 안정화하는 데이터 분석 AI입니다.

아래 데이터는 특정 업체의 최신순 포스팅 시퀀스입니다. 각 포스팅은 사진 수와 원문 텍스트를 포함합니다.



[업체 포스팅 시퀀스]

{combined_text}

[업체 포스팅 시퀀스 끝]



분석 목표:

1. 이 업체가 어떤 상품군을 주로 다루는지 판단합니다.

2. 하나의 상품을 한 포스팅에 올리는지, 여러 포스팅으로 쪼개 올리는지 판단합니다.

3. 자동 크롤러가 상품 경계, 보충컷, 공지/광고, 가격 표기, 글 작성 스타일을 판단할 수 있는 규칙을 추출합니다.

4. 한국어 판매글을 만들 때 어떤 구성과 톤을 유지해야 하는지 정리합니다.



반드시 아래 JSON 필드만 반환하세요. 값이 확실하지 않으면 빈 문자열 또는 빈 배열을 사용하세요.

{{

  "category": "남성의류|여성의류|가방/지갑|신발|시계/잡화|공장모음|원도매모음|기타 중 하나",

  "posting_pattern": "단일 포스팅|분할 포스팅 중 하나",

  "analysis_reason": "왜 그렇게 판단했는지 한국어 1~2문장",

  "skip_conditions": ["크롤링에서 제외해야 할 공지/광고/QR/연락처 키워드"],

  "bundle_logic": "연속 포스팅을 하나의 상품으로 묶는 기준",

  "recommended_style": "한국어 판매글 작성 톤과 강조 포인트",

  "pricing_pattern": "가격/단가가 보통 어디에 어떤 표기로 나오는지 (주의: 9330270처럼 의미를 알 수 없는 7자리 이상의 긴 숫자가 있을 경우, 보통 앞자리는 품번이고 '맨 뒤 3자리'가 실제 단가인 경우가 매우 많습니다. 이를 반드시 분석에 반영하세요). 예: P88, W120, 긴 숫자 끝 3자리",

  "price_regex": "이 업체의 텍스트에서 단가를 정확하게 추출할 수 있는 Python 정규식 (반드시 단가 숫자부분이 캡처그룹 1번이어야 함. 예: r'P(\\d+)' 또는 r'\\d{4,}(\\d{3})$' 또는 빈 문자열)",

  "post_structure": "한국어 상품글에 유지해야 할 정보 순서. 예: 상품명→핵심특징→컬러→사이즈→배송→상품코드/가격",

  "grouping_rules": "새 상품 시작/이전 상품 보충컷을 가르는 규칙",

  "matching_rules": "사진/텍스트 기준으로 같은 상품인지 판단하는 규칙",

  "profile_rules": "번역 및 상품글 생성 시 최우선으로 참고할 업체별 종합 규칙",

  "boundary_signals": ["새 상품 시작으로 보기 쉬운 중국어 키워드"],

  "supplement_patterns": ["보충컷/상세컷/사이즈표로 보기 쉬운 중국어 키워드"],

  "avg_images_per_product": 0,

  "has_price": true

}}



중요:

- `profile_rules`는 실제 글 작성 AI에게 그대로 전달됩니다. 짧고 실행 가능한 규칙으로 작성하세요.

- `grouping_rules`, `matching_rules`는 자동 병합/분리 판단에 쓰입니다. 모호한 감상문이 아니라 조건문처럼 작성하세요.

- `skip_conditions`는 상품이 아닌 게시물만 걸러야 하므로 과도하게 넓은 단어는 넣지 마세요.

"""

                self.add_log(f"🧠 Gemini API로 초고속 핵심 분석 요청 중 (대상 업체: {vendor_id_for_log})...")

                res = translator.models.generate_content(

                    model='gemini-2.5-pro',

                    contents=[profile_prompt],

                    config=genai.types.GenerateContentConfig(

                        response_mime_type="application/json",

                        temperature=0.1

                    )

                )



                if res and res.text:

                    res_text = res.text.strip()

                    if res_text.startswith("```json"):

                        res_text = res_text[7:-3].strip()

                    elif res_text.startswith("```"):

                        res_text = res_text[3:-3].strip()

                    

                    try:

                        data = json.loads(res_text)

                        self.add_log(f"✨ AI 프로파일링 분석 완료! (카테고리: {data.get('category')}, 방식: {data.get('posting_pattern')})")

                        self.add_log(f"   💡 이유: {data.get('analysis_reason', '')[:50]}...")

                        return data

                    except json.JSONDecodeError:

                        self.add_log("⚠️ JSON 파싱 실패, 일반 텍스트로 처리합니다.", "WARNING")

                        return {"category": "미상", "posting_pattern": "단일 포스팅", "profile_rules": res_text}

                else:

                    self.add_log("⚠️ AI 분석 결과가 비어있습니다.", "WARNING")

                    return None



        except Exception as e:
            self.add_log(f"❌ 프로파일링 중 오류: {e}", "ERROR")
            self.add_log(traceback.format_exc(), "ERROR")
            return ""
        finally:
            self.close_browser()



