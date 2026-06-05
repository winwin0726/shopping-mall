import os
import time
import re
import glob
import requests
import shutil
import hashlib
from urllib.parse import quote
from datetime import datetime, timedelta
from PyQt5.QtCore import QThread, pyqtSignal
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys


class BandCrawlingThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    result_signal = pyqtSignal(dict)
    finished_signal = pyqtSignal(int)

    def __init__(self, driver, start_date, end_date, max_count,
                 selected_cat_text, target_folder, transform_function=None, parent=None):
        super().__init__(parent)
        self.driver = driver
        self.start_date = start_date
        self.end_date = end_date
        self.max_count = max_count
        self.selected_cat_text = selected_cat_text
        self.target_folder = target_folder
        self.stop_flag = False
        self.transform_function = transform_function
        self._last_collected_image_urls = []

    def log(self, message):
        self.log_signal.emit(message)

    # ----------------------------------------------------------------
    # 날짜 파싱
    # ----------------------------------------------------------------
    def extract_post_date(self, post_elem):
        TIME_SELECTORS = [
            "div.postHeader time",
            "div._postHeader time",
            "div.uAuthorInfo time",
            "header time",
            "time.time",
            "time",
        ]
        for sel in TIME_SELECTORS:
            try:
                for elem in post_elem.find_elements(By.CSS_SELECTOR, sel):
                    dt_attr = elem.get_attribute("datetime") or ""
                    text = elem.text.strip()
                    parsed = self.parse_date(dt_attr) or self.parse_date(text)
                    if parsed:
                        return parsed
            except Exception:
                pass
        return None

    def parse_date(self, text):
        if not text:
            return None
        try:
            m = re.match(r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})', text)
            if m:
                return datetime(int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]))
            rel = re.match(r'(\d+)\s*(초|분|시간|일|주|개월|년)\s*전', text)
            if rel:
                n, unit = int(rel[1]), rel[2]
                now = datetime.now()
                d = {'초': timedelta(seconds=n), '분': timedelta(minutes=n),
                     '시간': timedelta(hours=n), '일': timedelta(days=n),
                     '주': timedelta(weeks=n), '개월': timedelta(days=n*30),
                     '년': timedelta(days=n*365)}
                return now - d.get(unit, timedelta(0))
            m2 = re.search(
                r'(?:(\d{4})년\s*)?(\d{1,2})월\s*(\d{1,2})일\s*(오전|오후)\s*(\d{1,2}):(\d{2})', text)
            if m2:
                y = int(m2[1]) if m2[1] else datetime.now().year
                mo, d2 = int(m2[2]), int(m2[3])
                ampm, h, mi = m2[4], int(m2[5]), int(m2[6])
                if ampm == '오후' and h < 12: h += 12
                elif ampm == '오전' and h == 12: h = 0
                return datetime(y, mo, d2, h, mi)
            if '오늘' in text:
                return datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
            if '어제' in text:
                return (datetime.now() - timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
                
            m3 = re.search(r'(?:(\d{4})\.\s*)?(\d{1,2})\.\s*(\d{1,2})\.\s*(?:(오전|오후)\s*)?(\d{1,2}):(\d{2})', text)
            if m3:
                y = int(m3.group(1)) if m3.group(1) else datetime.now().year
                mo, d2 = int(m3.group(2)), int(m3.group(3))
                ampm = m3.group(4)
                h, mi = int(m3.group(5)), int(m3.group(6))
                if ampm == '오후' and h < 12: h += 12
                elif ampm == '오전' and h == 12: h = 0
                return datetime(y, mo, d2, h, mi)
                
            m4 = re.search(r'(?:(\d{4})\.\s*)?(\d{1,2})\.\s*(\d{1,2})\.', text)
            if m4:
                y = int(m4.group(1)) if m4.group(1) else datetime.now().year
                return datetime(y, int(m4.group(2)), int(m4.group(3)), 12, 0)
        except Exception as e:
            self.log(f"날짜 파싱 실패 [{text}]: {e}")
        return None

    # ----------------------------------------------------------------
    # 이미지 다운로드 공통 함수
    # ----------------------------------------------------------------
    def _make_session(self):
        """Selenium 쿠키를 이식한 requests 세션 생성"""
        session = requests.Session()
        try:
            ua = self.driver.execute_script("return navigator.userAgent;")
        except Exception:
            ua = 'Mozilla/5.0'
        session.headers.update({
            'User-Agent': ua,
            'Referer': 'https://band.us/',
            'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
        })
        try:
            for cookie in self.driver.get_cookies():
                session.cookies.set(
                    cookie['name'], cookie['value'],
                    domain=cookie.get('domain', ''))
        except Exception:
            pass
        return session

    def _download_url(self, session, url, dest_path):
        """단일 이미지 URL → 파일 저장. 성공 시 True."""
        try:
            resp = session.get(url, timeout=20, stream=True)
            if resp.status_code == 200:
                content = b''.join(resp.iter_content(8192))
                if len(content) > 500:
                    with open(dest_path, 'wb') as f:
                        f.write(content)
                    return True
                else:
                    self.log(f"  ⚠️ 응답 너무 작음({len(content)}B): {url[:60]}")
            else:
                self.log(f"  ❌ HTTP {resp.status_code}: {url[:60]}")
        except Exception as e:
            self.log(f"  ❌ 다운로드 오류: {e}")
        return False

    def _normalize_image_url(self, src):
        """Return a stable product-image URL, or empty string for UI/profile images."""
        src = (src or "").strip()
        if not src.startswith("http"):
            return ""

        lowered = src.lower()
        blocked_tokens = (
            "emoji", "profile", "sticker", "blank", "favicon",
            "sprite", "loading", "default_profile", "ico_"
        )
        if any(token in lowered for token in blocked_tokens):
            return ""

        if "pstatic.net" not in lowered and "campmobile" not in lowered:
            return ""

        return src.split("?", 1)[0].split("#", 1)[0]

    def _is_non_product_image_element(self, elem, url=""):
        """Filter Band/profile/logo UI images before URL collection."""
        try:
            meta = self.driver.execute_script("""
                const el = arguments[0];
                const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : {};
                const chunks = [];
                let p = el;
                for (let i = 0; p && i < 6; i++, p = p.parentElement) {
                    chunks.push([
                        p.tagName || '',
                        p.id || '',
                        String(p.className || ''),
                        p.getAttribute('role') || '',
                        p.getAttribute('aria-label') || '',
                        p.getAttribute('title') || '',
                        p.getAttribute('alt') || ''
                    ].join(' '));
                }
                return {
                    w: Math.round(rect.width || 0),
                    h: Math.round(rect.height || 0),
                    naturalW: el.naturalWidth || 0,
                    naturalH: el.naturalHeight || 0,
                    alt: el.getAttribute('alt') || '',
                    title: el.getAttribute('title') || '',
                    aria: el.getAttribute('aria-label') || '',
                    context: chunks.join(' ').slice(0, 1600)
                };
            """, elem) or {}
        except Exception:
            meta = {}

        text = " ".join([
            str(url or ""),
            str(meta.get("alt", "")),
            str(meta.get("title", "")),
            str(meta.get("aria", "")),
            str(meta.get("context", "")),
        ]).lower()

        blocked = [
            "profile", "avatar", "author", "user", "member", "cover", "logo",
            "bandlogo", "band_logo", "profileimage", "profile_image",
            "프로필", "작성자", "밴드 로고", "밴드logo", "winwin"
        ]
        if any(token in text for token in blocked):
            return True

        w = int(meta.get("naturalW") or meta.get("w") or 0)
        h = int(meta.get("naturalH") or meta.get("h") or 0)
        if w and h and (w < 120 or h < 120):
            return True
        return False

    def _image_dhash(self, image_path):
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                img = img.convert("L").resize((9, 8))
                pixels = list(img.getdata())
            bits = []
            for row in range(8):
                start = row * 9
                for col in range(8):
                    bits.append(1 if pixels[start + col] > pixels[start + col + 1] else 0)
            value = 0
            for bit in bits:
                value = (value << 1) | bit
            return value
        except Exception:
            return None

    def _hamming(self, a, b):
        try:
            return (a ^ b).bit_count()
        except Exception:
            return 999

    def _looks_like_winwin_logo_file(self, image_path):
        """Best-effort local filter for the recurring WINWIN/Band logo image."""
        try:
            from PIL import Image, ImageStat
            with Image.open(image_path) as img:
                img = img.convert("RGB")
                w, h = img.size
                if w < 180 or h < 180:
                    return True

                small = img.resize((96, 96))
                pixels = list(small.getdata())
                total = len(pixels)
                light = 0
                blue_green = 0
                dark = 0
                for r, g, b in pixels:
                    if r > 185 and g > 185 and b > 185:
                        light += 1
                    if (b > 105 or g > 125) and r < 120 and abs(g - b) < 120:
                        blue_green += 1
                    if r < 65 and g < 65 and b < 65:
                        dark += 1

                light_ratio = light / total
                blue_green_ratio = blue_green / total
                dark_ratio = dark / total

                # The recurring WINWIN logo is a light square splash with blue/green mark.
                if light_ratio > 0.45 and blue_green_ratio > 0.05 and dark_ratio < 0.22:
                    return True

                hero_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web-ui", "src", "assets", "hero.png")
                if os.path.exists(hero_path):
                    h1 = self._image_dhash(image_path)
                    h2 = self._image_dhash(hero_path)
                    if h1 is not None and h2 is not None and self._hamming(h1, h2) <= 18:
                        return True
        except Exception:
            return False
        return False

    def _filter_saved_non_product_images(self, saved, post_img_dir):
        if not saved:
            return saved
        kept = []
        for filename in saved:
            path = os.path.join(post_img_dir, filename)
            if self._looks_like_winwin_logo_file(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
                self.log(f"  🧹 비상품 로고 이미지 제외: {filename}")
                continue
            kept.append(filename)

        if len(kept) == len(saved):
            return kept

        renamed = []
        for idx, filename in enumerate(kept):
            old_path = os.path.join(post_img_dir, filename)
            ext = os.path.splitext(filename)[1] or ".jpg"
            new_name = f"img_{idx+1:03d}{ext}"
            new_path = os.path.join(post_img_dir, new_name)
            if filename != new_name:
                try:
                    if os.path.exists(new_path):
                        os.remove(new_path)
                    os.rename(old_path, new_path)
                    filename = new_name
                except Exception:
                    pass
            renamed.append(filename)
        return renamed

    def _hash_text(self, text):
        return hashlib.md5((text or "").encode("utf-8", errors="ignore")).hexdigest()

    def _make_post_key(self, post_elem):
        """Build a stable key for a feed post even when DOM indexes change."""
        parts = []
        try:
            for attr in ("data-post-no", "data-post-id", "data-feed-no", "data-uiseq", "id"):
                value = post_elem.get_attribute(attr) or ""
                if value:
                    parts.append(f"{attr}:{value}")

            try:
                links = post_elem.find_elements(By.CSS_SELECTOR, "a[href]")
                for link in links[:6]:
                    href = (link.get_attribute("href") or "").split("?", 1)[0]
                    if href and "band.us" in href:
                        parts.append(href)
            except Exception:
                pass

            try:
                text = self.driver.execute_script("return arguments[0].innerText;", post_elem) or ""
            except Exception:
                text = post_elem.text or ""
            text = re.sub(r"\s+", " ", text).strip()
            if text:
                parts.append(text[:700])

            try:
                image_parts = []
                for img in post_elem.find_elements(By.CSS_SELECTOR, "img")[:10]:
                    normalized = self._normalize_image_url(img.get_attribute("src") or "")
                    if normalized and normalized not in image_parts:
                        image_parts.append(normalized)
                parts.extend(image_parts[:6])
            except Exception:
                pass
        except Exception:
            pass

        if not parts:
            try:
                return f"webelement:{post_elem.id}"
            except Exception:
                return ""
        return self._hash_text("|".join(parts))

    def _make_content_key(self, raw_text, image_urls):
        text = re.sub(r"\s+", " ", raw_text or "").strip()
        normalized_urls = []
        for url in image_urls or []:
            normalized = self._normalize_image_url(url) or (url or "").split("?", 1)[0]
            if normalized and normalized not in normalized_urls:
                normalized_urls.append(normalized)
        if not text and not normalized_urls:
            return ""
        return self._hash_text(text[:900] + "|" + "|".join(normalized_urls[:10]))

    def _navigate_to_selected_band_board(self):
        """Move to the selected Band hashtag board before crawling."""
        category = (self.selected_cat_text or "").strip()
        if not category:
            return
        try:
            cur_url = self.driver.current_url or ""
            m = re.search(r"/band/(\d+)", cur_url)
            if not m:
                self.log(f"⚠️ 밴드 번호를 URL에서 찾지 못해 현재 페이지에서 크롤링합니다: {cur_url[:90]}")
                return

            band_no = m.group(1)
            encoded_category = quote(category, safe="")
            target_url = f"https://www.band.us/band/{band_no}/hashtag/{encoded_category}"
            if f"/band/{band_no}/hashtag/{encoded_category}" in cur_url:
                self.log(f"✅ 선택 게시판 URL 확인: #{category}")
                return

            self.log(f"➡️ 선택 게시판으로 이동: #{category} ({band_no})")
            self.driver.get(target_url)
            end_at = time.time() + 25
            while time.time() < end_at and not self.stop_flag:
                try:
                    if self.driver.find_elements(By.CSS_SELECTOR, "article._postMainWrap, div.cCard > article.cContentsCard._postMainWrap"):
                        self.log(f"✅ 선택 게시판 로딩 완료: #{category}")
                        return
                    body_text = self.driver.execute_script("return document.body ? document.body.innerText : ''") or ""
                    if f"#{category}" in body_text and "로딩 중입니다" not in body_text:
                        self.log(f"✅ 선택 게시판 텍스트 감지: #{category}")
                        return
                except Exception:
                    pass
                time.sleep(0.5)
            self.log(f"⚠️ 선택 게시판 로딩 확인 지연: #{category}. 현재 DOM 기준으로 계속합니다.")
        except Exception as e:
            self.log(f"⚠️ 선택 게시판 이동 실패: {str(e)[:120]}")

    def _scroll_feed_once(self, post_selector=None):
        """Scroll the actual Band feed container, not only document.body."""
        try:
            result = self.driver.execute_script("""
                const postSelector = arguments[0];
                const root = document.scrollingElement || document.documentElement || document.body;
                const posts = postSelector ? Array.from(document.querySelectorAll(postSelector)) : [];
                const lastPost = posts.length ? posts[posts.length - 1] : null;
                const viewportStep = Math.max(window.innerHeight * 1.25, 1100);
                const targets = [];
                const seen = new Set();

                function addTarget(el, reason) {
                    if (!el || seen.has(el)) return;
                    seen.add(el);
                    const room = (el.scrollHeight || 0) - (el.clientHeight || 0);
                    const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : { left: 0, top: 0, width: window.innerWidth, height: window.innerHeight };
                    targets.push({ el, reason, room, rect });
                }

                function isScrollable(el) {
                    if (!el) return false;
                    if (el === root || el === document.body || el === document.documentElement) return true;
                    const s = getComputedStyle(el);
                    const room = (el.scrollHeight || 0) - (el.clientHeight || 0);
                    return room > 80 && /(auto|scroll|overlay)/.test(s.overflowY + s.overflow);
                }

                if (lastPost) {
                    try { lastPost.scrollIntoView({ block: 'end', inline: 'nearest' }); } catch (e) {}
                    let p = lastPost.parentElement;
                    while (p && p !== document.documentElement) {
                        if (isScrollable(p)) addTarget(p, 'ancestor');
                        p = p.parentElement;
                    }
                }

                addTarget(root, 'root');
                for (const el of document.querySelectorAll('main, section, article, div, ul')) {
                    const room = (el.scrollHeight || 0) - (el.clientHeight || 0);
                    if (room < 120) continue;
                    let containsPosts = false;
                    try { containsPosts = postSelector && el.querySelector(postSelector); } catch (e) {}
                    const className = String(el.className || '').toLowerCase();
                    const feedLike = containsPosts || /feed|post|card|list|scroll|content|body/.test(className);
                    if (feedLike || targets.length < 4) addTarget(el, containsPosts ? 'post-container' : 'scrollable');
                }

                targets.sort((a, b) => {
                    const aPost = a.reason === 'post-container' || a.reason === 'ancestor' ? 1 : 0;
                    const bPost = b.reason === 'post-container' || b.reason === 'ancestor' ? 1 : 0;
                    return (bPost - aPost) || (b.room - a.room);
                });

                let moved = false;
                const used = [];
                for (const item of targets.slice(0, 8)) {
                    const el = item.el;
                    const before = el === root ? (window.pageYOffset || root.scrollTop || 0) : (el.scrollTop || 0);

                    if (el === root) {
                        window.scrollBy(0, viewportStep);
                    } else {
                        el.scrollTop = Math.min(el.scrollHeight, before + Math.max(el.clientHeight * 1.15, viewportStep));
                    }

                    const rect = item.rect;
                    const x = Math.max(20, Math.min(window.innerWidth - 20, rect.left + Math.min(rect.width / 2, 500)));
                    const y = Math.max(20, Math.min(window.innerHeight - 20, rect.top + Math.min(rect.height / 2, 500)));
                    try {
                        el.dispatchEvent(new WheelEvent('wheel', { bubbles: true, cancelable: true, deltaY: viewportStep, clientX: x, clientY: y }));
                        document.dispatchEvent(new WheelEvent('wheel', { bubbles: true, cancelable: true, deltaY: viewportStep, clientX: x, clientY: y }));
                    } catch (e) {}

                    const after = el === root ? (window.pageYOffset || root.scrollTop || 0) : (el.scrollTop || 0);
                    if (Math.abs(after - before) > 2) moved = true;
                    used.push({ reason: item.reason, before: Math.round(before), after: Math.round(after), room: Math.round(item.room) });
                }

                if (lastPost) {
                    try { lastPost.scrollIntoView({ block: 'end', inline: 'nearest' }); } catch (e) {}
                }
                return { moved, used, postCount: posts.length };
            """, post_selector or "")
            return bool(result and result.get("moved"))
        except Exception:
            try:
                ActionChains(self.driver).send_keys(Keys.PAGE_DOWN).perform()
                return True
            except Exception:
                return False

    def _force_band_feed_bottom_scroll(self, post_selector=None):
        """Advance Band feed containers one chunk at a time so lazy loaders can fire."""
        try:
            result = self.driver.execute_script("""
                const postSelector = arguments[0];
                const root = document.scrollingElement || document.documentElement || document.body;
                const posts = postSelector ? Array.from(document.querySelectorAll(postSelector)) : [];
                const lastPost = posts.length ? posts[posts.length - 1] : null;
                const selectors = [
                    'div.searchResultList',
                    'div[data-viewname="DSearchResultView"]',
                    'div[class*="search"]',
                    'div[class*="Search"]',
                    'div.postWrap._postListRegion',
                    'div.postWrap',
                    'section.boardList',
                    'main#content',
                    '#content',
                    '#container',
                    '#wrap'
                ];
                const seen = new Set();
                const targets = [];

                function add(el, reason) {
                    if (!el || seen.has(el)) return;
                    seen.add(el);
                    targets.push({ el, reason });
                }

                for (const sel of selectors) {
                    try { add(document.querySelector(sel), sel); } catch (e) {}
                }
                if (lastPost) {
                    let p = lastPost.parentElement;
                    while (p && p !== document.documentElement) {
                        add(p, 'last-post-parent');
                        p = p.parentElement;
                    }
                }
                add(root, 'root');

                let moved = false;
                const used = [];
                const step = Math.max(window.innerHeight * 0.95, 760);
                for (const item of targets.slice(0, 12)) {
                    const el = item.el;
                    const before = el === root ? (window.pageYOffset || root.scrollTop || 0) : (el.scrollTop || 0);
                    const room = el === root
                        ? Math.max(0, (root.scrollHeight || 0) - window.innerHeight)
                        : Math.max(0, (el.scrollHeight || 0) - (el.clientHeight || 0));
                    try {
                        if (el === root) {
                            window.scrollBy(0, step);
                        } else if (room > 0) {
                            el.scrollTop = Math.min(el.scrollHeight, before + step);
                        }
                    } catch (e) {}
                    const after = el === root ? (window.pageYOffset || root.scrollTop || 0) : (el.scrollTop || 0);
                    if (Math.abs(after - before) > 2) moved = true;
                    used.push({ reason: item.reason, before: Math.round(before), after: Math.round(after), room: Math.round(room) });
                }

                return { moved, used, postCount: posts.length };
            """, post_selector or "")
            return result or {}
        except Exception:
            return {}

    def _get_feed_wheel_point(self, post_selector):
        """Find a reliable viewport point where Band feed wheel events should land."""
        try:
            return self.driver.execute_script("""
                const postSelector = arguments[0];
                const root = document.scrollingElement || document.documentElement || document.body;
                const posts = postSelector ? Array.from(document.querySelectorAll(postSelector)) : [];
                const lastPost = posts.length ? posts[posts.length - 1] : null;

                function clamp(value, min, max) {
                    return Math.max(min, Math.min(max, value));
                }

                function roomOf(el) {
                    if (!el) return 0;
                    if (el === root || el === document.body || el === document.documentElement) {
                        return Math.max(0, (root.scrollHeight || 0) - window.innerHeight);
                    }
                    return Math.max(0, (el.scrollHeight || 0) - (el.clientHeight || 0));
                }

                function isScrollable(el) {
                    if (!el) return false;
                    if (el === root || el === document.body || el === document.documentElement) return roomOf(root) > 40;
                    const style = getComputedStyle(el);
                    return roomOf(el) > 80 && /(auto|scroll|overlay)/.test(style.overflowY + style.overflow);
                }

                let target = null;
                let reason = "viewport";
                let bestRoom = -1;

                if (lastPost) {
                    let p = lastPost.parentElement;
                    while (p && p !== document.documentElement) {
                        const room = roomOf(p);
                        if (isScrollable(p) && room > bestRoom) {
                            target = p;
                            reason = "post-ancestor";
                            bestRoom = room;
                        }
                        p = p.parentElement;
                    }
                }

                if (!target) {
                    for (const el of document.querySelectorAll("main, section, div, ul")) {
                        let containsPosts = false;
                        try { containsPosts = postSelector && el.querySelector(postSelector); } catch (e) {}
                        const room = roomOf(el);
                        const className = String(el.className || "").toLowerCase();
                        const feedLike = containsPosts || /feed|post|card|list|scroll|content|body/.test(className);
                        if (feedLike && isScrollable(el) && room > bestRoom) {
                            target = el;
                            reason = containsPosts ? "post-container" : "feed-like";
                            bestRoom = room;
                        }
                    }
                }

                if (!target) {
                    target = root;
                    reason = "root";
                    bestRoom = roomOf(root);
                }

                let rect;
                if (target === root || target === document.body || target === document.documentElement) {
                    rect = { left: 0, top: 0, width: window.innerWidth, height: window.innerHeight };
                } else {
                    rect = target.getBoundingClientRect();
                    if (!rect || rect.width < 20 || rect.height < 20) {
                        rect = { left: 0, top: 0, width: window.innerWidth, height: window.innerHeight };
                    }
                }

                const x = Math.round(clamp(rect.left + rect.width * 0.5, 30, window.innerWidth - 30));
                const y = Math.round(clamp(rect.top + rect.height * 0.82, 80, window.innerHeight - 40));
                return {
                    x,
                    y,
                    reason,
                    room: Math.round(bestRoom),
                    postCount: posts.length,
                    pageY: Math.round(window.pageYOffset || root.scrollTop || 0)
                };
            """, post_selector or "")
        except Exception:
            return {
                "x": 500,
                "y": 700,
                "reason": "fallback",
                "room": 0,
                "postCount": 0,
                "pageY": 0,
            }

    def _dispatch_feed_wheel(self, post_selector, times=5, delta=1500):
        """Send real Chrome wheel input; Band lazy loading often reacts to this better than JS scrollTop."""
        point = self._get_feed_wheel_point(post_selector) or {}
        x = int(point.get("x") or 500)
        y = int(point.get("y") or 700)
        used_cdp = False

        for _ in range(max(1, times)):
            try:
                self.driver.execute_cdp_cmd("Input.dispatchMouseEvent", {
                    "type": "mouseWheel",
                    "x": x,
                    "y": y,
                    "deltaX": 0,
                    "deltaY": delta,
                    "modifiers": 0,
                    "pointerType": "mouse",
                })
                used_cdp = True
                time.sleep(0.32)
            except Exception:
                try:
                    ActionChains(self.driver).scroll_by_amount(0, delta).perform()
                    time.sleep(0.32)
                except Exception:
                    try:
                        self.driver.execute_script(
                            "window.dispatchEvent(new WheelEvent('wheel', {bubbles:true,cancelable:true,deltaY:arguments[0],clientX:arguments[1],clientY:arguments[2]}));",
                            delta, x, y
                        )
                        time.sleep(0.32)
                    except Exception:
                        pass
        point["used_cdp"] = used_cdp
        return point

    def _click_feed_load_more(self, post_selector):
        """Click bottom feed load-more controls, excluding post text/photo more buttons."""
        try:
            buttons = self.driver.find_elements(
                By.CSS_SELECTOR,
                "button, a, div[role='button'], span[role='button'], div[class*='More'], div[class*='more'], span[class*='More'], span[class*='more']"
            )
        except Exception:
            return False

        candidates = []
        for elem in buttons:
            try:
                if not self._visible(elem):
                    continue
                text = (elem.text or elem.get_attribute("aria-label") or elem.get_attribute("title") or "").strip()
                class_name = (elem.get_attribute("class") or "").lower()
                lowered_text = text.lower()
                if not (
                    "더보기" in text or "더 보기" in text or "더 많은" in text or
                    "다음" in text or "결과" in text or "이전" in text or
                    "more" in lowered_text or "load" in class_name or "more" in class_name or
                    "next" in class_name or "prev" in class_name
                ):
                    continue
                inside_post = self.driver.execute_script(
                    "return !!arguments[0].closest(arguments[1]);",
                    elem, post_selector
                )
                if inside_post:
                    continue
                rect = self.driver.execute_script("""
                    const r = arguments[0].getBoundingClientRect();
                    return { x: r.left, y: r.top, w: r.width, h: r.height };
                """, elem) or {}
                if rect.get("y", 0) < 0 or rect.get("y", 0) < self.driver.execute_script("return window.innerHeight * 0.45;"):
                    continue
                candidates.append((rect.get("y", 0), elem, text[:30] or class_name[:30]))
            except Exception:
                pass

        for _, elem, label in sorted(candidates, key=lambda item: item[0], reverse=True)[:3]:
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", elem)
                time.sleep(0.2)
                if self._click_element(elem):
                    self.log(f"📜 피드 하단 로드 버튼 클릭: {label}")
                    time.sleep(1.8)
                    return True
            except Exception:
                pass
        return False

    def _scroll_until_new_posts(self, post_selector, processed_keys, attempts=8):
        stable_rounds = 0
        last_signature = ""
        any_moved = False
        for scroll_try in range(attempts):
            self._close_open_layers()
            try:
                posts_before = self.driver.find_elements(By.CSS_SELECTOR, post_selector)
                if posts_before:
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'end', inline:'nearest'});", posts_before[-1])
                    time.sleep(0.25)
            except Exception:
                posts_before = []

            moved = self._scroll_feed_once(post_selector)
            force_info = self._force_band_feed_bottom_scroll(post_selector)
            if force_info.get("moved"):
                moved = True
                any_moved = True
            wheel_info = self._dispatch_feed_wheel(
                post_selector,
                times=4 + min(scroll_try, 5),
                delta=1500 + min(scroll_try, 5) * 280
            )
            if moved:
                any_moved = True
            if scroll_try == 0:
                self.log(
                    "📜 피드 휠 스크롤 대상: "
                    f"{wheel_info.get('reason', 'unknown')} "
                    f"(게시물 {wheel_info.get('postCount', 0)}개, room {wheel_info.get('room', 0)}, "
                    f"강제스크롤 {'Y' if force_info.get('moved') else 'N'})"
                )

            clicked_load_more = False
            if scroll_try % 2 == 1:
                clicked_load_more = self._click_feed_load_more(post_selector)

            try:
                if posts_before:
                    # Stale 요소 방지를 위해 최신 DOM 다시 찾기
                    current_posts = self.driver.find_elements(By.CSS_SELECTOR, post_selector)
                    if current_posts:
                        ActionChains(self.driver).move_to_element(current_posts[-1]).scroll_by_amount(0, 2200).perform()
            except Exception:
                try:
                    ActionChains(self.driver).send_keys(Keys.PAGE_DOWN).perform()
                except Exception:
                    pass

            # Lazy loader가 고장난 경우를 위해 화면을 살짝 위로 올렸다가 내리는 Jiggle 로직
            if scroll_try % 3 == 2:
                try:
                    self._dispatch_feed_wheel(post_selector, times=2, delta=-1000)
                    time.sleep(0.4)
                    self._dispatch_feed_wheel(post_selector, times=3, delta=1200)
                except Exception:
                    pass

            time.sleep(2.4 + scroll_try * 0.45)
            try:
                posts = self.driver.find_elements(By.CSS_SELECTOR, post_selector)
                keys = [self._make_post_key(post) for post in posts]
                signature = "|".join([k for k in keys[-6:] if k])
                if len(posts) > len(posts_before):
                    self.log(f"📜 스크롤 성공: 게시물 DOM 증가 {len(posts_before)} → {len(posts)} ({scroll_try+1}/{attempts})")
                    return True
                for post in posts:
                    key = self._make_post_key(post)
                    if key and key not in processed_keys:
                        self.log(f"📜 스크롤 성공: 새 게시물 후보 감지 ({scroll_try+1}/{attempts})")
                        return True

                if signature and signature != last_signature:
                    self.log(f"📜 피드 위치 변화 감지: 추가 로딩 대기 중 ({scroll_try+1}/{attempts})")
                    last_signature = signature
                    stable_rounds = 0
                else:
                    stable_rounds += 1
            except Exception:
                stable_rounds += 1

            if clicked_load_more:
                stable_rounds = 0

            try:
                ActionChains(self.driver).send_keys(Keys.PAGE_DOWN).perform()
            except Exception:
                pass

            # 강제 JS 스크롤 폴백 (해시태그 보드 등에서 종종 필요함)
            try:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            except Exception:
                pass
                
            if not moved and stable_rounds >= max(5, attempts // 2):
                self.log(f"⚠️ 피드 스크롤 위치가 {stable_rounds}회 연속 변하지 않았습니다.")
        if any_moved:
            self.log("📜 피드는 이동했지만 아직 새 게시물 후보가 감지되지 않아 다음 루프에서 재확인합니다.")
            return True
        return False

    def _visible(self, elem):
        try:
            return elem.is_displayed()
        except Exception:
            return False

    def _click_element(self, elem):
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
            time.sleep(0.2)
        except Exception:
            pass
        try:
            elem.click()
            return True
        except Exception:
            try:
                self.driver.execute_script("arguments[0].click();", elem)
                return True
            except Exception:
                return False

    def _close_open_layers(self):
        """Close Band text/photo layers so feed scrolling and next clicks target the card."""
        close_selectors = [
            "button.btnLyClose",
            "button.btnClose",
            "button._closeViewer",
            "button._btnClose",
            "button[class*='Close']",
            "button[class*='close']",
            "button[aria-label*='닫']",
            "button[title*='닫']",
            "button[data-viewname='DLayerCloseButton']",
        ]
        for _ in range(2):
            closed = False
            for sel in close_selectors:
                try:
                    buttons = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for btn in reversed(buttons):
                        if self._visible(btn) and self._click_element(btn):
                            closed = True
                            time.sleep(0.4)
                            break
                    if closed:
                        break
                except Exception:
                    pass
            try:
                ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                time.sleep(0.4)
            except Exception:
                pass
        return True

    def _extract_text_from_post_card(self, post_elem):
        selectors = [
            "div.postText._postText",
            "div.postText",
            "div._postText",
            "p.listBody",
            "div.postBody",
        ]
        parts = []
        for sel in selectors:
            try:
                elems = post_elem.find_elements(By.CSS_SELECTOR, sel)
                for elem in elems:
                    text = self.driver.execute_script("return arguments[0].innerText;", elem) or elem.text or ""
                    text = re.sub(r'\.{2,}\s*더보기\s*$', '', text).strip()
                    text = re.sub(r'^\s*더보기\s*$', '', text, flags=re.M).strip()
                    if text and text not in parts:
                        parts.append(text)
                if parts:
                    break
            except Exception:
                pass
        return "\n".join(parts).strip()

    def _extract_text_from_popup(self):
        text_selectors = [
            "div[data-viewname='DPostTextView'] div.postText",
            "div[data-viewname='DPostView'] div.postText",
            "div.layerWrap div.postText",
            "div.viewer_layer div.postText",
            "div.postText._postText",
        ]
        best_text = ""
        for sel in text_selectors:
            try:
                elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for elem in reversed(elems):
                    if not self._visible(elem):
                        continue
                    text = self.driver.execute_script("return arguments[0].innerText;", elem) or elem.text or ""
                    text = text.strip()
                    if len(text) > len(best_text):
                        best_text = text
            except Exception:
                pass
        return best_text.strip()

    def _collect_post_text(self, post_elem):
        """Collect text first, then close the text layer before image work."""
        raw_text = self._extract_text_from_post_card(post_elem)

        try:
            more_buttons = post_elem.find_elements(By.CSS_SELECTOR, "button._btnMore, button[class*='MoreText'], a[class*='more']")
            for btn in more_buttons:
                if self._visible(btn) and self._click_element(btn):
                    time.sleep(1.2)
                    popup_text = self._extract_text_from_popup()
                    if len(popup_text) > len(raw_text):
                        raw_text = popup_text
                    break
        except Exception:
            pass

        if not raw_text:
            try:
                for sel in ["div.postText", "p.listBody", "div.postBody", "a.postLink"]:
                    elems = post_elem.find_elements(By.CSS_SELECTOR, sel)
                    for elem in elems:
                        if self._visible(elem) and self._click_element(elem):
                            self.log("  🔍 본문 팝업에서 텍스트 수집 시도...")
                            time.sleep(1.5)
                            raw_text = self._extract_text_from_popup() or raw_text
                            break
                    if raw_text:
                        break
            except Exception:
                pass

        self._close_open_layers()
        return (raw_text or "").strip()

    def _find_active_photo_layer(self):
        selectors = [
            "div[data-viewname='DPostPhotoView']",
            "div.photo_viewer_layer",
            "div.viewer_layer",
            "div.layerWrap",
            "div[class*='PhotoViewer']",
            "div[class*='photoViewer']",
        ]
        candidates = []
        for sel in selectors:
            try:
                for layer in self.driver.find_elements(By.CSS_SELECTOR, sel):
                    if not self._visible(layer):
                        continue
                    try:
                        image_count = len(layer.find_elements(By.CSS_SELECTOR, "img[src*='pstatic.net'], img[src*='campmobile']"))
                    except Exception:
                        image_count = 0
                    if image_count:
                        candidates.append((image_count, layer))
            except Exception:
                pass
        if candidates:
            candidates.sort(key=lambda item: item[0])
            return candidates[-1][1]
        return None

    def _find_active_post_layer(self):
        """Find the currently open post-detail popup layer."""
        selectors = [
            "div[data-viewname='DPostView']",
            "div[role='dialog']",
            "section[role='dialog']",
            "div[aria-modal='true']",
            "div.layerWrap",
            "div.viewer_layer",
            "div.modal",
            "div[class*='Modal']",
            "div[class*='modal']",
            "div[class*='Dialog']",
            "div[class*='dialog']",
            "div[class*='Popup']",
            "div[class*='popup']",
            "div[class*='Layer']",
            "div[class*='layer']",
            "div[class*='ly']",
            "div[class*='Layer']",
        ]
        candidates = []
        for sel in selectors:
            try:
                for layer in self.driver.find_elements(By.CSS_SELECTOR, sel):
                    if not self._visible(layer):
                        continue
                    try:
                        text_count = len(layer.find_elements(By.CSS_SELECTOR, "div.postText, p.listBody, div.postBody"))
                        image_count = len(layer.find_elements(By.CSS_SELECTOR, "img[src*='pstatic.net'], img[src*='campmobile']"))
                    except Exception:
                        text_count, image_count = 0, 0
                    if text_count or image_count:
                        candidates.append((text_count * 10 + image_count, layer))
            except Exception:
                pass
        if candidates:
            candidates.sort(key=lambda item: item[0])
            return candidates[-1][1]

        # Band changes popup class names often. As a fallback, locate the largest
        # visible overlay-like element with post text or campmobile images.
        try:
            return self.driver.execute_script("""
                const vw = window.innerWidth || document.documentElement.clientWidth;
                const vh = window.innerHeight || document.documentElement.clientHeight;
                const nodes = Array.from(document.querySelectorAll('div, section, article, main'));
                const scored = [];

                for (const el of nodes) {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    if (!rect || rect.width < 280 || rect.height < 240) continue;
                    if (rect.bottom < 0 || rect.right < 0 || rect.top > vh || rect.left > vw) continue;
                    if (style.visibility === 'hidden' || style.display === 'none' || Number(style.opacity || 1) < 0.2) continue;
                    if (el === document.body || el === document.documentElement) continue;

                    const z = parseInt(style.zIndex, 10);
                    const isOverlay =
                        style.position === 'fixed' ||
                        style.position === 'absolute' ||
                        Number.isFinite(z) && z >= 10 ||
                        rect.width < vw * 0.92 && rect.height < vh * 0.95;
                    if (!isOverlay) continue;

                    const text = (el.innerText || '').trim();
                    const imageCount = el.querySelectorAll("img[src*='pstatic.net'], img[src*='campmobile'], [style*='pstatic.net'], [style*='campmobile']").length;
                    const textCount = el.querySelectorAll('div.postText, p.listBody, div.postBody').length;
                    if (text.length < 20 && imageCount === 0 && textCount === 0) continue;

                    const area = rect.width * rect.height;
                    const centerBonus = (rect.left > vw * 0.08 && rect.right < vw * 0.92) ? 500000 : 0;
                    const zBonus = Number.isFinite(z) ? z * 10000 : 0;
                    scored.push({ score: area + centerBonus + zBonus + text.length * 50 + imageCount * 30000, el });
                }

                scored.sort((a, b) => b.score - a.score);
                return scored.length ? scored[0].el : null;
            """)
        except Exception:
            return None

    def _open_post_detail_popup(self, post_elem):
        self._close_open_layers()
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", post_elem)
            time.sleep(0.4)
        except Exception:
            pass

        selectors = [
            "button._btnMore",
            "button[class*='MoreText']",
            "a[class*='more']",
            "span[class*='more']",
            "span[class*='More']",
            "div[class*='more']",
            "div[class*='More']",
            "div.postText",
            "p.listBody",
            "div.postBody",
            "a.postLink",
            "div.photoGrid",
            "ul.uCollage",
            "article",
        ]
        for sel in selectors:
            try:
                elems = post_elem.find_elements(By.CSS_SELECTOR, sel) if sel != "article" else [post_elem]
                for elem in elems:
                    if not self._visible(elem):
                        continue
                    if self._click_element(elem):
                        time.sleep(1.8)
                        layer = self._find_active_post_layer()
                        if layer:
                            self.log("  🔍 게시물 상세 팝업 열기 성공")
                            return layer
            except Exception:
                pass
        layer = self._find_active_post_layer()
        if layer:
            self.log("  🔍 이미 열린 상세 팝업 감지")
            return layer
        return None

    def _extract_text_from_layer(self, layer):
        best_text = ""
        selectors = [
            "div[data-viewname='DPostTextView'] div.postText",
            "div.postText._postText",
            "div.postText",
            "p.listBody",
            "div.postBody",
        ]
        for sel in selectors:
            try:
                for elem in layer.find_elements(By.CSS_SELECTOR, sel):
                    if not self._visible(elem):
                        continue
                    text = self.driver.execute_script("return arguments[0].innerText;", elem) or elem.text or ""
                    text = text.strip()
                    if len(text) > len(best_text):
                        best_text = text
            except Exception:
                pass
        return best_text.strip()

    def _extract_image_url_from_element(self, elem):
        attrs = ("src", "data-src", "data-original", "data-url", "data-image-url")
        for attr in attrs:
            try:
                url = self._normalize_image_url(elem.get_attribute(attr) or "")
                if url and not self._is_non_product_image_element(elem, url):
                    return url
            except Exception:
                pass
        try:
            style = elem.get_attribute("style") or ""
            m = re.search(r'url\(["\']?([^"\')]+)', style)
            if m:
                url = self._normalize_image_url(m.group(1))
                if url and not self._is_non_product_image_element(elem, url):
                    return url
        except Exception:
            pass
        return ""

    def _collect_popup_image_urls(self, layer, expected_count):
        """Collect image URLs only from the opened post popup/photo layer."""
        collected = []
        seen = set()

        def add_from(target):
            before = len(collected)
            selectors = [
                "div.photoList img",
                "div.photoGrid img",
                "ul.uCollage img",
                "div.mediaWrap img",
                "ul.list img",
                "img[src*='pstatic.net']",
                "img[src*='campmobile']",
                "[style*='pstatic.net']",
                "[style*='campmobile']",
            ]
            for sel in selectors:
                try:
                    for elem in target.find_elements(By.CSS_SELECTOR, sel):
                        url = self._extract_image_url_from_element(elem)
                        if url and url not in seen:
                            seen.add(url)
                            collected.append(url)
                            self.log(f"  🔍 팝업 이미지 URL 추출 [{len(collected)}]: {url[:60]}...")
                except Exception:
                    pass
            return len(collected) - before

        add_from(layer)

        if expected_count and expected_count > 4 and len(collected) >= expected_count:
            return collected

        # Stay anchored to the open popup: click only photo/more controls inside this layer.
        open_selectors = [
            "li.more button",
            "button.uMoreImage",
            "li._collageMore button",
            "button[class*='MoreImage']",
            "button[class*='more']",
            "div.photoGrid button",
            "ul.uCollage li button._imageButton",
            "button._imageButton",
            "div.photoGrid img",
            "ul.uCollage img",
        ]
        viewer_opened = False
        for sel in open_selectors:
            try:
                elems = layer.find_elements(By.CSS_SELECTOR, sel)
                for elem in elems:
                    if not self._visible(elem):
                        continue
                    if self._click_element(elem):
                        time.sleep(1.4)
                        photo_layer = self._find_active_photo_layer()
                        if photo_layer:
                            viewer_opened = True
                            break
                if viewer_opened:
                    break
            except Exception:
                pass

        if viewer_opened:
            viewer_urls = self._collect_urls_from_photo_viewer(expected_count)
            for url in viewer_urls:
                if url and url not in seen:
                    seen.add(url)
                    collected.append(url)
            return collected

        return collected

    def _collect_post_from_single_popup(self, post_elem, post_img_dir):
        """Open one post popup, collect its text and popup-scoped images, then close it."""
        self._last_collected_image_urls = []
        layer = self._open_post_detail_popup(post_elem)
        if not layer:
            self.log("  ⚠️ 게시물 상세 팝업을 열지 못해 인라인 추출을 시도합니다.")
            raw_text = self._extract_text_from_post_card(post_elem)
            expected_count = self._get_total_image_count(post_elem)
            image_urls = []
            
            # 인라인에서 이미지 추출 (팝업 없이)
            selectors = ["div.photoGrid img", "ul.uCollage img", "img._image", "img"]
            for sel in selectors:
                try:
                    for img in post_elem.find_elements(By.CSS_SELECTOR, sel):
                        url = self._extract_image_url_from_element(img)
                        if url and url not in image_urls:
                            image_urls.append(url)
                            self.log(f"  🔍 인라인 이미지 URL 추출 [{len(image_urls)}]: {url[:60]}...")
                except Exception:
                    pass
            
            self._last_collected_image_urls = image_urls
            image_files = self._download_image_urls(image_urls, post_img_dir) if image_urls else []
            return raw_text, image_files

        try:
            raw_text = self._extract_text_from_layer(layer)
            expected_count = self._get_total_image_count(post_elem)
            image_urls = self._collect_popup_image_urls(layer, expected_count)
            self._last_collected_image_urls = image_urls

            if expected_count and image_urls and len(image_urls) < expected_count:
                self.log(f"  ⚠️ 예상 {expected_count}장 중 팝업에서 {len(image_urls)}장만 감지되었습니다.")

            image_files = self._download_image_urls(image_urls, post_img_dir) if image_urls else []
            return raw_text, image_files
        finally:
            self._close_open_layers()

    def _open_photo_viewer(self, post_elem):
        self._close_open_layers()
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", post_elem)
            time.sleep(0.4)
        except Exception:
            pass

        selectors = [
            "li.more button",
            "button.uMoreImage",
            "li._collageMore button",
            "button[class*='MoreImage']",
            "ul.uCollage li button._imageButton",
            "button._imageButton",
            "div.photoGrid button",
            "div.photoGrid img",
            "ul.uCollage img",
            "img._image",
        ]
        for sel in selectors:
            try:
                elems = post_elem.find_elements(By.CSS_SELECTOR, sel)
                for elem in elems:
                    if not self._visible(elem):
                        continue
                    if self._click_element(elem):
                        time.sleep(1.7)
                        if self._find_active_photo_layer():
                            self.log("  🔍 사진 뷰어 열기 성공")
                            return True
            except Exception:
                pass
        return False

    def _collect_urls_from_photo_viewer(self, expected_count):
        collected = []
        seen = set()

        def collect_once():
            layer = self._find_active_photo_layer()
            if not layer:
                return 0
            before = len(collected)
            selectors = [
                "ul.list img",
                "div.photoList img",
                "div.thumbnail img",
                "div.mediaWrap img",
                "img[src*='pstatic.net']",
                "img[src*='campmobile']",
            ]
            for sel in selectors:
                try:
                    for img in layer.find_elements(By.CSS_SELECTOR, sel):
                        src = img.get_attribute("src") or img.get_attribute("data-src") or ""
                        url = self._normalize_image_url(src)
                        if url and url not in seen and not self._is_non_product_image_element(img, url):
                            seen.add(url)
                            collected.append(url)
                            self.log(f"  🔍 고화질 이미지 URL 추출 [{len(collected)}]: {url[:60]}...")
                except Exception:
                    pass
            return len(collected) - before

        max_steps = max(expected_count + 6, 24)
        no_growth = 0
        for _ in range(max_steps):
            growth = collect_once()
            if expected_count and len(collected) >= expected_count:
                break

            layer = self._find_active_photo_layer()
            if layer:
                try:
                    self.driver.execute_script("""
                        const root = arguments[0];
                        const items = root.querySelectorAll('ul, div');
                        for (const el of items) {
                            if ((el.scrollHeight || 0) - (el.clientHeight || 0) > 80) {
                                el.scrollTop = Math.min(el.scrollHeight, (el.scrollTop || 0) + Math.max(el.clientHeight * 0.9, 500));
                            }
                        }
                    """, layer)
                except Exception:
                    pass

            clicked_next = False
            next_selectors = [
                "button._nextPhoto",
                "button._btnNext",
                "button.mediaNav.next",
                "button[class*='next']",
                "a[class*='next']",
            ]
            for sel in next_selectors:
                try:
                    buttons = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for btn in reversed(buttons):
                        if self._visible(btn) and btn.is_enabled() and self._click_element(btn):
                            clicked_next = True
                            time.sleep(0.55)
                            break
                    if clicked_next:
                        break
                except Exception:
                    pass

            if not clicked_next:
                try:
                    ActionChains(self.driver).send_keys(Keys.ARROW_RIGHT).perform()
                    clicked_next = True
                    time.sleep(0.55)
                except Exception:
                    pass

            if growth == 0 and not clicked_next:
                no_growth += 1
            elif growth == 0:
                no_growth += 1
            else:
                no_growth = 0

            if no_growth >= 4:
                break
            time.sleep(0.25)

        return collected

    def _download_image_urls(self, image_urls, post_img_dir):
        os.makedirs(post_img_dir, exist_ok=True)
        session = self._make_session()
        saved = []
        for idx, url in enumerate(image_urls):
            ext = '.jpg'
            m = re.search(r'\.(jpg|jpeg|png|webp|gif)', url, re.I)
            if m:
                ext = '.' + m[1].lower()
            filename = f"img_{idx+1:03d}{ext}"
            dest = os.path.join(post_img_dir, filename)
            if self._download_url(session, url, dest):
                saved.append(filename)
                self.log(f"  📷 저장: {filename}")
        saved = self._filter_saved_non_product_images(saved, post_img_dir)
        self.log(f"  ✅ 총 {len(saved)}장 이미지 저장 완료")
        return saved

    # ----------------------------------------------------------------
    # 뷰어 열기 → 전체 이미지 순환 수집
    # ----------------------------------------------------------------
    def collect_images_via_viewer(self, post_elem, post_img_dir):
        """
        현재 게시물의 사진 영역을 눌러 사진 뷰어를 열고 전체 이미지 URL을 수집합니다.
        텍스트 팝업과 사진 뷰어를 분리해서 4장짜리 카드 썸네일만 저장되는 문제를 막습니다.
        """
        self._last_collected_image_urls = []
        expected_count = self._get_total_image_count(post_elem)

        if not self._open_photo_viewer(post_elem):
            self.log("  ⚠️ 사진 뷰어 열기 실패, 현재 게시물 썸네일만 fallback 수집합니다.")
            try:
                urls = []
                seen = set()
                for img in post_elem.find_elements(By.CSS_SELECTOR, "img._image, ul.uCollage img, div.photoGrid img"):
                    url = self._normalize_image_url(img.get_attribute("src") or "")
                    if url and url not in seen and not self._is_non_product_image_element(img, url):
                        seen.add(url)
                        urls.append(url)
                self._last_collected_image_urls = urls
                return self._download_image_urls(urls, post_img_dir) if urls else []
            finally:
                self._close_open_layers()

        try:
            image_urls = self._collect_urls_from_photo_viewer(expected_count)
            self._last_collected_image_urls = image_urls
            if not image_urls:
                self.log("  ⚠️ 사진 뷰어에서 수집할 이미지를 찾지 못했습니다.")
                return []
            if expected_count and len(image_urls) < expected_count:
                self.log(f"  ⚠️ 예상 {expected_count}장 중 {len(image_urls)}장만 감지되었습니다.")
            return self._download_image_urls(image_urls, post_img_dir)
        finally:
            self._close_open_layers()

    def _get_total_image_count(self, post_elem):
        """콜라주의 총 이미지 수 파악 (더보기 + 로부터 추정)"""
        try:
            # "더보기 +N" 버튼에서 숫자 추출
            MORE_SELECTORS = [
                "li.more span",
                "button.uMoreImage span",
                "span.uMoreCount",
                "li._collageMore span",
            ]
            for sel in MORE_SELECTORS:
                try:
                    elem = post_elem.find_element(By.CSS_SELECTOR, sel)
                    text = elem.text.strip()
                    m = re.search(r'\d+', text)
                    if m:
                        # 보이는 4장 + 더보기 N장
                        visible = len(post_elem.find_elements(By.CSS_SELECTOR, "ul.uCollage li"))
                        return visible + int(m.group())
                except Exception:
                    pass
            # 더보기 버튼 없으면 보이는 이미지 수
            visible = len(post_elem.find_elements(By.CSS_SELECTOR,
                "ul.uCollage li button._imageButton"))
            return max(visible, 1)
        except Exception:
            return 10  # 기본값

    def _close_viewer(self):
        """뷰어 ESC로 닫기"""
        try:
            # ESC 키
            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            time.sleep(1)
        except Exception:
            pass
        # 닫기 버튼도 시도
        for sel in ["button._closeViewer", "button.close", "button[class*='close']"]:
            try:
                btn = self.driver.find_element(By.CSS_SELECTOR, sel)
                btn.click()
                time.sleep(0.5)
                break
            except Exception:
                pass

    def _collect_from_collage_only(self, post_elem, post_img_dir):
        """Fallback: 콜라주 썸네일 이미지만 수집"""
        IMG_SELECTORS = ["img._image", "ul.uCollage img", "img[src*='band']"]
        img_urls = []
        seen = set()
        for sel in IMG_SELECTORS:
            try:
                for img in post_elem.find_elements(By.CSS_SELECTOR, sel):
                    normalized = self._normalize_image_url(img.get_attribute("src") or "")
                    if normalized and normalized not in seen and not self._is_non_product_image_element(img, normalized):
                        seen.add(normalized)
                        img_urls.append(normalized)
            except Exception:
                pass
        if not img_urls:
            return []
        os.makedirs(post_img_dir, exist_ok=True)
        session = self._make_session()
        saved = []
        for idx, url in enumerate(img_urls):
            ext = '.jpg'
            m = re.search(r'\.(jpg|jpeg|png|webp|gif)', url, re.I)
            if m:
                ext = '.' + m[1].lower()
            filename = f"img_{idx+1:03d}{ext}"
            dest = os.path.join(post_img_dir, filename)
            if self._download_url(session, url, dest):
                saved.append(filename)
        return saved

    # ----------------------------------------------------------------
    # 포스트 선택자 감지
    # ----------------------------------------------------------------
    def detect_post_selector(self):
        for sel in ["article._postMainWrap",
                    "div.cCard > article.cContentsCard._postMainWrap",
                    "div.cCard article", "li.cCard"]:
            if self.driver.find_elements(By.CSS_SELECTOR, sel):
                self.log(f"✅ 포스트 선택자: {sel}")
                return sel
        return "article._postMainWrap"

    # ----------------------------------------------------------------
    # 메인 실행
    # ----------------------------------------------------------------
    def run(self):
        self.log("🔁 밴드 크롤링 시작 (뷰어 순환 방식)")

        count = 0
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        post_selector = self.detect_post_selector()
        processed_post_keys = set()
        processed_content_keys = set()
        no_new_rounds = 0

        while count < self.max_count and not self.stop_flag:
            posts = self.driver.find_elements(By.CSS_SELECTOR, post_selector)

            new_posts_found = False
            processed_this_round = 0
            for idx, post in enumerate(posts):
                post_key = self._make_post_key(post)
                if post_key and post_key in processed_post_keys:
                    continue
                if count >= self.max_count or self.stop_flag:
                    break

                new_posts_found = True
                if post_key:
                    processed_post_keys.add(post_key)

                try:
                    # 1) 날짜 확인
                    post_date = self.extract_post_date(post)
                    date_str = post_date.strftime('%Y-%m-%d %H:%M') if post_date else '날짜불명'

                    if post_date:
                        if post_date > self.end_date:
                            self.log(f"[{idx+1}] {date_str} > 종료일, 건너뜀")
                            continue
                        if post_date < self.start_date:
                            self.log(f"[{idx+1}] {date_str} < 시작일, 중단")
                            self.stop_flag = True
                            break

                    # 2 & 3) 본문 상세 보기(팝업) 열어서 텍스트 및 이미지 추출
                    raw_text = ""
                    image_files = []
                    collected_urls = []
                    pending_content_key = ""
                    duplicate_content = False
                    post_img_dir = os.path.join(self.target_folder, f"band_post_{count+1}")
                    
                    try:
                        self.log("  🔍 상세 팝업 기준으로 본문과 이미지를 함께 수집합니다...")
                        raw_text, image_files = self._collect_post_from_single_popup(post, post_img_dir)
                        collected_urls = list(self._last_collected_image_urls)
                    except Exception as e:
                        self.log(f"  ❌ 상세 팝업 수집 중 오류: {e}")
                        self._close_open_layers()

                    if not raw_text and not image_files:
                        self.log(f"  ⚠️ 게시물 {idx+1}: 텍스트/이미지가 없어 건너뜁니다.")
                        shutil.rmtree(post_img_dir, ignore_errors=True)
                        continue

                    content_key = pending_content_key or self._make_content_key(raw_text, collected_urls)
                    if content_key and content_key in processed_content_keys:
                        self.log(f"  ⚠️ 중복 게시물 감지: 같은 본문/이미지 조합이라 건너뜁니다. ({idx+1})")
                        shutil.rmtree(post_img_dir, ignore_errors=True)
                        continue
                    if content_key:
                        processed_content_keys.add(content_key)

                    # 4-1) 텍스트 파일 저장 (.txt)
                    if raw_text:
                        os.makedirs(post_img_dir, exist_ok=True)
                        txt_filename = f"band_post_{count+1}_content.txt"
                        txt_path = os.path.join(post_img_dir, txt_filename)
                        try:
                            with open(txt_path, 'w', encoding='utf-8') as f:
                                f.write(raw_text)
                            self.log(f"  📝 텍스트 저장: {txt_filename} ({len(raw_text)}자)")
                        except Exception as e:
                            self.log(f"  ❌ 텍스트 저장 오류: {e}")

                    # 5) 텍스트 변환 및 파싱 (제목, 단가, 상품코드 자동 추출)
                    title, body = "", ""
                    sale_price = "0"
                    product_code = ""

                    if raw_text:
                        lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
                        if lines:
                            title = lines[0]  # 첫 번째 줄은 무조건 제목
                            body = raw_text
                            
                            # ㄷㄱ 기호 및 상품코드 파싱
                            for i, ln in enumerate(lines):
                                m = re.search(r'ㄷㄱ\s*([0-9.]+)', ln)
                                if m:
                                    # 단가 추출 (예: 5.5 -> 55000원)
                                    try:
                                        val = float(m.group(1))
                                        sale_price = f"{int(val * 10000)}원"
                                    except:
                                        pass
                                    
                                    # 상품코드는 ㄷㄱ 구문 바로 윗줄로 지정
                                    if i > 0:
                                        product_code = lines[i-1]
                                    break
                            
                            # 기존 변환 함수가 있으면 body 정제에 보조적으로만 사용
                            if self.transform_function:
                                try:
                                    result = self.transform_function(raw_text)
                                    if isinstance(result, (list, tuple)) and len(result) >= 2:
                                        _, body = result[0], result[1]
                                except Exception as te2:
                                    self.log(f"텍스트 변환 오류: {te2}")

                    # 6) 결과 전송
                    result_data = {
                        "title": title,
                        "body": body,
                        "raw_description": raw_text,
                        "product_code": product_code,
                        "image_files": image_files,
                        "local_image_dir": post_img_dir if image_files else "",
                        "price_input": "0",   # 원가는 0으로 세팅 (화면에서는 숨김 처리 예정)
                        "sale_price": sale_price,
                        "created_at": post_date.strftime("%Y-%m-%d %H:%M:%S") if post_date else "",
                        "full_text": raw_text,
                    }
                    self.result_signal.emit(result_data)
                    count += 1
                    processed_this_round += 1
                    self.progress_signal.emit(count)
                    self.log(
                        f"✅ [{count}] {date_str} | 텍스트 {len(raw_text)}자 | 이미지 {len(image_files)}장")

                except Exception as e:
                    self.log(f"⚠️ 게시물[{idx+1}] 오류: {e}")

            if self.stop_flag:
                break

            if processed_this_round > 0 or new_posts_found:
                no_new_rounds = 0
                if not self._scroll_until_new_posts(post_selector, processed_post_keys, attempts=10):
                    self.log("더 이상 로딩되는 게시물이 없습니다.")
                    break
            else:
                no_new_rounds += 1
                self.log(f"⚠️ 현재 화면에서 새 게시물이 없어 추가 스크롤을 시도합니다... ({no_new_rounds})")
                if not self._scroll_until_new_posts(post_selector, processed_post_keys, attempts=16):
                    self.log("더 이상 로딩되는 게시물이 없습니다.")
                    break
                if no_new_rounds >= 4:
                    self.log("⚠️ 여러 차례 스크롤 후에도 새 게시물이 없어 중단합니다.")
                    break

        self.log(f"🏁 밴드 크롤링 완료. 총 {count}개 수집.")
        self.finished_signal.emit(count)

    def stop(self):
        self.stop_flag = True
