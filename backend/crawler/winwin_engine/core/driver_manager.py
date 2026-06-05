"""core.driver_manager

크롬 버전 감지 + undetected_chromedriver 실행 로직만 분리한 모듈입니다.

중요:
- 이 파일은 "코어" 모듈이므로 PyQt5/UI, 이미지/엑셀, 기타 프로젝트 모듈을 import 하지 않습니다.
- undetected_chromedriver(uc)는 설치가 안 되어 있어도 "import 시점"에 오류가 나지 않도록,
  실제 드라이버를 만들 때(create_uc_driver) 내부에서 import 합니다.
"""

from __future__ import annotations

import os
import re
import subprocess


def get_installed_chrome_major_version():
    """Windows에서 설치된 Chrome의 메이저 버전을 최대한 안전하게 찾습니다.

    - 성공: int (예: 144)
    - 실패: None
    """

    # 1) 레지스트리에서 버전 조회
    reg_keys = [
        r"HKCU\Software\Google\Chrome\BLBeacon",
        r"HKLM\Software\Google\Chrome\BLBeacon",
        r"HKLM\Software\WOW6432Node\Google\Chrome\BLBeacon",
    ]

    for key in reg_keys:
        try:
            out = subprocess.check_output(
                ["reg", "query", key, "/v", "version"],
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
            m = re.search(r"version\s+REG_SZ\s+([0-9.]+)", out, flags=re.IGNORECASE)
            if m:
                ver = m.group(1).strip()
                return int(ver.split(".")[0])
        except Exception:
            pass

    # 2) chrome.exe --version
    candidates = [
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
    ]

    for exe in candidates:
        try:
            if not exe or not os.path.exists(exe):
                continue
            out = subprocess.check_output(
                [exe, "--version"],
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
            m = re.search(r"(\d+)\.(\d+)\.(\d+)\.(\d+)", out)
            if m:
                return int(m.group(1))
        except Exception:
            pass

    return None


def _safe_log(log_func, msg: str):
    if not callable(log_func):
        return
    try:
        # winwin 계열 log_message(msg, level, also_print)
        log_func(msg, "INFO", True)
        return
    except TypeError:
        pass
    except Exception:
        return

    try:
        log_func(msg)
    except Exception:
        return


def create_uc_driver(options, use_subprocess: bool = True, log_func=None):
    """undetected_chromedriver로 Chrome을 띄웁니다.

    - options: selenium Options
    - use_subprocess: uc 옵션
    - log_func: winwin 로그함수(있으면 사용)

    NOTE: uc는 이 함수 내부에서 import 합니다.
    """

    _safe_log(log_func, "undetected_chromedriver 드라이버 준비 중...")

    try:
        import undetected_chromedriver as uc
    except Exception as e:
        raise ModuleNotFoundError(
            "undetected_chromedriver가 설치되어 있지 않습니다.\n"
            "해결: pip install undetected-chromedriver"
        ) from e

    major = get_installed_chrome_major_version()
    if major:
        _safe_log(log_func, f"Chrome 메이저 버전 감지: {major}")

    kwargs = {
        "options": options,
        "use_subprocess": use_subprocess,
    }
    if major:
        kwargs["version_main"] = major

    # ── options에서 --user-data-dir을 추출하여 uc 전용 파라미터로 전달 ──
    # undetected_chromedriver는 options의 --user-data-dir을 무시하므로
    # 반드시 user_data_dir 키워드로 별도 전달해야 프로필이 정상 로드됩니다.
    for arg in (options.arguments if hasattr(options, 'arguments') else []):
        if arg.startswith("--user-data-dir="):
            profile_path = arg.split("=", 1)[1]
            kwargs["user_data_dir"] = profile_path
            _safe_log(log_func, f"프로필 디렉터리 적용: {profile_path}")
            break

    try:
        return uc.Chrome(**kwargs)
    except Exception as e:
        msg = str(e)

        # 예: "This version of ChromeDriver only supports Chrome version 145\nCurrent browser version is 144..."
        cur_m = re.search(r"Current browser version is\s+(\d+)\.", msg)
        cur_major = int(cur_m.group(1)) if cur_m else None

        if ("only supports Chrome version" in msg) or ("Current browser version is" in msg):
            _safe_log(log_func, "드라이버/크롬 버전 불일치 감지 → 캐시 삭제 후 재시도")

            # uc 캐시 드라이버 삭제(자주 있는 문제)
            cache_exe = os.path.join(
                os.path.expanduser("~"),
                "AppData",
                "Roaming",
                "undetected_chromedriver",
                "undetected_chromedriver.exe",
            )
            try:
                if os.path.exists(cache_exe):
                    os.remove(cache_exe)
                    _safe_log(log_func, f"기존 uc 드라이버 캐시 삭제: {cache_exe}")
            except Exception:
                pass

            retry_major = cur_major or major
            if retry_major:
                try:
                    kwargs["version_main"] = retry_major
                    _safe_log(log_func, f"재시도: version_main={retry_major}")
                    return uc.Chrome(**kwargs)
                except Exception:
                    pass

        # 그 외는 그대로 올려서 호출부에서 처리
        raise
