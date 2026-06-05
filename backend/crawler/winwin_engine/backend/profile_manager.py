"""
profile_manager.py
──────────────────
카카오스토리 / 네이버밴드 계정 프로필 CRUD 관리.
비밀번호는 Base64 인코딩으로 저장하여 평문 노출 방지.
"""

import os
import json
from datetime import datetime
from dotenv import load_dotenv

try:
    from backend.secret_store import decode_text, encode_text
except ImportError:
    from secret_store import decode_text, encode_text

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(os.path.dirname(_PROJECT_ROOT), ".env"))

_PROFILES_PATH = os.path.join(os.path.dirname(_PROJECT_ROOT), "profiles.json")


def _load() -> dict:
    """profiles.json을 읽어서 dict를 반환한다."""
    if os.path.exists(_PROFILES_PATH):
        try:
            with open(_PROFILES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"kakao": [], "band": []}


def _save(data: dict):
    """dict를 profiles.json에 저장한다."""
    with open(_PROFILES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _encode_pw(pw: str) -> str:
    return encode_text(pw)


def _decode_pw(encoded: str) -> str:
    try:
        return decode_text(encoded)
    except Exception:
        return encoded  # 이미 평문이면 그대로 반환


def list_profiles(platform: str = None) -> dict:
    """
    프로필 목록을 반환한다.
    비밀번호는 마스킹(****) 처리하여 반환.
    """
    data = _load()
    result = {}
    platforms = [platform] if platform else ["kakao", "band"]
    for p in platforms:
        items = data.get(p, [])
        masked = []
        for i, item in enumerate(items):
            masked.append({
                "index": i,
                "name": item.get("name", ""),
                "login_id": item.get("login_id", ""),
                "login_pw_masked": "••••••",
                "created_at": item.get("created_at", ""),
                "last_used": item.get("last_used", ""),
            })
        result[p] = masked
    return result


def add_profile(platform: str, name: str, login_id: str, login_pw: str) -> dict:
    """새 프로필을 추가한다."""
    data = _load()
    if platform not in data:
        data[platform] = []

    profile = {
        "name": name,
        "login_id": login_id,
        "login_pw": _encode_pw(login_pw),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "last_used": "",
    }
    data[platform].append(profile)
    _save(data)
    return {"status": "success", "index": len(data[platform]) - 1}


def delete_profile(platform: str, index: int) -> dict:
    """프로필을 삭제한다."""
    data = _load()
    items = data.get(platform, [])
    if 0 <= index < len(items):
        removed = items.pop(index)
        _save(data)
        return {"status": "success", "removed": removed.get("name", "")}
    return {"status": "error", "message": "유효하지 않은 인덱스"}


def update_profile(platform: str, index: int, name: str = None,
                   login_id: str = None, login_pw: str = None) -> dict:
    """프로필을 수정한다."""
    data = _load()
    items = data.get(platform, [])
    if 0 <= index < len(items):
        if name is not None:
            items[index]["name"] = name
        if login_id is not None:
            items[index]["login_id"] = login_id
        if login_pw is not None:
            items[index]["login_pw"] = _encode_pw(login_pw)
        _save(data)
        return {"status": "success"}
    return {"status": "error", "message": "유효하지 않은 인덱스"}


def get_credentials(platform: str, index: int) -> dict | None:
    """
    로그인에 사용할 자격 증명을 반환한다.
    비밀번호를 복호화하여 반환.
    사용 시각을 업데이트.
    """
    data = _load()
    items = data.get(platform, [])
    if 0 <= index < len(items):
        item = items[index]
        # 마지막 사용 시각 업데이트
        item["last_used"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        _save(data)
        return {
            "name": item.get("name", ""),
            "login_id": item.get("login_id", ""),
            "login_pw": _decode_pw(item.get("login_pw", "")),
        }
    return None
