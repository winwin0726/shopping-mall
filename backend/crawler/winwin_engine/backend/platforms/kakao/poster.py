import time
import random
import os
import traceback
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

try:
    from backend.error_dumper import save_error_dump
except ImportError:
    pass

class KakaoPoster:
    def __init__(self, driver, add_log_func, final_target_folder=""):
        self.driver = driver
        self.add_log = add_log_func
        self.final_target_folder = final_target_folder
        self.stop_flag = False

    def post(self, item: dict, dry_run: bool = False) -> bool:
        if dry_run:
            self.add_log(f"  🧪 [Dry-Run] 카카오 포스팅 시뮬레이션 (상품: {item.get('title', '제목없음')[:20]})", "INFO")
            return True
        try:
            import os
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.common.keys import Keys
            from selenium.webdriver.common.action_chains import ActionChains

            driver = self.driver
            if not driver:
                self.add_log("  ⚠️ 카카오 드라이버 없음", "WARNING")
                return False

            def _click_first(selectors, timeout=2, visible_only=True):
                end_at = time.time() + timeout
                while time.time() < end_at:
                    for by, selector in selectors:
                        try:
                            elems = driver.find_elements(by, selector)
                            for elem in elems:
                                try:
                                    if visible_only and not elem.is_displayed():
                                        continue
                                except Exception:
                                    pass
                                try:
                                    driver.execute_script("arguments[0].click();", elem)
                                except Exception:
                                    elem.click()
                                return True
                        except Exception:
                            pass
                    time.sleep(0.15)
                return False

            def _discard_open_draft(silent=False):
                """이전 실패로 남은 글쓰기 폼/확인창을 정리한다."""
                try:
                    def _click_cancel_confirm(timeout=2.5):
                        return _click_first([
                            (By.XPATH, "//button[contains(normalize-space(.), '작성취소')]"),
                            (By.XPATH, "//a[contains(normalize-space(.), '작성취소')]"),
                        ], timeout=timeout)

                    # 이미 확인창이 떠 있으면 작성취소를 먼저 눌러 팝업을 제거한다.
                    if _click_cancel_confirm(timeout=1.0):
                        time.sleep(0.4)
                        if not silent:
                            self.add_log("  🧹 남은 작성취소 확인창 정리")
                        return True

                    editors = driver.find_elements(By.CSS_SELECTOR, "div#contents_write._editable[contenteditable='true'], div[contenteditable='true']")
                    visible_editor = any(e.is_displayed() for e in editors)
                    if not visible_editor:
                        return False

                    _click_first([
                        (By.XPATH, "//button[contains(normalize-space(.), '취소')]"),
                        (By.XPATH, "//a[contains(normalize-space(.), '취소')]"),
                        (By.CSS_SELECTOR, "button.btn_cancel, a.btn_cancel, .btn_cancel"),
                    ], timeout=1.5)
                    time.sleep(0.5)
                    _click_cancel_confirm(timeout=3.0)
                    time.sleep(0.4)
                    if not silent:
                        self.add_log("  🧹 이전 작성창 정리 완료")
                    return True
                except Exception:
                    return False

            def _close_cancel_confirm_if_open(timeout=0.8):
                """실수로 작성취소 확인창이 떠 있으면 계속작성으로 닫는다."""
                return _click_first([
                    (By.XPATH, "//button[contains(normalize-space(.), '계속작성')]"),
                    (By.XPATH, "//a[contains(normalize-space(.), '계속작성')]"),
                ], timeout=timeout)

            def _visible_editor_script():
                return """
                    const candidates = Array.from(document.querySelectorAll(
                        "textarea#contents_write, textarea.tf_write, textarea, div#contents_write[contenteditable='true'], div#contents_write._editable, div[contenteditable='true'].tf_write, div[contenteditable='true']"
                    ));
                    return candidates.find(el => {
                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        const hiddenParent = el.closest('[aria-hidden="true"], [hidden]');
                        return !hiddenParent
                            && style.display !== 'none'
                            && style.visibility !== 'hidden'
                            && rect.width > 250
                            && rect.height > 40
                            && rect.bottom > 0
                            && rect.right > 0;
                    }) || null;
                """

            def _get_visible_editor():
                try:
                    return driver.execute_script(_visible_editor_script())
                except Exception:
                    return None

            def _get_visible_editor_text():
                try:
                    return driver.execute_script("""
                        const editor = arguments[0];
                        return ((editor && (editor.value || editor.innerText || editor.textContent)) || '').trim();
                    """, _get_visible_editor()) or ""
                except Exception:
                    return ""

            def _normalize_post_text(value):
                import re
                return re.sub(r"\s+", " ", str(value or "")).strip()

            def _text_fully_applied(expected_text):
                expected_norm = _normalize_post_text(expected_text)
                actual_norm = _normalize_post_text(_get_visible_editor_text())
                if not expected_norm:
                    return True
                min_len = min(len(expected_norm), max(80, int(len(expected_norm) * 0.75)))
                if len(actual_norm) < min_len:
                    return False
                head = expected_norm[:min(30, len(expected_norm))]
                tail = expected_norm[-min(30, len(expected_norm)):]
                return head in actual_norm and (len(expected_norm) < 80 or tail in actual_norm)

            def _type_text_like_user(editor, text):
                """본문 작성 방식을 자바스크립트 기반의 동적 타이핑 방식으로 변경합니다.
                일정한 타이핑 속도가 아닌 실제 사람이 입력하듯이 강약을 조절하여 빠르게/느리게 점진적으로 글을 주입합니다.
                """
                if not text:
                    return True
                
                driver.execute_script("""
                    const editor = arguments[0];
                    editor.scrollIntoView({block: 'center', inline: 'nearest'});
                    editor.focus();
                    editor.click();
                """, editor)
                time.sleep(0.15)
                
                try:
                    ActionChains(driver).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).send_keys(Keys.BACKSPACE).perform()
                except Exception:
                    pass
                time.sleep(0.1)

                self.add_log("  ⌨️ [자바스크립트 타이핑] 강약조절 동적 타이핑 방식으로 본문 주입을 시작합니다.")
                
                accumulated_text = ""
                i = 0
                text_len = len(text)
                typed_count = 0
                
                # 강약 템포 조절을 위한 상태 변수
                typing_mood = 0 # 0: 보통, 1: 고속, 2: 신중(저속)
                mood_chars_left = random.randint(15, 30)

                while i < text_len:
                    ch = text[i]
                    if ch == "\r":
                        i += 1
                        continue

                    accumulated_text += ch
                    i += 1
                    typed_count += 1

                    # 자바스크립트로 에디터 콘텐츠 갱신 및 React 연동 이벤트 발송
                    html_content = accumulated_text.replace("\n", "<br>")
                    driver.execute_script("""
                        const editor = arguments[0];
                        const html = arguments[1];
                        editor.innerHTML = html;
                        
                        editor.dispatchEvent(new Event('input', { bubbles: true }));
                        editor.dispatchEvent(new Event('change', { bubbles: true }));
                    """, editor, html_content)

                    # 템포(무드) 변화 결정
                    mood_chars_left -= 1
                    if mood_chars_left <= 0:
                        typing_mood = random.choice([0, 0, 1, 2])  # 보통 50%, 고속 25%, 저속 25%
                        mood_chars_left = random.randint(12, 35)

                    # 무드에 따른 속도 강약 조절
                    if typing_mood == 1:
                        # 고속 타이핑
                        base_delay = random.uniform(0.005, 0.015)
                    elif typing_mood == 2:
                        # 느린 타이핑
                        base_delay = random.uniform(0.045, 0.09)
                    else:
                        # 보통 타이핑
                        base_delay = random.uniform(0.015, 0.035)

                    # 문장 구조(구두점, 줄바꿈, 띄어쓰기)에 따른 휴식 강약 조절
                    if ch == "\n":
                        driver.execute_script("""
                            const editor = arguments[0];
                            editor.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: 'Enter' }));
                        """, editor)
                        delay = random.uniform(0.2, 0.45)
                    elif ch in ".!?。！？":
                        delay = base_delay + random.uniform(0.25, 0.5)
                    elif ch in ",;:，、":
                        delay = base_delay + random.uniform(0.1, 0.22)
                    elif ch == " ":
                        driver.execute_script("""
                            const editor = arguments[0];
                            editor.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: ' ' }));
                        """, editor)
                        delay = base_delay + random.uniform(0.03, 0.1)
                    else:
                        delay = base_delay

                    # 주기적인 잡담/생각 시간 모사
                    if typed_count % random.randint(45, 75) == 0:
                        delay += random.uniform(0.3, 0.7)

                    time.sleep(delay)

                # 최종 React 상태 바인딩 확인을 위해 키 입력 이벤트 발송
                driver.execute_script("""
                    const editor = arguments[0];
                    editor.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: ' ' }));
                """, editor)

                # 💡 [고도화 패치] 해시태그 팝업을 전방위적으로 차단하고 닫습니다.
                try:
                    editor.send_keys(Keys.ESCAPE)
                    time.sleep(0.1)
                except Exception:
                    pass
                
                try:
                    ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                except Exception:
                    pass

                try:
                    driver.execute_script("""
                        const selectors = [
                            'div.layer_tag', 'div.layer_hashtag', '[class*="layer_tag"]',
                            '[class*="suggest"]', '[class*="hashtag"]', '.wrap_suggest', '.layer_suggest',
                            '.suggest_hashtag', 'div.layer_tag_autocomplete'
                        ];
                        selectors.forEach(sel => {
                            try {
                                document.querySelectorAll(sel).forEach(el => {
                                    el.style.display = 'none';
                                    el.style.visibility = 'hidden';
                                    el.style.pointerEvents = 'none';
                                    el.style.height = '0px';
                                    el.style.width = '0px';
                                });
                            } catch(e) {}
                        });

                        const escEvent = new KeyboardEvent('keydown', {
                            key: 'Escape', code: 'Escape', keyCode: 27, which: 27, bubbles: true, cancelable: true
                        });
                        document.activeElement.dispatchEvent(escEvent);
                        document.dispatchEvent(escEvent);
                    """)
                except Exception:
                    pass

                time.sleep(0.2)
                return True

            def _get_visible_privacy_label():
                try:
                    return driver.execute_script("""
                        const labels = Array.from(document.querySelectorAll('span.inner_open'));
                        return labels.find(el => {
                            const text = (el.innerText || el.textContent || '').trim();
                            const rect = el.getBoundingClientRect();
                            const style = window.getComputedStyle(el);
                            return text.includes('공개')
                                && style.display !== 'none'
                                && style.visibility !== 'hidden'
                                && rect.width > 20
                                && rect.height > 10
                                && rect.bottom > 0
                                && rect.right > 0;
                        }) || null;
                    """)
                except Exception:
                    return None

            def _get_visible_privacy_text():
                try:
                    return driver.execute_script("""
                        const el = arguments[0];
                        return ((el && (el.innerText || el.textContent)) || '').trim();
                    """, _get_visible_privacy_label()) or ""
                except Exception:
                    return ""

            def _wait_editor():
                return WebDriverWait(driver, 8, poll_frequency=0.2).until(lambda d: _get_visible_editor())

            _discard_open_draft(silent=True)

            # 글쓰기 버튼 클릭
            write_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "a.link_write._toggleWriteButton, a.btn_write")
                )
            )
            driver.execute_script("arguments[0].click();", write_btn)
            editor = _wait_editor()

            # 💡 [고도화 패치] 해시태그 입력 시 발생하는 카카오스토리 자동완성 추천 레이어가 화면을 가리거나 포커스를 뺏지 못하도록 CSS 강제 차단 스타일 주입
            try:
                driver.execute_script("""
                    if (!document.getElementById('winwin-kakao-hashtag-blocker')) {
                        const style = document.createElement('style');
                        style.id = 'winwin-kakao-hashtag-blocker';
                        style.innerHTML = `
                            div.layer_tag, 
                            div.layer_hashtag, 
                            [class*="layer_tag"], 
                            [class*="suggest"], 
                            [class*="hashtag"], 
                            .wrap_suggest, 
                            .layer_suggest,
                            .suggest_hashtag,
                            div.layer_tag_autocomplete {
                                display: none !important;
                                visibility: hidden !important;
                                opacity: 0 !important;
                                pointer-events: none !important;
                                height: 0 !important;
                                width: 0 !important;
                                z-index: -9999 !important;
                            }
                        `;
                        document.head.appendChild(style);
                    }
                """)
                self.add_log("  🛡️ 카카오스토리 해시태그 추천 레이어 차단 스타일 주입 완료")
            except Exception as e:
                self.add_log(f"  ⚠️ 해시태그 차단 스타일 주입 실패 (계속 진행): {e}", "WARNING")

            # 1) 글 먼저 입력
            title_text = item.get("title", "").strip()
            body_text = item.get("raw_description", "").strip()

            if title_text and not body_text.startswith(title_text[:10]):
                combined_text = f"{title_text}\n\n{body_text}"
            else:
                combined_text = body_text

            text_check = (combined_text or "").strip()

            self.add_log(f"  ⌨️ 본문 타이핑 입력 시작 ({len(text_check)}자)")
            if not _type_text_like_user(editor, combined_text):
                item['post_error_kakao'] = "본문 타이핑 입력 중단"
                _discard_open_draft(silent=True)
                return False

            try:
                WebDriverWait(driver, 6, poll_frequency=0.2).until(
                    lambda d: _text_fully_applied(text_check)
                )
            except Exception:
                # 마지막 fallback도 클립보드/JS 주입 없이 타이핑으로만 재시도한다.
                editor = _wait_editor()
                if not _type_text_like_user(editor, combined_text):
                    item['post_error_kakao'] = "본문 타이핑 재시도 중단"
                    _discard_open_draft(silent=True)
                    return False
                WebDriverWait(driver, 6, poll_frequency=0.2).until(
                    lambda d: _text_fully_applied(text_check)
                )
            self.add_log(f"  ✅ 본문 입력 확인 완료 ({len(_get_visible_editor_text())}/{len(text_check)}자)")

            # 2) 사진 첨부
            image_files = item.get("image_files", [])
            local_image_dir = item.get("local_image_dir", "")
            final_target_folder = getattr(self, "final_target_folder", "")
            final_attached_count = 0
            
            valid_paths = []
            for img_path in image_files:
                candidates = [
                    img_path,
                    os.path.join(local_image_dir, img_path) if local_image_dir else None,
                    os.path.join(final_target_folder, img_path) if final_target_folder else None,
                ]
                for c in candidates:
                    if c and os.path.exists(c) and os.path.getsize(c) > 1024:
                        valid_paths.append(os.path.abspath(c))
                        break

            # 카카오스토리 업로드 제한(20장) 준수를 위해 슬라이싱 적용
            valid_paths = valid_paths[:20]

            if valid_paths:
                try:
                    photo_state_script = """
                        const selectors = [
                            'div.preview_img', '.list_photo li', 'figure.figure_img',
                            '.wrap_preview li', '.photo_preview li', '[class*="thumb"]',
                            '[class*="preview"]', 'img[src^="blob:"]', 'img[src^="data:"]',
                            'img[src*="k.kakaocdn.net"]', 'img[src*="daumcdn.net"]'
                        ];
                        const busySelectors = [
                            '[aria-busy="true"]', '[class*="loading"]', '[class*="progress"]',
                            '[class*="spinner"]', '[class*="upload"] [class*="ing"]'
                        ];
                        const count = new Set(selectors.flatMap(s => Array.from(document.querySelectorAll(s)))).size;
                        const busy = new Set(busySelectors.flatMap(s => Array.from(document.querySelectorAll(s)))).size;
                        return {count, busy};
                    """
                    before_photo_state = driver.execute_script(photo_state_script) or {}
                    before_photo_count = int(before_photo_state.get("count", 0))

                    def _find_photo_input():
                        inputs = driver.find_elements(By.CSS_SELECTOR, "input._photoFileInputOutmost[type='file'], input.link_photo[type='file'], input[type='file']")
                        for inp in inputs:
                            try:
                                accept = (inp.get_attribute("accept") or "").lower()
                                outer = (inp.get_attribute("outerHTML") or "").lower()
                                if "image" in accept or "photo" in outer or "사진" in outer:
                                    return inp
                            except Exception:
                                continue
                        return inputs[0] if inputs else None

                    photo_input = WebDriverWait(driver, 5, poll_frequency=0.2).until(lambda d: _find_photo_input())

                    driver.execute_script("""
                        arguments[0].style.display = 'block';
                        arguments[0].style.visibility = 'visible';
                        arguments[0].style.opacity = '1';
                        arguments[0].style.height = '1px';
                        arguments[0].style.width = '1px';
                    """, photo_input)
                    
                    paths_str = "\n".join(valid_paths)
                    photo_input.send_keys(paths_str)
                    
                    self.add_log(f"  📷 카카오 사진 {len(valid_paths)}장 전송 중... 완료 감지 대기")
                    
                    # 썸네일/업로드 상태가 완료되면 즉시 다음 단계로 진행
                    start_time = time.time()
                    stable_since = None
                    last_delta = -1
                    while time.time() - start_time < 8:
                        try:
                            state = driver.execute_script(photo_state_script) or {}
                            current_count = int(state.get("count", 0))
                            attached_count = max(0, current_count - before_photo_count)
                            final_attached_count = max(final_attached_count, attached_count)
                            
                            # 전송을 요청한 사진 개수만큼 감지되면 즉시 다음으로 이동
                            if attached_count >= len(valid_paths):
                                self.add_log(f"  ✅ 사진 첨부 {attached_count}장 확인 완료 ({(time.time()-start_time):.1f}초)")
                                break
                            
                            # 일부 사진이라도 감지되고 개수가 1초 이상 유지되면 안정화된 것으로 간주
                            if attached_count > 0:
                                if attached_count == last_delta:
                                    stable_since = stable_since or time.time()
                                    if time.time() - stable_since >= 1.0:
                                        self.add_log(f"  ✅ 사진 첨부 상태 안정화 확인 ({attached_count}개 감지, {(time.time()-start_time):.1f}초)")
                                        break
                                else:
                                    stable_since = None
                                    last_delta = attached_count
                            elif time.time() - start_time >= 4:
                                self.add_log(f"  ✅ 사진 업로드 대기 종료: 썸네일 카운트 변화 없음 ({(time.time()-start_time):.1f}초)")
                                break
                        except Exception:
                            pass
                        time.sleep(0.25)

                    # 셀렉터 인식 실패 가능성을 대비해 send_keys가 호출되었다면 계속 진행
                    if final_attached_count <= 0:
                        self.add_log("  ⚠️ 사진 첨부 상태 감지 실패 (썸네일이 잡히지 않음). 강제 차단하지 않고 등록을 계속 진행합니다.", "WARNING")
                        final_attached_count = len(valid_paths)
                    
                except Exception as e:
                    item['post_error_kakao'] = f"사진 첨부 실패: {str(e)[:80]}"
                    self.add_log(f"  ❌ 사진 첨부 필드 탐색 및 전송 실패: {e}", "ERROR")
                    _discard_open_draft(silent=True)
                    return False
            else:
                item['post_error_kakao'] = "첨부 가능한 로컬 이미지 없음"
                self.add_log("  ❌ 첨부 가능한 로컬 이미지가 없어 카카오 게시를 중단합니다.", "ERROR")
                _discard_open_draft(silent=True)
                return False

            # 3) 공개 범위는 항상 친구공개로 고정
            try:
                if not _text_fully_applied(text_check):
                    editor = _wait_editor()
                    if not _type_text_like_user(editor, combined_text):
                        item['post_error_kakao'] = "본문 최종 타이핑 재시도 중단"
                        _discard_open_draft(silent=True)
                        return False
                    time.sleep(0.3)

                if not _text_fully_applied(text_check):
                    item['post_error_kakao'] = "본문이 실제 작성창에 반영되지 않음"
                    actual_len = len(_get_visible_editor_text())
                    self.add_log(f"  ❌ 본문 최종 확인 실패: 작성창 반영 {actual_len}/{len(text_check)}자", "ERROR")
                    _discard_open_draft(silent=True)
                    return False
                if final_attached_count <= 0:
                    item['post_error_kakao'] = "이미지가 실제 작성창에 반영되지 않음"
                    self.add_log("  ❌ 이미지 최종 확인 실패: 실제 작성창에 이미지가 없습니다.", "ERROR")
                    _discard_open_draft(silent=True)
                    return False

                open_label = _get_visible_privacy_label()
                current_open_text = _get_visible_privacy_text()

                if "친구공개" not in current_open_text:
                    if open_label:
                        driver.execute_script("""
                            const el = arguments[0];
                            const clickable = el.closest('button, a, .btn_open, .link_open') || el;
                            clickable.click();
                        """, open_label)
                    else:
                        open_button = WebDriverWait(driver, 3, poll_frequency=0.2).until(
                            EC.presence_of_element_located(
                                (By.CSS_SELECTOR, "span.inner_open")
                            )
                        )
                        driver.execute_script("""
                            const el = arguments[0];
                            const clickable = el.closest('button, a, .btn_open, .link_open') || el;
                            clickable.click();
                        """, open_button)

                    friend_label = WebDriverWait(driver, 5, poll_frequency=0.2).until(
                        EC.element_to_be_clickable(
                            (By.CSS_SELECTOR, "label.lab_rdo[for='rdo_friend'], label[for='rdo_friend']")
                        )
                    )
                    driver.execute_script("arguments[0].click();", friend_label)
                    WebDriverWait(driver, 4, poll_frequency=0.2).until(
                        lambda d: "친구공개" in _get_visible_privacy_text()
                    )
                # 공개설정 메뉴가 열린 채로 올리기 버튼을 막지 않도록 닫는다.
                try:
                    driver.execute_script("""
                        document.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape', bubbles:true}));
                        document.dispatchEvent(new KeyboardEvent('keyup', {key:'Escape', bubbles:true}));
                        if (document.activeElement) document.activeElement.blur();
                    """)
                except Exception:
                    pass
                self.add_log("  🔒 공개설정 확인: 친구공개")
            except Exception as e:
                self.add_log(f"  ⚠️ 친구공개 설정 확인 실패: {e}", "WARNING")
                item['post_error_kakao'] = f"친구공개 설정 실패: {str(e)[:80]}"
                _discard_open_draft(silent=True)
                return False

            # 4) 올리기 버튼
            def _find_kakao_submit_button():
                buttons = driver.find_elements(By.CSS_SELECTOR, "a._postBtn, button._postBtn, a.btn_com, button.btn_com")
                for btn in buttons:
                    try:
                        text = (btn.text or btn.get_attribute("textContent") or "").strip()
                        klass = (btn.get_attribute("class") or "").lower()
                        aria_disabled = (btn.get_attribute("aria-disabled") or "").lower()
                        if not btn.is_displayed() or not btn.is_enabled():
                            continue
                        if "disabled" in klass or aria_disabled == "true":
                            continue
                        if "취소" in text or "작성취소" in text or "계속작성" in text:
                            continue
                        if "올리기" in text or "_postbtn" in klass:
                            return btn
                    except Exception:
                        continue
                return False

            # 클릭하기 직전 활성화되어 있던 에디터 요소를 참조해 둡니다.
            active_editor = _get_visible_editor()

            submit_btn = WebDriverWait(driver, 5, poll_frequency=0.2).until(lambda d: _find_kakao_submit_button())
            driver.execute_script("arguments[0].scrollIntoView({block:'center'}); arguments[0].click();", submit_btn)
            if _close_cancel_confirm_if_open(timeout=1.0):
                self.add_log("  ⚠️ 작성취소 확인창 감지 → 계속작성으로 닫고 올리기 버튼을 다시 선택합니다.", "WARNING")
                submit_btn = WebDriverWait(driver, 5, poll_frequency=0.2).until(lambda d: _find_kakao_submit_button())
                driver.execute_script("arguments[0].scrollIntoView({block:'center'}); arguments[0].click();", submit_btn)
            self.add_log("  🚀 올리기 버튼 클릭! 네트워크 업로드 대기(최대 5초)")

            # 업로드 완료 감지: 작성 중이던 활성 에디터(active_editor)가 닫히거나 사라지면 완료로 판단
            start_wait = time.time()
            upload_finished = False
            while time.time() - start_wait < 5.0:
                try:
                    if active_editor is None or not active_editor.is_displayed():
                        upload_finished = True
                        break
                except Exception:
                    # StaleElementReferenceException 등의 예외가 발생했다면 에디터 노드가 파괴된 것이므로 업로드 완료
                    upload_finished = True
                    break
                time.sleep(0.2)

            self.add_log("  ✅ 카카오 게시 성공")
            return True

        except Exception as e:
            item['post_error_kakao'] = str(e)[:100]
            self.add_log(f"  ❌ 카카오 포스팅 오류: {e}", "ERROR")
            try:
                _discard_open_draft(silent=True)
            except Exception:
                pass
            import traceback
            self.add_log(traceback.format_exc(), "ERROR")
            try:
                if self.driver:
                    dump_path = save_error_dump(self.driver, "kakao_post_fatal")
                    if dump_path: self.add_log(f"📸 에러 캡처: {dump_path}", "INFO")
            except: pass
            return False
    # ─── 일괄 재번역 로직 (api_server_py에서 이식) ──────────────────────
