# -*- coding: utf-8 -*-
"""
윈윈크롤러 → LUXAI 쇼핑몰 webhook 연결기 (도킹 전송기)
=====================================================
윈윈크롤러가 수집해 둔 상품(폴더별: 텍스트파일 + 이미지들)을 읽어,
이미지는 쇼핑몰에 업로드하고 상품 데이터는 webhook 으로 전송해 자동 등록한다.

[준비물]  pip install requests

[사용법]
  1) 관리자 화면(크롤러 설정)에서 securityToken 을 정해 저장한다.
  2) 아래 '설정'을 채운다(파일 직접 수정 또는 환경변수).
  3) 먼저 연결 테스트:   python winwin_webhook_sender.py --demo
  4) 실제 전송(미리보기): python winwin_webhook_sender.py --dry-run
  5) 실제 전송:          python winwin_webhook_sender.py

[환경변수로도 설정 가능]
  MALL_URL, WEBHOOK_TOKEN, MALL_EMAIL, MALL_PASSWORD, WINWIN_SOURCE_DIR, CATEGORY_ID
"""
import os
import re
import sys
import glob
import json
import mimetypes
import argparse

# Windows 콘솔(cp949)에서도 이모지/한글 출력이 깨지지 않도록 UTF-8 강제
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

try:
    import requests
except ImportError:
    print("❌ 'requests' 가 필요합니다.  먼저:  pip install requests")
    sys.exit(1)

# ===================== 설정 (직접 수정하거나 환경변수 사용) =====================
MALL_URL = os.environ.get("MALL_URL", "http://localhost:8002").rstrip("/")
WEBHOOK_TOKEN = os.environ.get("WEBHOOK_TOKEN", "")           # 관리자에서 정한 토큰 (필수)
LOGIN_EMAIL = os.environ.get("MALL_EMAIL", "admin@example.com")
LOGIN_PASSWORD = os.environ.get("MALL_PASSWORD", "admin1234")
SOURCE_DIR = os.environ.get("WINWIN_SOURCE_DIR", "")          # 윈윈크롤러 수집 폴더(상품별 하위폴더)
DEFAULT_CATEGORY_ID = int(os.environ.get("CATEGORY_ID", "1") or "1")  # 자동분류 실패 시 폴백
CATEGORY_MAP_FILE = os.environ.get("CATEGORY_MAP_FILE", "")   # LUXAI 카테고리맵 JSON 경로(비우면 서버서 자동 fetch)
AUTO_CLASSIFY = os.environ.get("AUTO_CLASSIFY", "1") != "0"   # 제목/본문 자동 카테고리 분류 (기본 ON)
# ============================================================================

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp")
_jwt = {"token": None}


def _login():
    """이미지 업로드용 JWT 발급(1회 캐시)."""
    if _jwt["token"]:
        return _jwt["token"]
    r = requests.post(f"{MALL_URL}/api/auth/login",
                      data={"username": LOGIN_EMAIL, "password": LOGIN_PASSWORD}, timeout=15)
    r.raise_for_status()
    _jwt["token"] = r.json()["access_token"]
    return _jwt["token"]


def upload_images(local_paths):
    """로컬 이미지 파일들을 쇼핑몰에 업로드하고 URL 목록을 반환."""
    local_paths = [p for p in local_paths if os.path.isfile(p)]
    if not local_paths:
        return []
    token = _login()
    handles, files = [], []
    try:
        for p in local_paths[:12]:  # 상품당 최대 12장
            f = open(p, "rb")
            handles.append(f)
            ctype = mimetypes.guess_type(p)[0] or "image/jpeg"  # 서버 업로드 검증 통과용 content-type
            files.append(("files", (os.path.basename(p), f, ctype)))
        r = requests.post(f"{MALL_URL}/api/admin/upload/multiple",
                          headers={"Authorization": f"Bearer {token}"}, files=files, timeout=120)
        r.raise_for_status()
        return [u["url"] for u in r.json().get("uploaded", [])]
    finally:
        for f in handles:
            f.close()


def _parse_price(text):
    """본문에서 위안화(¥/￥) 가격 추정. 없으면 0."""
    m = re.search(r'[¥￥]\s*([\d,.]+)', text or "")
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return 0


_catmap = {"data": None, "loaded": False}


def load_category_map():
    """LUXAI 카테고리맵 로드 — CATEGORY_MAP_FILE 우선, 없으면 서버에서 fetch. 1회 캐시."""
    if _catmap["loaded"]:
        return _catmap["data"]
    _catmap["loaded"] = True
    data = None
    try:
        if CATEGORY_MAP_FILE and os.path.isfile(CATEGORY_MAP_FILE):
            with open(CATEGORY_MAP_FILE, encoding="utf-8") as f:
                data = json.load(f)
            print(f"  (카테고리맵 파일 로드: {CATEGORY_MAP_FILE}, {data.get('category_count')}개)")
        else:
            token = _login()
            r = requests.get(f"{MALL_URL}/api/category-sync/map",
                             headers={"Authorization": f"Bearer {token}"}, timeout=15)
            r.raise_for_status()
            data = r.json()
            print(f"  (카테고리맵 서버 fetch: {data.get('category_count')}개)")
    except Exception as e:
        print(f"  ⚠️ 카테고리맵 로드 실패 → 자동분류 끄고 기본 카테고리 사용: {e}")
        data = None
    _catmap["data"] = data
    return data


def classify_category(title, body, cmap):
    """제목/본문 → category_id (cmap 키워드 점수매칭). cmap 없으면 None."""
    if not cmap:
        return None
    cfg = cmap.get("match") or {}
    tw, bw = cfg.get("title_weight", 5), cfg.get("body_weight", 1)
    min_score = cfg.get("min_score", 1)
    prefer_deeper = cfg.get("prefer_deeper", True)
    t, b = (title or "").lower(), (body or "").lower()
    both = t + " " + b
    best = None
    for cat in cmap.get("categories", []):
        if any(x and x.lower() in both for x in cat.get("exclude", [])):
            continue
        score = 0
        for kw in cat.get("keywords", []):
            k = (kw or "").lower()
            if not k:
                continue
            if k in t:
                score += tw
            if k in b:
                score += bw
        if score <= 0:
            continue
        cand = (score, cat.get("level", 0) if prefer_deeper else 0, cat.get("id"))
        if best is None or cand[:2] > best[:2]:
            best = cand
    if best and best[0] >= min_score:
        return best[2]
    return cmap.get("fallback_category_id")


def send_product(title, desc, image_urls, source_url, category_id, price=0):
    """webhook 으로 상품 1건 전송."""
    payload = {
        "title": title,
        "desc": desc,
        "images": image_urls,
        "source_url": source_url,
        "category_id": category_id,
    }
    if price:
        payload["price"] = price
    return requests.post(f"{MALL_URL}/api/crawler/webhook",
                         params={"token": WEBHOOK_TOKEN}, json=payload, timeout=120)


def _short(body):
    if isinstance(body, dict):
        return f"{body.get('status')} (id={body.get('product_id', '-')})"
    return str(body)[:200]


def process_folder(folder, dry_run=False):
    """상품 폴더 1개(텍스트 + 이미지) → 전송."""
    txts = glob.glob(os.path.join(folder, "*.txt"))
    text = ""
    if txts:
        with open(txts[0], encoding="utf-8", errors="ignore") as f:
            text = f.read().strip()
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    title = (lines[0][:80] if lines else os.path.basename(folder))

    imgs = []
    for ext in IMAGE_EXTS:
        imgs += glob.glob(os.path.join(folder, f"*{ext}"))
    imgs = sorted(imgs)
    price = _parse_price(text)
    source_url = f"winwin://{os.path.basename(folder)}"

    cat_id = (classify_category(title, text, load_category_map()) if AUTO_CLASSIFY else None) or DEFAULT_CATEGORY_ID
    print(f"\n[폴더] {os.path.basename(folder)}  (이미지 {len(imgs)}장, 가격추정 {price}, 자동분류→category_id={cat_id})")
    if dry_run:
        print(f"  └ (dry-run) 제목: {title[:40]}")
        return
    image_urls = upload_images(imgs)
    r = send_product(title, text, image_urls, source_url, cat_id, price)
    try:
        print(f"  └ {r.status_code}: {_short(r.json())}")
    except Exception:
        print(f"  └ {r.status_code}: {r.text[:200]}")


def cmd_demo():
    print("== 연결 테스트(샘플 1건 전송) ==")
    title = "연결테스트 남성 반팔 티셔츠"
    cat_id = (classify_category(title, "", load_category_map()) if AUTO_CLASSIFY else None) or DEFAULT_CATEGORY_ID
    print(f"  자동분류 결과: category_id={cat_id}")
    r = send_product(
        title=title,
        desc="이 상품이 관리자 상품목록에 보이면 도킹 연결 성공입니다. (S M L 사이즈)",
        image_urls=["https://cdn-icons-png.flaticon.com/512/863/863684.png"],
        source_url="winwin://demo-sample",
        category_id=cat_id,
        price=100,
    )
    try:
        print(f"  결과 {r.status_code}: {r.json()}")
    except Exception:
        print(f"  결과 {r.status_code}: {r.text[:300]}")
    if r.status_code == 200:
        print("✅ 연결 성공! 관리자 → 상품 관리에서 '연결테스트 샘플상품' 을 확인하세요.")
    else:
        print("⚠️ 실패. 토큰/주소를 확인하세요. (관리자에서 정한 securityToken == WEBHOOK_TOKEN)")


def main():
    ap = argparse.ArgumentParser(description="윈윈크롤러 → 쇼핑몰 webhook 전송기")
    ap.add_argument("--demo", action="store_true", help="샘플 1건 전송(연결 테스트)")
    ap.add_argument("--dry-run", action="store_true", help="전송하지 않고 미리보기")
    args = ap.parse_args()

    if not WEBHOOK_TOKEN:
        print("❌ WEBHOOK_TOKEN 이 비어 있습니다. 관리자에서 정한 토큰을 파일 상단 또는 환경변수에 설정하세요.")
        sys.exit(1)

    print(f"대상 쇼핑몰: {MALL_URL}")
    if args.demo:
        cmd_demo()
        return

    if not SOURCE_DIR or not os.path.isdir(SOURCE_DIR):
        print(f"❌ 수집 폴더(SOURCE_DIR)가 없습니다: {SOURCE_DIR!r}")
        print("   윈윈크롤러가 상품을 저장한 폴더(상품별 하위폴더 구조)를 지정하세요.")
        sys.exit(1)

    folders = [os.path.join(SOURCE_DIR, d) for d in os.listdir(SOURCE_DIR)
               if os.path.isdir(os.path.join(SOURCE_DIR, d))]
    # [정렬 개선] 폴더 수정 시간(mtime) 기준으로 정렬하여 크롤링되어 생성된 시간 순서를 그대로 보존합니다.
    # 과거 상품부터 순차적으로 전송해야 최종적으로 최신 상품이 가장 늦게 등록되어 쇼핑몰 최상단에 꽂히게 됩니다.
    folders.sort(key=os.path.getmtime)
    
    print(f"총 {len(folders)}개 상품 폴더 발견. {'(dry-run) ' if args.dry_run else ''}전송 시작…")
    ok = 0
    for folder in folders:
        try:
            process_folder(folder, dry_run=args.dry_run)
            ok += 1
        except Exception as e:
            print(f"  ⚠️ 폴더 처리 실패({os.path.basename(folder)}): {e}")
    print(f"\n완료. (처리 {ok}/{len(folders)})")


if __name__ == "__main__":
    main()
