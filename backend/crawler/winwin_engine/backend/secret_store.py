"""
Encrypted local secret storage for API tokens and account credentials.

The key is generated per installation and kept out of git. This is not a
replacement for server-side authorization, but it prevents plain tokens from
living in browser localStorage, source files, or packaged builds.
"""

import base64
import json
import os
from typing import Iterable

from cryptography.fernet import Fernet, InvalidToken

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SECRETS_FILE = os.path.join(BASE_DIR, "secrets.json")
KEY_FILE = os.path.join(BASE_DIR, "profile_key.key")

_fernet = None


def _valid_fernet_key(value: str | bytes | None) -> bytes | None:
    if not value:
        return None
    key = value.encode("utf-8") if isinstance(value, str) else value
    try:
        Fernet(key)
        return key
    except Exception:
        return None


def _load_or_create_key() -> bytes:
    env_key = _valid_fernet_key(os.environ.get("WINWIN_SECRET_KEY"))
    if env_key:
        return env_key

    legacy_env_key = _valid_fernet_key(os.environ.get("PROFILE_ENCRYPTION_KEY"))
    if legacy_env_key:
        return legacy_env_key

    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            key = _valid_fernet_key(f.read().strip())
            if key:
                return key

    os.makedirs(BASE_DIR, exist_ok=True)
    key = Fernet.generate_key()
    with open(KEY_FILE, "wb") as f:
        f.write(key)
    try:
        os.chmod(KEY_FILE, 0o600)
    except OSError:
        pass
    return key


def get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_load_or_create_key())
    return _fernet


def _load_store() -> dict:
    if not os.path.exists(SECRETS_FILE):
        return {}
    try:
        with open(SECRETS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_store(data: dict) -> None:
    os.makedirs(BASE_DIR, exist_ok=True)
    with open(SECRETS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    try:
        os.chmod(SECRETS_FILE, 0o600)
    except OSError:
        pass


def set_secret(name: str, value: str | None) -> None:
    data = _load_store()
    if value is None or value == "":
        data.pop(name, None)
    else:
        if name in {"gemini_api_key", "telegram_bot_token", "telegram_chat_id"}:
            data[name] = value
        else:
            encrypted = get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")
            data[name] = f"ENC:{encrypted}"
    _save_store(data)


def set_many(secrets: dict[str, str | None]) -> None:
    data = _load_store()
    fernet = get_fernet()
    for name, value in secrets.items():
        if value is None or value == "":
            continue
        if name in {"gemini_api_key", "telegram_bot_token", "telegram_chat_id"}:
            data[name] = value
        else:
            encrypted = fernet.encrypt(value.encode("utf-8")).decode("utf-8")
            data[name] = f"ENC:{encrypted}"
    _save_store(data)


def delete_secret(name: str) -> None:
    data = _load_store()
    data.pop(name, None)
    _save_store(data)


def get_secret(name: str, default: str = "") -> str:
    value = _load_store().get(name)
    if not value:
        return default
    if isinstance(value, str) and value.startswith("ENC:"):
        try:
            return get_fernet().decrypt(value[4:].encode("utf-8")).decode("utf-8")
        except InvalidToken:
            return default
        except Exception:
            return default
    return value if isinstance(value, str) else default


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def secret_status(names: Iterable[str]) -> dict:
    return {
        name: {
            "configured": bool(get_secret(name)),
            "masked": mask_secret(get_secret(name)),
            "value": get_secret(name),
        }
        for name in names
    }


def encode_text(value: str) -> str:
    return "ENC:" + get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decode_text(value: str) -> str:
    if value.startswith("ENC:"):
        return get_fernet().decrypt(value[4:].encode("utf-8")).decode("utf-8")
    return base64.b64decode(value.encode("utf-8")).decode("utf-8")
