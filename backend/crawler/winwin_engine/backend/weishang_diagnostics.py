import datetime
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover - optional at import time
    BeautifulSoup = None


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
SNAPSHOT_DIR = PROJECT_ROOT / "data" / "weishang_snapshots"


def _safe_slug(value: str, fallback: str = "snapshot") -> str:
    text = re.sub(r"[^\w가-힣.-]+", "_", str(value or "").strip(), flags=re.UNICODE)
    text = text.strip("._-")
    return (text or fallback)[:48]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _load_json(path: Path, default: Any = None) -> Any:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_weishang_snapshot(
    vendor_id: str,
    vendor_name: str,
    vendor_url: str,
    html: str,
    api_data: dict | None = None,
    api_list: list | None = None,
    item_count: int = 0,
    metadata: dict | None = None,
) -> str:
    """Save one vendor-page capture so crawler decisions can be replayed offline."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now()
    seed = f"{vendor_id}|{vendor_url}|{now.isoformat(timespec='seconds')}"
    short_hash = hashlib.sha1(seed.encode("utf-8", errors="ignore")).hexdigest()[:8]
    snapshot_id = f"{now.strftime('%Y%m%d_%H%M%S')}_{_safe_slug(vendor_name or vendor_id)}_{short_hash}"

    html_path = SNAPSHOT_DIR / f"{snapshot_id}.html"
    api_path = SNAPSHOT_DIR / f"{snapshot_id}.api.json"
    manifest_path = SNAPSHOT_DIR / f"{snapshot_id}.json"

    html_path.write_text(html or "", encoding="utf-8")
    api_payload = {
        "feedApiData": _json_safe(api_data or {}),
        "feedApiDataList": _json_safe(api_list or []),
    }
    api_path.write_text(json.dumps(api_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest = {
        "id": snapshot_id,
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "vendor_id": vendor_id or "",
        "vendor_name": vendor_name or "",
        "vendor_url": vendor_url or "",
        "item_count": int(item_count or 0),
        "api_map_count": len(api_payload["feedApiData"]) if isinstance(api_payload["feedApiData"], dict) else 0,
        "api_list_count": len(api_payload["feedApiDataList"]) if isinstance(api_payload["feedApiDataList"], list) else 0,
        "html_file": html_path.name,
        "api_file": api_path.name,
        "metadata": _json_safe(metadata or {}),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return snapshot_id


def list_weishang_snapshots(limit: int = 80) -> list[dict]:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    manifests = []
    for path in SNAPSHOT_DIR.glob("*.json"):
        if path.name.endswith(".api.json"):
            continue
        data = _load_json(path, {})
        if isinstance(data, dict) and data.get("id"):
            manifests.append(data)
    manifests.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
    return manifests[: max(1, int(limit or 80))]


def load_weishang_snapshot(snapshot_id: str, include_html: bool = False, include_api: bool = True) -> dict | None:
    snapshot_id = _safe_slug(snapshot_id, "")
    if not snapshot_id:
        return None
    manifest_path = SNAPSHOT_DIR / f"{snapshot_id}.json"
    manifest = _load_json(manifest_path)
    if not isinstance(manifest, dict):
        return None

    result = dict(manifest)
    if include_html:
        html_path = SNAPSHOT_DIR / str(manifest.get("html_file") or f"{snapshot_id}.html")
        try:
            result["html"] = html_path.read_text(encoding="utf-8")
        except Exception:
            result["html"] = ""
    if include_api:
        api_path = SNAPSHOT_DIR / str(manifest.get("api_file") or f"{snapshot_id}.api.json")
        result["api"] = _load_json(api_path, {"feedApiData": {}, "feedApiDataList": []})
    return result


def _metadata_from_event(event: dict) -> dict:
    metadata = event.get("metadata")
    if isinstance(metadata, dict):
        return metadata
    metadata_json = event.get("metadata_json")
    if isinstance(metadata_json, str):
        try:
            return json.loads(metadata_json)
        except Exception:
            return {}
    return {}


def _identity_key_type(metadata: dict) -> str:
    identity = metadata.get("identity")
    if isinstance(identity, dict) and identity.get("key_type"):
        return str(identity.get("key_type"))
    evidence = metadata.get("evidence")
    if isinstance(evidence, dict):
        ev_identity = evidence.get("identity")
        if isinstance(ev_identity, dict) and ev_identity.get("key_type"):
            return str(ev_identity.get("key_type"))
    item_key = str(metadata.get("item_key") or metadata.get("key") or "")
    if ":goods:" in item_key:
        return "goods_id"
    if ":code:" in item_key:
        return "product_code"
    if ":api:" in item_key:
        return "api_packet"
    if ":img:" in item_key:
        return "image_fingerprint"
    if ":dom:" in item_key:
        return "dom_index"
    if ":text:" in item_key:
        return "raw_text"
    if metadata.get("goods_id"):
        return "goods_id"
    if metadata.get("codes"):
        return "product_code"
    if metadata.get("api_hit") or metadata.get("api_match"):
        return "api_packet"
    if metadata.get("image_fingerprints"):
        return "image_fingerprint"
    return "unknown"


def summarize_identity_stats(events: list[dict]) -> dict:
    """Summarize how each vendor identifies posts: goods_id/API/text/image/etc."""
    overall_types = Counter()
    overall_events = Counter()
    by_vendor: dict[str, dict] = defaultdict(lambda: {
        "vendor_id": "",
        "vendor_name": "",
        "total": 0,
        "goods_id_present": 0,
        "api_hit": 0,
        "item_key_types": Counter(),
        "event_types": Counter(),
    })

    for event in events or []:
        metadata = _metadata_from_event(event)
        key_type = _identity_key_type(metadata)
        event_type = str(event.get("event_type") or "")
        vendor_id = str(event.get("vendor_id") or "unknown")
        vendor_name = str(event.get("vendor_name") or "")

        overall_types[key_type] += 1
        overall_events[event_type] += 1

        row = by_vendor[vendor_id]
        row["vendor_id"] = vendor_id
        row["vendor_name"] = vendor_name
        row["total"] += 1
        row["item_key_types"][key_type] += 1
        row["event_types"][event_type] += 1
        if metadata.get("goods_id"):
            row["goods_id_present"] += 1
        if metadata.get("api_hit") or metadata.get("api_match"):
            row["api_hit"] += 1

    vendor_rows = []
    for row in by_vendor.values():
        total = max(1, row["total"])
        vendor_rows.append({
            "vendor_id": row["vendor_id"],
            "vendor_name": row["vendor_name"],
            "total": row["total"],
            "goods_id_present": row["goods_id_present"],
            "goods_id_rate": round(row["goods_id_present"] / total * 100, 1),
            "api_hit": row["api_hit"],
            "api_hit_rate": round(row["api_hit"] / total * 100, 1),
            "item_key_types": dict(row["item_key_types"]),
            "event_types": dict(row["event_types"]),
        })
    vendor_rows.sort(key=lambda x: (x["goods_id_rate"], -x["total"]))

    return {
        "overall": {
            "total_events": sum(overall_events.values()),
            "item_key_types": dict(overall_types),
            "event_types": dict(overall_events),
        },
        "vendors": vendor_rows,
    }


def _role_from_text(raw_text: str) -> str:
    text = str(raw_text or "")
    compact = re.sub(r"\s+", "", text)
    if any(k in text for k in ["合集", "集合", "汇总", "图集", "合辑", "大全", "目录"]) and len(compact) <= 80:
        return "collection"
    if any(k in text for k in ["尺码表", "尺寸表", "尺码图", "尺寸图", "规格表", "SIZE CHART", "size chart"]):
        return "size"
    if any(k in text for k in ["官网图", "官图", "官网", "Official", "official"]):
        return "official"
    if any(k in text for k in ["专柜图", "柜台图", "专柜", "柜台"]):
        return "counter"
    if any(k in text for k in ["模特图", "上身图", "模特", "上身", "试穿"]):
        return "model"
    if any(k in text for k in ["细节", "细节图", "实拍", "特写", "五金", "走线", "内里"]):
        return "detail"
    if any(k in text for k in ["包装", "盒子", "吊牌"]):
        return "packaging"
    return "main"


def replay_snapshot(snapshot_id: str) -> dict:
    """Lightweight replay: parse saved HTML/API and show what the crawler would classify."""
    snapshot = load_weishang_snapshot(snapshot_id, include_html=True, include_api=True)
    if not snapshot:
        return {"status": "error", "message": "스냅샷을 찾을 수 없습니다."}
    if BeautifulSoup is None:
        return {"status": "error", "message": "BeautifulSoup을 사용할 수 없습니다."}

    soup = BeautifulSoup(snapshot.get("html") or "", "html.parser")
    items = soup.find_all("div", class_=lambda c: c and "normalItemContent" in c)
    api = snapshot.get("api") or {}
    api_list = api.get("feedApiDataList") if isinstance(api.get("feedApiDataList"), list) else []
    replay_items = []
    role_counter = Counter()
    goods_id_count = 0

    for idx, item in enumerate(items):
        raw_text = item.get_text("\n", strip=True)
        role = _role_from_text(raw_text)
        data_blob = " ".join(str(v) for v in item.attrs.values())
        goods_id = ""
        match = re.search(r"[\"']?(?:goods_id|goodsId|id)[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9_-]{5,})", data_blob)
        if match:
            goods_id = match.group(1)
        if not goods_id and idx < len(api_list) and isinstance(api_list[idx], dict):
            for key in ("goods_id", "goodsId", "id", "goods_no", "goodsNo"):
                if api_list[idx].get(key):
                    goods_id = str(api_list[idx].get(key))
                    break
        if goods_id:
            goods_id_count += 1
        role_counter[role] += 1
        replay_items.append({
            "index": idx,
            "role": role,
            "goods_id": goods_id,
            "api_index_available": idx < len(api_list),
            "raw_text_len": len(raw_text),
            "raw_text_preview": re.sub(r"\s+", " ", raw_text)[:160],
        })

    return {
        "status": "success",
        "snapshot": {k: snapshot.get(k) for k in ["id", "created_at", "vendor_id", "vendor_name", "vendor_url", "item_count"]},
        "summary": {
            "html_items": len(items),
            "api_list_items": len(api_list),
            "goods_id_present": goods_id_count,
            "goods_id_rate": round(goods_id_count / max(1, len(items)) * 100, 1),
            "roles": dict(role_counter),
        },
        "items": replay_items,
    }


def simulate_decision_trace(products: list[dict]) -> dict:
    role_counter = Counter()
    decision_counter = Counter()
    key_type_counter = Counter()
    identity_confidence_counter = Counter()
    price_candidate_sources = Counter()
    image_candidate_sources = Counter()
    over_20_images = []
    missing_price = []
    low_identity_samples = []
    multi_post_products = 0

    for idx, product in enumerate(products or [], start=1):
        image_count = len(product.get("image_files") or product.get("image_urls") or [])
        if image_count > 20:
            over_20_images.append({"index": idx, "title": product.get("title", ""), "image_count": image_count})
        price_value = str(product.get("price_input") or product.get("price") or "").strip()
        if price_value in {"", "-", "0", "단가미상"}:
            missing_price.append({"index": idx, "title": product.get("title", ""), "vendor": product.get("vendor_name", "")})

        source_posts = product.get("source_posts") if isinstance(product.get("source_posts"), list) else []
        if len(source_posts) >= 2:
            multi_post_products += 1
        for post in source_posts:
            role_counter[str(post.get("role") or "unknown")] += 1
            evidence = post.get("evidence") if isinstance(post.get("evidence"), dict) else {}
            identity = post.get("identity") if isinstance(post.get("identity"), dict) else evidence.get("identity", {})
            key_type_counter[_identity_key_type({
                "item_key": post.get("item_key"),
                "goods_id": post.get("goods_id"),
                "codes": post.get("codes"),
                "api_match": post.get("api_match"),
                "identity": identity,
                "evidence": evidence,
            })] += 1
            try:
                confidence = int((identity or {}).get("confidence") or 0)
            except Exception:
                confidence = 0
            if confidence >= 90:
                identity_confidence_counter["verified_90_plus"] += 1
            elif confidence >= 70:
                identity_confidence_counter["strong_70_89"] += 1
            elif confidence >= 50:
                identity_confidence_counter["weak_50_69"] += 1
            else:
                identity_confidence_counter["fragile_under_50"] += 1
                if len(low_identity_samples) < 10:
                    low_identity_samples.append({
                        "index": idx,
                        "title": product.get("title", ""),
                        "item_key": post.get("item_key", ""),
                        "confidence": confidence,
                        "key_type": (identity or {}).get("key_type", ""),
                        "raw_text_preview": post.get("raw_text_preview", ""),
                    })
            for candidate in (post.get("price_candidates") or evidence.get("price_candidates") or []):
                if isinstance(candidate, dict):
                    price_candidate_sources[str(candidate.get("source") or "unknown")] += 1
            for candidate in (post.get("image_candidates") or evidence.get("image_candidates") or []):
                if isinstance(candidate, dict):
                    image_candidate_sources[str(candidate.get("source") or "unknown")] += 1

        if not source_posts:
            for evidence in (product.get("evidence_items") or [])[:6]:
                if not isinstance(evidence, dict):
                    continue
                identity = evidence.get("identity", {})
                key_type_counter[_identity_key_type({"identity": identity, "evidence": evidence})] += 1
                for candidate in evidence.get("price_candidates") or []:
                    if isinstance(candidate, dict):
                        price_candidate_sources[str(candidate.get("source") or "unknown")] += 1
                for candidate in evidence.get("image_candidates") or []:
                    if isinstance(candidate, dict):
                        image_candidate_sources[str(candidate.get("source") or "unknown")] += 1
        traces = product.get("decision_trace") if isinstance(product.get("decision_trace"), list) else []
        for trace in traces:
            decision_counter[str(trace.get("decision") or "unknown")] += 1

    total = len(products or [])
    recommendations = []
    if missing_price:
        recommendations.append({
            "target": "price_policy",
            "rule": "본문 가격 미감지 시 OCR/업체 기본가 후보를 확정 전 후보 상태로 남김",
            "impact_count": len(missing_price),
        })
    if over_20_images:
        recommendations.append({
            "target": "image_policy",
            "rule": "20장 초과 상품은 main 앞/뒤, detail, size 순서로 대표컷 압축",
            "impact_count": len(over_20_images),
        })
    if role_counter.get("size") or role_counter.get("official") or role_counter.get("counter") or role_counter.get("model"):
        recommendations.append({
            "target": "boundary_policy",
            "rule": "size/official/counter/model 포스팅은 새 상품보다 보충 포스팅으로 우선 판단",
            "impact_count": sum(role_counter.get(k, 0) for k in ["size", "official", "counter", "model"]),
        })
    if key_type_counter.get("unknown", 0) > max(3, total // 3):
        recommendations.append({
            "target": "identity_policy",
            "rule": "goods_id 미확보 상품은 API index + 이미지 fingerprint + 핵심어 조합으로 item_key 생성",
            "impact_count": key_type_counter.get("unknown", 0),
        })
    fragile_count = identity_confidence_counter.get("fragile_under_50", 0)
    if fragile_count:
        recommendations.append({
            "target": "identity_confidence",
            "rule": "식별 신뢰도 50 미만 포스팅은 goods_id/API 매칭 또는 이미지 fingerprint 보강 전 확정 중복 처리 금지",
            "impact_count": fragile_count,
        })
    if price_candidate_sources.get("missing", 0):
        recommendations.append({
            "target": "price_candidates",
            "rule": "missing 가격 후보가 남은 상품은 OCR/업체 기본가/identifier_tail_price 중 하나를 후보로 추가하고 확정값과 후보값을 분리",
            "impact_count": price_candidate_sources.get("missing", 0),
        })
    if image_candidate_sources and not image_candidate_sources.get("api", 0):
        recommendations.append({
            "target": "image_source_priority",
            "rule": "API 원본 이미지 후보가 없는 업체는 DOM/다운로드 버튼 매칭 실패 원인을 별도 추적",
            "impact_count": sum(image_candidate_sources.values()),
        })

    return {
        "total_products": total,
        "multi_post_products": multi_post_products,
        "source_post_roles": dict(role_counter),
        "decision_counts": dict(decision_counter),
        "identity_key_types": dict(key_type_counter),
        "identity_confidence_buckets": dict(identity_confidence_counter),
        "price_candidate_sources": dict(price_candidate_sources),
        "image_candidate_sources": dict(image_candidate_sources),
        "missing_price_count": len(missing_price),
        "over_20_images_count": len(over_20_images),
        "samples": {
            "missing_price": missing_price[:10],
            "over_20_images": over_20_images[:10],
            "low_identity": low_identity_samples[:10],
        },
        "recommended_rule_updates": recommendations,
    }


def extract_price_ocr_candidates(image_paths_or_urls: list[str], max_images: int = 3) -> dict:
    """Best-effort OCR hook. It is safe when OCR dependencies are absent."""
    local_paths = [p for p in (image_paths_or_urls or []) if p and os.path.exists(str(p))][: max(1, int(max_images or 3))]
    if not local_paths:
        return {"status": "skipped", "reason": "local_image_not_available", "candidates": []}

    try:
        import pytesseract
        from PIL import Image
    except Exception:
        return {"status": "unavailable", "reason": "pytesseract_or_pillow_not_installed", "candidates": []}

    candidates = []
    text_chunks = []
    pattern = re.compile(r"(?:¥|￥|P|p|W|w|Q|q|价|批|拿货|出货|💰)\s*[:：]?\s*(\d{2,4})")
    for path in local_paths:
        try:
            text = pytesseract.image_to_string(Image.open(path), lang="chi_sim+eng")
        except Exception:
            continue
        text_chunks.append(text[:600])
        for match in pattern.finditer(text):
            value = int(match.group(1))
            if 10 <= value <= 3000:
                candidates.append({
                    "price": value,
                    "source_file": os.path.basename(path),
                    "context": text[max(0, match.start() - 20): match.end() + 20].replace("\n", " ")[:100],
                })

    unique = []
    seen = set()
    for item in candidates:
        key = (item["price"], item["source_file"])
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return {
        "status": "success" if unique else "no_candidate",
        "candidates": unique[:10],
        "ocr_text_preview": "\n---\n".join(text_chunks)[:1200],
    }
