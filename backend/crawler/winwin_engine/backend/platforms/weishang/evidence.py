import hashlib
import os
import re
from typing import Any


EVIDENCE_VERSION = "weishang-evidence-v1"


def _clean_text(value: Any, limit: int | None = None) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit] if limit else text


def _normalize_image_ref(src: Any) -> str:
    if not src:
        return ""
    text = str(src).strip().strip("'\"")
    if text.startswith("//"):
        text = "https:" + text
    if not text:
        return ""
    lower = text.lower()
    if lower.startswith("data:image") or lower.endswith(".gif"):
        return ""
    text = re.sub(r"([?&])(imageView2|x-oss-process|w|h|width|height|resize|thumbnail)=[^&]+", r"\1", text, flags=re.IGNORECASE)
    text = text.rstrip("?&")
    return text


def image_fingerprint(src: Any) -> str:
    clean = _normalize_image_ref(src)
    if not clean:
        return ""
    basename = os.path.basename(clean.split("?", 1)[0]).lower()
    seed = basename or clean.lower()
    return hashlib.sha1(seed.encode("utf-8", errors="ignore")).hexdigest()[:16]


def infer_item_key_type(item_key: Any) -> str:
    key = str(item_key or "")
    if ":goods:" in key:
        return "goods_id"
    if ":code:" in key:
        return "product_code"
    if ":api:" in key:
        return "api_packet"
    if ":img:" in key:
        return "image_fingerprint"
    if ":dom:" in key:
        return "dom_index"
    if ":text:" in key:
        return "raw_text"
    return "unknown"


def _api_score(api_match: Any) -> float:
    if not isinstance(api_match, dict):
        return 0.0
    for key in ("score", "match_score", "__ww_match_score"):
        try:
            value = float(api_match.get(key) or 0)
        except Exception:
            value = 0
        if value:
            return value
    return 0.0


def score_identity_confidence(
    item_key: Any = "",
    goods_id: Any = "",
    product_codes: list | tuple | None = None,
    api_match: dict | None = None,
    image_urls: list | tuple | None = None,
) -> dict:
    product_codes = list(product_codes or [])
    image_urls = list(image_urls or [])
    key_type = infer_item_key_type(item_key)
    reasons = []
    confidence = 0

    if goods_id:
        confidence = 100
        reasons.append("goods_id_present")
        key_type = "goods_id"
    elif product_codes:
        confidence = 86
        reasons.append("product_code_present")
        if key_type == "unknown":
            key_type = "product_code"
    elif key_type == "api_packet":
        score = _api_score(api_match)
        confidence = max(70, min(84, int(score or 70)))
        reasons.append(f"api_packet_match:{int(score or 0)}")
    elif key_type == "image_fingerprint":
        confidence = 66
        reasons.append("image_fingerprint_only")
    elif key_type == "dom_index":
        confidence = 42
        reasons.append("dom_index_fallback")
    elif key_type == "raw_text":
        confidence = 34
        reasons.append("raw_text_fallback")

    if isinstance(api_match, dict) and api_match:
        reasons.append("api_match_available")
        if confidence and key_type not in {"goods_id", "product_code"}:
            confidence = max(confidence, min(84, int(_api_score(api_match) or 70)))
    if image_urls:
        reasons.append(f"image_refs:{len(image_urls)}")
        confidence = max(confidence, 48 if key_type in {"unknown", "raw_text"} else confidence)

    return {
        "key_type": key_type,
        "confidence": int(confidence),
        "item_key": str(item_key or ""),
        "goods_id_present": bool(goods_id),
        "code_count": len(product_codes),
        "api_score": _api_score(api_match),
        "image_count": len(image_urls),
        "reasons": reasons,
    }


def build_image_candidates(
    image_urls: list | tuple | None = None,
    api_urls: list | tuple | None = None,
    dom_urls: list | tuple | None = None,
    downloaded_files: list | tuple | None = None,
    max_candidates: int = 24,
) -> list[dict]:
    buckets = [
        ("api", list(api_urls or []), 88),
        ("downloaded", list(downloaded_files or []), 92),
        ("final", list(image_urls or []), 80),
        ("dom", list(dom_urls or []), 62),
    ]
    seen = set()
    candidates = []
    rank = 1
    for source, values, confidence in buckets:
        for value in values:
            ref = _normalize_image_ref(value) or str(value or "")
            fp = image_fingerprint(ref)
            key = fp or ref
            if not key or key in seen:
                continue
            seen.add(key)
            candidates.append({
                "rank": rank,
                "source": source,
                "ref": ref,
                "fingerprint": fp,
                "is_local": bool(ref and (os.path.isabs(ref) or os.path.exists(ref))),
                "confidence": confidence,
            })
            rank += 1
            if len(candidates) >= max_candidates:
                return candidates
    return candidates


def _price_from_any(value: Any) -> str:
    if value in ("", "-", "0", 0, None):
        return ""
    matches = re.findall(r"\d{2,4}", str(value))
    return matches[0] if matches else ""


def build_price_candidates(
    text_price: Any = None,
    text_source: str = "text",
    ocr_payload: dict | None = None,
    policy: dict | None = None,
    defaults: list | tuple | None = None,
) -> list[dict]:
    candidates = []
    seen = set()

    def add(value: Any, source: str, confidence: int, reason: str = ""):
        price = _price_from_any(value)
        if not price or price in seen:
            return
        seen.add(price)
        candidates.append({
            "price": price,
            "source": source,
            "confidence": int(confidence),
            "reason": reason,
        })

    add(text_price, text_source or "text", 92, "explicit_text_price")

    if isinstance(ocr_payload, dict):
        for item in ocr_payload.get("candidates") or []:
            if isinstance(item, dict):
                add(item.get("price"), "ocr", 58, item.get("context", "image_ocr_candidate"))

    policy = policy if isinstance(policy, dict) else {}
    default_values = list(defaults or [])
    default_values.extend([
        policy.get("default_price"),
        policy.get("vendor_default_price"),
        policy.get("fallback_price"),
    ])
    for value in default_values:
        add(value, "vendor_default", 45, "policy_default_candidate")

    if not candidates:
        candidates.append({
            "price": "",
            "source": "missing",
            "confidence": 0,
            "reason": "no_price_candidate",
        })
    return candidates[:8]


def build_post_evidence(
    raw_text: str = "",
    item_key: str = "",
    goods_id: str = "",
    shop_id: str = "",
    role: str = "main",
    codes: list | tuple | None = None,
    api_match: dict | None = None,
    identity: dict | None = None,
    price_candidates: list | tuple | None = None,
    image_candidates: list | tuple | None = None,
    candidate_score: float | int | None = None,
    candidate_reasons: list | tuple | None = None,
    decision_stage: str = "",
) -> dict:
    codes = list(codes or [])
    identity = identity or score_identity_confidence(
        item_key=item_key,
        goods_id=goods_id,
        product_codes=codes,
        api_match=api_match,
        image_urls=[c.get("ref") for c in image_candidates or [] if isinstance(c, dict)],
    )
    payload = {
        "version": EVIDENCE_VERSION,
        "item_key": item_key or "",
        "goods_id": goods_id or "",
        "shop_id": shop_id or "",
        "role": role or "main",
        "codes": codes,
        "identity": identity,
        "api_match": api_match or {},
        "price_candidates": list(price_candidates or []),
        "image_candidates": list(image_candidates or []),
        "raw_text_len": len(raw_text or ""),
        "raw_text_preview": _clean_text(raw_text, 220),
        "decision_stage": decision_stage or "",
    }
    if candidate_score is not None:
        payload["candidate_score"] = candidate_score
    if candidate_reasons is not None:
        payload["candidate_reasons"] = list(candidate_reasons or [])
    return payload
