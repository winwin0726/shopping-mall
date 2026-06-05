import hashlib
import json
import os
import uuid
from urllib import request

try:
    from backend.secret_store import delete_secret, get_secret, mask_secret, set_secret
except ImportError:
    from secret_store import delete_secret, get_secret, mask_secret, set_secret

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LEGACY_LICENSE_FILE = os.path.join(BASE_DIR, "license.json")
LICENSE_SECRET_NAME = "license_key"


def get_hardware_id() -> str:
    """PC 고유 하드웨어 ID 추출 (MAC 주소 기반)."""
    mac = uuid.getnode()
    hash_str = hashlib.md5(str(mac).encode("utf-8")).hexdigest().upper()
    return f"HWID-{hash_str[:4]}-{hash_str[4:8]}-{hash_str[8:12]}"


def _hash_license_key(license_key: str) -> str:
    return hashlib.sha256(license_key.encode("utf-8")).hexdigest()


def _verify_with_server(license_key: str, hwid: str) -> dict | None:
    verify_url = os.environ.get("WINWIN_LICENSE_VERIFY_URL", "").strip()
    if not verify_url:
        return None

    payload = json.dumps({"license_key": license_key, "hwid": hwid}).encode("utf-8")
    req = request.Request(
        verify_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("is_valid") or data.get("valid"):
        return {"is_valid": True, "mode": "server", "message": data.get("message", "서버 인증 완료")}
    return {"is_valid": False, "mode": "server", "message": data.get("message", "서버 인증 실패")}


def _verify_with_local_allowlist(license_key: str) -> dict | None:
    allowlist = [x.strip() for x in os.environ.get("WINWIN_LICENSE_KEYS", "").split(",") if x.strip()]
    if not allowlist:
        return None

    digest = _hash_license_key(license_key)
    if license_key in allowlist or digest in allowlist:
        return {"is_valid": True, "mode": "local-allowlist", "message": "로컬 허용 목록 인증 완료"}
    return {"is_valid": False, "mode": "local-allowlist", "message": "허용되지 않은 라이선스 키입니다."}


def verify_license(license_key: str, hwid: str | None = None) -> dict:
    """라이선스 키를 서버 또는 로컬 허용 목록으로 검증한다."""
    if not license_key:
        return {"is_valid": False, "mode": "none", "message": "라이선스 키가 없습니다."}

    hwid = hwid or get_hardware_id()
    try:
        server_result = _verify_with_server(license_key, hwid)
        if server_result is not None:
            return server_result
    except Exception as exc:
        return {"is_valid": False, "mode": "server", "message": f"서버 인증 오류: {exc}"}

    allowlist_result = _verify_with_local_allowlist(license_key)
    if allowlist_result is not None:
        return allowlist_result

    # 개발/오프라인 호환 경로. 실제 배포에서는 WINWIN_LICENSE_VERIFY_URL 또는
    # WINWIN_LICENSE_KEYS를 설정해 이 경로에 의존하지 않도록 한다.
    if license_key.startswith("WINWIN-PRO-"):
        return {"is_valid": True, "mode": "legacy-offline", "message": "오프라인 호환 인증 완료"}
    return {"is_valid": False, "mode": "legacy-offline", "message": "유효하지 않거나 만료된 라이선스 키입니다."}


def _migrate_legacy_license() -> str:
    existing = get_secret(LICENSE_SECRET_NAME)
    if existing or not os.path.exists(LEGACY_LICENSE_FILE):
        return existing
    try:
        with open(LEGACY_LICENSE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        legacy_key = data.get("license_key", "")
        if legacy_key:
            set_secret(LICENSE_SECRET_NAME, legacy_key)
            return legacy_key
    except Exception:
        return ""
    return ""


def check_license_status() -> dict:
    """현재 로컬에 저장된 라이선스 정보가 이 PC에 유효한지 검증."""
    hwid = get_hardware_id()
    saved_key = _migrate_legacy_license()
    if not saved_key:
        return {"is_valid": False, "hwid": hwid, "configured": False, "message": "라이선스 정보가 없습니다."}

    result = verify_license(saved_key, hwid)
    result.update({
        "hwid": hwid,
        "configured": True,
        "license_key_masked": mask_secret(saved_key),
    })
    return result


def register_license(license_key: str) -> dict:
    """사용자가 입력한 새 라이선스 키를 검증하고 암호화 저장."""
    hwid = get_hardware_id()
    result = verify_license(license_key, hwid)
    if result.get("is_valid"):
        set_secret(LICENSE_SECRET_NAME, license_key)
        return {
            "status": "success",
            "message": "라이선스가 정상적으로 등록되었습니다.",
            "hwid": hwid,
            "mode": result.get("mode"),
            "license_key_masked": mask_secret(license_key),
        }
    return {"status": "error", "message": result.get("message", "유효하지 않은 라이선스 키입니다."), "hwid": hwid}


def unregister_license() -> dict:
    """라이선스 연동 해제."""
    delete_secret(LICENSE_SECRET_NAME)
    return {"status": "success", "message": "기기 등록이 해제되었습니다."}
