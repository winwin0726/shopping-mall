import hashlib
import os
import re
from typing import Iterable, List, Tuple


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _read_text(path: str) -> str:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        return ""
    return ""


def _clean_label(value: str) -> str:
    return re.sub(r"[\r\n\t]+", " ", str(value or "")).strip()


def _category_candidates(category: str) -> List[str]:
    raw = _clean_label(category)
    if not raw:
        return []

    candidates = [raw]
    for part in re.split(r"[|,]", raw):
        part = part.strip()
        if part and part not in candidates:
            candidates.append(part)
    return candidates


def load_style_blocks(category: str = "", include_band: bool = True) -> List[Tuple[str, str]]:
    """Load owner writing style profiles in the priority used by translation prompts."""
    files: List[Tuple[str, str]] = []

    common_path = os.path.join(BASE_DIR, "my_style_prompt_공통.txt")
    if os.path.exists(common_path):
        files.append(("공통 스타일 분석", common_path))

    if include_band:
        band_path = os.path.join(BASE_DIR, "my_style_prompt_밴드.txt")
        if os.path.exists(band_path):
            files.append(("밴드 1000건 기준 분석", band_path))

    for cat in _category_candidates(category):
        cat_path = os.path.join(BASE_DIR, f"my_style_prompt_{cat}.txt")
        if os.path.exists(cat_path) and all(cat_path != path for _, path in files):
            files.append((f"{cat} 카테고리 스타일 분석", cat_path))

        band_cat_path = os.path.join(BASE_DIR, f"my_style_prompt_밴드_{cat}.txt")
        if include_band and os.path.exists(band_cat_path) and all(band_cat_path != path for _, path in files):
            files.append((f"밴드 {cat} 기준 분석", band_cat_path))

    fallback_path = os.path.join(BASE_DIR, "my_style_prompt.txt")
    if not files and os.path.exists(fallback_path):
        files.append(("기본 스타일 분석", fallback_path))

    blocks: List[Tuple[str, str]] = []
    for label, path in files:
        text = _read_text(path)
        if text:
            blocks.append((label, text))
    return blocks


def build_style_instruction(category: str = "", include_band: bool = True) -> str:
    blocks = load_style_blocks(category=category, include_band=include_band)
    if not blocks:
        return ""

    body = "\n\n".join(f"[{label}]\n{text}" for label, text in blocks)
    return (
        "\n\n🚨 [사장님 고유 스타일/양식 기준 - 최우선 반영]\n"
        "아래 기준은 실제 운영 글을 분석해 만든 작성 규칙입니다. 카테고리별 양식 차이는 유지하되, "
        "제목/정보 순서/구분선/배송/마무리 방식은 이 기준에 맞춰 일관되게 작성하세요.\n"
        f"{body}\n"
    )


def extract_post_content(product: dict) -> str:
    for key in ("raw_description", "full_text", "body", "content", "description"):
        value = str(product.get(key) or "").strip()
        if value:
            return value
    return ""


def build_post_history_from_products(products: Iterable[dict], limit: int = 1000) -> List[dict]:
    posts = []
    seen = set()
    for product in products or []:
        content = extract_post_content(product)
        content = re.sub(r"\r\n?", "\n", content).strip()
        if len(content) < 20:
            continue

        digest = hashlib.md5(content.encode("utf-8", errors="ignore")).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)

        posts.append({
            "content": content,
            "title": str(product.get("title") or "").strip(),
            "category": str(product.get("vendor_category") or product.get("category") or "").strip(),
            "product_code": str(product.get("product_code") or "").strip(),
            "sale_price": str(product.get("sale_price") or "").strip(),
            "created_at": str(product.get("created_at") or "").strip(),
            "image_count": len(product.get("image_files") or product.get("local_image_paths") or []),
        })

        if len(posts) >= limit:
            break
    return posts
