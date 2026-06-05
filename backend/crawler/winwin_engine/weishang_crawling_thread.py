import os
import re
import datetime
import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from PyQt5.QtCore import QThread, pyqtSignal

def sanitize_path_component(name: str) -> str:
    name = re.sub(r'["\'<>:\\/|?*]', "_", name)
    name = name.replace("\r", "").replace("\n", " ")
    return name.strip()

def _download_image(args):
    """모듈 레벨 평행 이미지 다운로더 (ThreadPoolExecutor 용)"""
    idx, img_url, local_dir_path, product_code = args
    try:
        resp = requests.get(img_url, timeout=8)
        if resp.status_code == 200:
            img_ext = ".jpg"
            if "png" in img_url.lower(): img_ext = ".png"
            elif "gif" in img_url.lower(): img_ext = ".gif"
            fname = f"{product_code}_{idx+1}{img_ext}"
            img_path = os.path.join(local_dir_path, fname)
            with open(img_path, "wb") as f:
                f.write(resp.content)
            return (idx, fname)
    except Exception:
        pass
    return (idx, None)

class WeishangCrawlingThread(QThread):
    progress_signal = pyqtSignal(int)
    log_signal = pyqtSignal(str)
    result_signal = pyqtSignal(dict)
    finished_signal = pyqtSignal(str)

    def __init__(self, vendor_url, vendor_name, target_count, dest_dir, headless_mode, trans_options, parent=None):
        super().__init__(parent)
        self.vendor_url = vendor_url
        self.vendor_name = vendor_name
        self.target_count = target_count
        self.dest_dir = dest_dir
        self.headless_mode = headless_mode
        self.trans_options = trans_options or {}
        self.stop_flag = False
        
        self.auth_state_path = "auth_state.json"
        
        # winwin59와의 코드 호환성을 위해 category_mapping 로드
        from category_data import category_mapping
        # 만약 trans_options 카테고리 이름이 있으면 연결해주기 위해
        self.category_mapping = category_mapping

    def filter_bmp(self, text):
        return ''.join(ch for ch in text if ord(ch) <= 0xFFFF)

    def run(self):
        import datetime  # 실행 스코프에 확실한 datetime 모듈 기록
        import traceback
        # 취약한 dynamic import를 run() 시작부비로 이동 (loop내 매번 실행 대신)
        from category_data import generate_product_code, CATEGORY_KEYWORDS
        from winwin59 import compute_sale_price

        # 날짜 미리 계산 (playwright 블록 진입 전에 계산해 스코프 문제 원천차단)
        _today = datetime.datetime.now()
        _today_str = _today.strftime("%Y%m%d")

        translator = None
        if self.trans_options.get("enable"):
            gemini_key = self.trans_options.get("api_key", "").strip()
            if gemini_key:
                try:
                    from google import genai
                    translator = genai.Client(api_key=gemini_key)
                except ImportError:
                    self.log_signal.emit("⚠️ 'google-genai' 모듈이 설치되지 않아 번역이 불가능합니다.")
                    self.log_signal.emit("💡 터미널에서 'pip install google-genai' 명령어를 실행해주세요.")
                except Exception as e:
                    self.log_signal.emit(f"⚠️ Gemini 클라이언트 생성 실패: {e}")
            else:
                self.log_signal.emit("⚠️ Gemini API Key가 비어있습니다. 번역이 생략됩니다.")

        # ===== 브라우저 구동 =====
        try:
            with sync_playwright() as p:
                self.log_signal.emit("[1] 웨이상 크롬 엔진을 시작합니다.")
                has_auth = os.path.exists(self.auth_state_path)
                
                browser = p.chromium.launch(
                    headless=self.headless_mode,
                    args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
                )
                
                if has_auth:
                    self.log_signal.emit("[1-2] 기존에 저장된 웨이상 로그인(세션) 정보를 불러옵니다.")
                    context = browser.new_context(storage_state=self.auth_state_path)
                else:
                    self.log_signal.emit("[1-2] ⚠️ 저장된 웨이상 로그인 정보가 없습니다.")
                    context = browser.new_context()

                page = context.new_page()
                
                # ===== QR 로그인 로직 =====
                LOGIN_URL = "https://www.szwego.com/static/index.html?link_type=pc_login#/pc_login"
                if not has_auth:
                    self.log_signal.emit(f"[2] 웨이상 로그인 전용 페이지로 접속합니다.")
                    try:
                        page.goto(LOGIN_URL, timeout=60000)
                    except Exception as e:
                        self.log_signal.emit(f"❌ 로그인 페이지 접속 실패: {e}")
                        self.finished_signal.emit("접속 실패")
                        return

                    self.log_signal.emit("❗ 브라우저 화면에 뜬 QR 코드를 스마트폰 미상앨범/위챗으로 스캔해주세요.")
                    self.log_signal.emit("⏳ 로그인이 완료되어 화면이 넘어갈 때까지 대기합니다 (최대 3분).")
                    try:
                        page.wait_for_url(lambda url: "pc_login" not in url, timeout=180000)
                        self.log_signal.emit("✅ 로그인 완료! 안정화를 위해 3초 대기합니다.")
                        page.wait_for_timeout(3000)
                        context.storage_state(path=self.auth_state_path)
                        self.log_signal.emit("웨이상 로그인 세션(auth_state.json)을 저장했습니다.")
                    except Exception as e:
                        self.log_signal.emit("❌ 로그인 대기 시간 초과 또는 화면 전환 감지 실패.")
                        self.finished_signal.emit("로그인 실패")
                        return
                else:
                    self.log_signal.emit("[2] 기존 로그인 정보를 사용합니다.")

                # ===== 수집 대상 URL로 이동 =====
                self.log_signal.emit(f"[3] 목표 업체 앨범 페이지 진입: {self.vendor_url}")
                try:
                    page.goto(self.vendor_url, timeout=60000)
                except Exception as e:
                    self.log_signal.emit(f"❌ 업체 페이지 접속 실패: {e}")
                    self.finished_signal.emit("접속 실패")
                    return

                try:
                    page.wait_for_selector("img, .goods-list, .goods-item, .album-list, .error-page", timeout=5000)
                    if page.locator(".error-page").is_visible() or "未开通相册网址" in page.content():
                        self.log_signal.emit("🚫 해당 업체는 '웹 상점(PC 앨범)' 기능을 열어두지 않았습니다.")
                        self.finished_signal.emit("접근 불가")
                        return
                except Exception as e:
                    self.log_signal.emit("⚠️ 요소 대기 시간 초과 (계속 진행합니다).")

                # ===== 목록(리스트) 뷰 모드 전환 =====
                try:
                    self.log_signal.emit("[4] 목록 보기 버튼 클릭 시도...")
                    page.wait_for_timeout(2000)  # SPA 렌더링 대기

                    # 1단계: 템플릿 전환 버튼 (3개 셀렉터 중 첫 번째 성공한 것 사용)
                    switcher_clicked = False
                    for sel in ["i.icon-pengyouquandongtai", "i[class*='icon-pengyouquandongtai']", "i[class*='pengyouquan']"]:
                        try:
                            # 요소가 DOM에 렌더링될 때까지 대기
                            page.wait_for_selector(sel, state="attached", timeout=3000)
                            # Playwright의 엄격한 click() 대신 JS 강제 클릭 (겹침/투명도 무시)
                            page.evaluate(f"document.querySelector('{sel}').click()")
                            self.log_signal.emit(f"  ✅ 템플릿 전환 버튼 클릭 완료 ({sel})")
                            page.wait_for_timeout(800)
                            switcher_clicked = True
                            break
                        except Exception:
                            continue
                    if not switcher_clicked:
                        self.log_signal.emit("  ⚠️ 템플릿 전환 버튼을 찾지 못했습니다.")

                    # 2단계: 목록 뷰 선택 (3개 셀렉터 호환)
                    list_clicked = False
                    for sel in ["div.index-module_highightFrame_tiqeg", "div[class*='highightFrame']", "div[class*='tiqeg']"]:
                        try:
                            page.wait_for_selector(sel, state="attached", timeout=3000)
                            page.evaluate(f"document.querySelector('{sel}').click()")
                            self.log_signal.emit(f"  ✅ 목록 뷰 선택 완료 ({sel})")
                            page.wait_for_timeout(1500)
                            list_clicked = True
                            break
                        except Exception:
                            continue
                    if not list_clicked:
                        self.log_signal.emit("  ⚠️ 목록 뷰 아이콘을 찾지 못했습니다. 기본 뷰로 계속 진행합니다.")

                except Exception as e:
                    self.log_signal.emit(f"  ⚠️ 뷰 전환 중 오류 (계속 진행): {e}")

                self.log_signal.emit("🎉 데이터 수집을 시작합니다...")
                page.wait_for_timeout(2000)

                # --- 본격적인 스크롤 및 데이터 수집 ---
                processed_count = 0
                target_count = self.target_count if self.target_count > 0 else 999999
                seen_items = set()

                # 규칙 파일을 루프 전 1회만 읽어 캐싱 (매 아이템마다 재읽기 방지)
                rules_text = ""
                try:
                    with open("양식적용 프로젝트규칙1.txt", "r", encoding="utf-8") as f:
                        rules_text = f.read()
                except Exception:
                    pass

                while processed_count < target_count and not self.stop_flag:
                    html = page.content()
                    soup = BeautifulSoup(html, "html.parser")
                    items = soup.find_all('div', class_=lambda c: c and 'normalItemContent' in c)
                    
                    found_new = False
                    for item in items:
                        if self.stop_flag: break
                        
                        texts = item.find_all(string=True)
                        raw_text = " ".join([t.strip() for t in texts if t.strip()])
                        raw_text = raw_text.replace("download Edit Forwarding", "").strip()
                        raw_text = raw_text.replace("转发 编辑 下载", "").strip()
                        raw_text = self.filter_bmp(raw_text)
                        
                        if not raw_text: continue
                            
                        item_hash = raw_text[:50]
                        if item_hash not in seen_items:
                            seen_items.add(item_hash)
                            
                            imgs = item.find_all('img')
                            img_urls = []
                            for img in imgs:
                                src = img.get('src')
                                if src:
                                    clean_url = src.split("?")[0]
                                    img_urls.append(clean_url)
                                    
                            price_word = "0"
                            words = raw_text.split()
                            for w in words:
                                if "￥" in w or "¥" in w:
                                    try:
                                        p_val = float(re.sub(r'[^\d.]', '', w))
                                        price_word = str(p_val)
                                    except:
                                        pass
                                    break

                            final_text = raw_text
                            final_price = price_word
                            
                            # Gemini 번역 적용
                            if translator and self.trans_options.get("enable"):
                                try:
                                    selected_cat = self.trans_options.get("category", "남성의류")
                                    naver_fx = self.trans_options.get("naver_fx", 195.0)
                                    prefix = self.trans_options.get("prefix", "AUTO")
                                    
                                    prompt = f"""내가 제공하는 [프로젝트 규칙]과 [입력 파라미터]를 바탕으로, 아래 주어진 [중국어 원본 텍스트]를 가공하여 완벽한 한국어 쇼핑뫰 형태의 텍스트 결과물 1개만 반환해.
[프로젝트 규칙]
{rules_text}

[입력 파라미터]
- 처리해야 할 카테고리: {selected_cat}
- 네이버 기준환율(naver_fx): {naver_fx}
- 업체코드(prefix): {prefix}

[중국어 원본 텍스트]
{raw_text[:4000]}

[출력 시 엄격한 주의사항]
- 오직 '규칙'에 맞게 완성된 문서 텍스트 한 덩어리만 반환해야 한다. 부가 설명 금지.
"""
                                    response = translator.models.generate_content(
                                        model='gemini-2.5-flash',
                                        contents=prompt,
                                    )
                                    if response and response.text:
                                        final_text = response.text.strip()
                                        final_price = "0"
                                except Exception as e:
                                    self.log_signal.emit(f"  ⚠️ 번역 오류: {e}")

                            # 기존 winwin59 포맷에 맞춘 결과 딕셔너리 생성
                            # (product_code, date_folder 등은 process_data 시점에 생성되거나 여기서 임시 부여)
                            from category_data import generate_product_code, CATEGORY_KEYWORDS
                            selected_cat_text = self.trans_options.get("category", "기타")
                            
                            # 기본코드 획득 (추정)
                            base_info = CATEGORY_KEYWORDS.get(selected_cat_text, {})
                            basic_code = base_info.get("기본", {}).get("code", "0000")
                            
                            # 고유코드 생성
                            product_code = generate_product_code(basic_code, basic_code)
                            date_folder = _today_str  # 사전 계산된 날짜 문자열 사용
                            found_new = True

                            safe_title = sanitize_path_component(final_text.splitlines()[0][:15].strip()) if final_text.splitlines() else "item"
                            if not safe_title: safe_title = "item"
                            item_dir_name = f"{processed_count + 1}_{safe_title}"
                            local_dir_path = os.path.join(self.dest_dir, item_dir_name)
                            os.makedirs(local_dir_path, exist_ok=True)
                            
                            # 1. 텍스트 임시 저장 
                            with open(os.path.join(local_dir_path, "발견텍스트.txt"), "w", encoding="utf-8") as f:
                                f.write(final_text)

                            # 2. 이미지 병렬 다운로드
                            local_img_names = []
                            download_args = [(i, u, local_dir_path, product_code) for i, u in enumerate(img_urls)]
                            
                            with ThreadPoolExecutor(max_workers=5) as executor:
                                futures = {executor.submit(_download_image, arg): arg[0] for arg in download_args}
                                results = {}
                                for future in as_completed(futures):
                                    idx, fname = future.result()
                                    if fname:
                                        results[idx] = fname
                            
                            for i in sorted(results):
                                local_img_names.append(results[i])

                            # UI 전달
                            computed_price = compute_sale_price(final_price, selected_cat_text) if final_price != "0" else 0

                            result_item = {
                                "title": final_text.splitlines()[0] if final_text else "제목없음",
                                "raw_description": final_text,
                                "image_files": local_img_names,
                                "sale_price": computed_price,
                                "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "product_code": product_code,
                                "basic_code": basic_code,
                                "date_folder": date_folder,
                                "local_image_dir": local_dir_path  # 향후 업로드 쓰레드가 사진을 찾을 위치
                            }
                            
                            self.result_signal.emit(result_item)
                            processed_count += 1
                            try:
                                self.progress_signal.emit(processed_count)
                            except RuntimeError:
                                pass  # 위젯 삭제 시 안전하게 지나침
                            self.log_signal.emit(f"  👉 {processed_count}번째 수집 [사진 {len(local_img_names)}장]: {final_text[:20]}...")

                    # 스크롤 (브라우저가 닫혔을 경우 안전하게 종료)
                    try:
                        if not found_new:
                            page.mouse.wheel(0, 1200)
                            page.wait_for_timeout(600)
                        else:
                            page.mouse.wheel(0, 900)
                            found_new = False
                        page.wait_for_timeout(800)
                    except Exception as scroll_err:
                        err_msg = str(scroll_err)
                        if "closed" in err_msg or "Target" in err_msg:
                            self.log_signal.emit("🛑 브라우저가 닫혀 수집을 중단합니다.")
                            self.stop_flag = True  # while 루프 즉시 탈출
                        else:
                            raise  # 예상 못한 오류는 상위 except로 전달

                if self.stop_flag:
                    self.log_signal.emit("🛑 수집 중단됨")
                    self.finished_signal.emit("사용자 중지")
                else:
                    self.log_signal.emit("✅ 목표 수집 완료")
                    self.finished_signal.emit("완료")

        except Exception as e:
            tb = traceback.format_exc()
            self.log_signal.emit(f"❌ 웨이상 엔진 오류: {e}")
            # 로그 UI에서 잘리는 문제를 피해 파일로 traceback 저장
            try:
                with open("weishang_error.log", "w", encoding="utf-8") as f:
                    f.write(f"Error: {e}\n\n{tb}")
                self.log_signal.emit("홀 파일에 저장됨: weishang_error.log")
            except Exception:
                pass
            self.finished_signal.emit(f"오류: {e}")
