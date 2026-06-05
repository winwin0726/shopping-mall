"""FTP 업로드 유틸"""

from __future__ import annotations

import json
import os
import posixpath

from ftplib import FTP

def load_luxboom_ftp_config(config_path: str = None) -> dict:
    """FTP 설정 로드
    - 기본: winwin47.py와 같은 폴더에 luxboom_ftp.json 파일 사용
    - 파일이 없거나 필수값이 없으면 {} 반환
    """
    try:
        if not config_path:
            config_path = os.path.join(os.path.dirname(__file__), "luxboom_ftp.json")

        if not os.path.exists(config_path):
            return {}

        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        # 필수 키 체크
        required = ["host", "user", "password"]
        if any(k not in cfg or not str(cfg.get(k, "")).strip() for k in required):
            return {}

        # 기본값
        cfg.setdefault("port", 21)
        cfg.setdefault("timeout", 20)
        cfg.setdefault("passive", True)
        # 서버에서 item 이미지가 위치할 기본 경로 (대부분: data/item)
        cfg.setdefault("remote_item_root", "data/item")
        # FTP 접속 후 시작 경로 (예: public_html, www 등). 비워두면 루트 그대로
        cfg.setdefault("ftp_root_dir", "")
        # FTPS 사용 여부 (필요하면 true)
        cfg.setdefault("use_tls", False)

        return cfg
    except Exception:
        return {}




def _ftp_connect(cfg: dict, log_func=None):
    """FTP(또는 FTPS) 접속 객체 생성
    ✅ 중요: ftp_root_dir 이동 실패를 '조용히 무시'하면
             업로드가 엉뚱한 폴더(/home/계정 등)에 들어가서
             '성공'으로 보이는데 실제 public_html에는 없게 됩니다.
    """
    host = cfg["host"]
    port = int(cfg.get("port", 21))
    timeout = int(cfg.get("timeout", 20))
    use_tls = bool(cfg.get("use_tls", False))

    if use_tls:
        ftp = FTP_TLS()
        ftp.connect(host, port, timeout=timeout)
        ftp.login(cfg["user"], cfg["password"])
        # 데이터 채널도 암호화
        ftp.prot_p()
    else:
        ftp = FTP()
        ftp.connect(host, port, timeout=timeout)
        ftp.login(cfg["user"], cfg["password"])

    ftp.set_pasv(bool(cfg.get("passive", True)))

    # ✅ 현재 위치 로그
    try:
        if log_func:
            log_func(f"FTP 접속 위치(pwd): {ftp.pwd()}")
    except Exception:
        pass

    root_dir = str(cfg.get("ftp_root_dir", "")).strip().strip("/")
    if root_dir:
        moved = False
        last_err = ""
        # 1) 상대 경로 이동 시도 (예: public_html)
        try:
            ftp.cwd(root_dir)
            moved = True
        except Exception as e:
            last_err = str(e)

        # 2) 절대 경로 이동 시도 (예: /public_html)
        if not moved:
            try:
                ftp.cwd("/" + root_dir)
                moved = True
            except Exception as e:
                last_err = str(e)

        if not moved:
            cur = "?"
            try:
                cur = ftp.pwd()
            except Exception:
                pass
            # ✅ 여기서 실패를 '명확히' 알려야, 업로드가 다른 곳으로 새는 걸 막습니다.
            raise Exception(f"FTP root_dir 이동 실패: '{root_dir}' (현재:{cur}) / luxboom_ftp.json의 ftp_root_dir 확인 필요. (예: public_html) / 원인:{last_err}")

        try:
            if log_func:
                log_func(f"FTP root_dir 이동 완료 → pwd: {ftp.pwd()}")
        except Exception:
            pass

    return ftp




def _ftp_ensure_dir(ftp, remote_dir: str):
    """원격 폴더가 없으면 생성 (data/item/카테고리/날짜 같은 다단계 지원)"""
    remote_dir = remote_dir.replace("\\", "/").strip("/")
    if not remote_dir:
        return

    parts = [p for p in remote_dir.split("/") if p]
    for p in parts:
        try:
            ftp.cwd(p)
        except Exception:
            try:
                ftp.mkd(p)
            except Exception:
                # 동시 생성/권한 등으로 실패해도 한번 더 cwd 시도
                pass
            ftp.cwd(p)




def ftp_upload_folder(local_folder: str, remote_dir: str, cfg: dict, log_func=None) -> bool:
    """local_folder 안의 파일을 FTP로 업로드"""
    if not cfg:
        if log_func:
            log_func("FTP 설정(luxboom_ftp.json)이 없어 업로드를 건너뜁니다.")
        return False

    if not os.path.isdir(local_folder):
        if log_func:
            log_func(f"FTP 업로드 실패: 로컬 폴더가 없습니다. ({local_folder})")
        return False

    try:
        ftp = _ftp_connect(cfg, log_func=log_func)

        # ✅ 폴더 생성 후 이동
        _ftp_ensure_dir(ftp, remote_dir)

        # 현재 위치가 remote_dir 최종 폴더가 됨
        files = sorted([f for f in os.listdir(local_folder) if os.path.isfile(os.path.join(local_folder, f))])

        for name in files:
            local_path = os.path.join(local_folder, name)
            with open(local_path, "rb") as fp:
                ftp.storbinary(f"STOR {name}", fp)

        ftp.quit()

        if log_func:
            log_func(f"FTP 업로드 완료: {remote_dir} (파일 {len(files)}개)")
        return True

    except Exception as e:
        if log_func:
            log_func(f"FTP 업로드 오류: {e}")
        return False



########################################
# 12-1) FTP 업로드 (상세/동시 업로드/결과 리포트)
########################################

