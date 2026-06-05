import sys
import os
import time
import random
import json
import shutil
import logging
import requests
import re
import traceback
from datetime import datetime, timedelta
import concurrent.futures

from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition, QObject
from PyQt5.QtWidgets import QApplication
import undetected_chromedriver as uc
from PyQt5.QtGui import QColor, QFont
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

# 루트 경로 참조
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class FtpUploadThread(QThread):
    """FTP 업로드를 백그라운드에서 실행하고, 파일별 성공/실패를 UI로 전달"""

    # done, total, ok, fail
    progress = pyqtSignal(int, int, int, int)

    # 파일 1개 결과(dict)
    file_result = pyqtSignal(object)

    # 전체 결과(dict)
    finished_report = pyqtSignal(object)

    def __init__(
        self,
        local_folder: str,
        remote_dir: str,
        cfg: dict,
        workers: int = 4,
        retries: int = 1,
        only_files: list = None,
        parent=None
    ):
        super().__init__(parent)
        self.local_folder = local_folder
        self.remote_dir = remote_dir
        self.cfg = cfg or {}
        self.workers = max(1, int(workers))
        self.retries = max(0, int(retries))
        self.only_files = only_files  # [local_path, ...] 형태(선택)
        self._cancel_event = threading.Event()

    def cancel(self):
        self._cancel_event.set()

    def _list_files(self):
        if self.only_files:
            return [p for p in self.only_files if os.path.isfile(p)]
        if not os.path.isdir(self.local_folder):
            return []
        # ✅ 이미지/정적파일 위주 (필요하면 확장자 추가)
        exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
        files = []
        for name in sorted(os.listdir(self.local_folder)):
            p = os.path.join(self.local_folder, name)
            if os.path.isfile(p):
                if os.path.splitext(name.lower())[1] in exts:
                    files.append(p)
        # 폴더에 이미지가 없으면, 그냥 모든 파일 업로드(보조)
        if not files:
            for name in sorted(os.listdir(self.local_folder)):
                p = os.path.join(self.local_folder, name)
                if os.path.isfile(p):
                    files.append(p)
        return files

    def _ensure_remote_dir(self):
        # 원격 폴더는 1번만 생성/이동 시도(동시 업로드 전에)
        try:
            ftp = _ftp_connect(self.cfg)
            _ftp_ensure_dir(ftp, self.remote_dir)
            ftp.quit()
            return True, ""
        except Exception as e:
            return False, str(e)

    def _upload_one(self, local_path: str):
        name = os.path.basename(local_path)
        size = 0
        try:
            size = os.path.getsize(local_path)
        except Exception:
            pass

        if self._cancel_event.is_set():
            return {
                "file": name,
                "local_path": local_path,
                "size": size,
                "ok": False,
                "error": "사용자 취소",
                "seconds": 0.0,
                "remote_dir": self.remote_dir,
            }

        last_err = ""
        for attempt in range(self.retries + 1):
            try:
                t0 = time.time()
                ftp = _ftp_connect(self.cfg)
                _ftp_ensure_dir(ftp, self.remote_dir)  # 이미 있으면 빠르게 cwd만 수행
                with open(local_path, "rb") as fp:
                    ftp.storbinary(f"STOR {name}", fp)
                ftp.quit()
                dt = time.time() - t0
                return {
                    "file": name,
                    "local_path": local_path,
                    "size": size,
                    "ok": True,
                    "error": "",
                    "seconds": dt,
                    "remote_dir": self.remote_dir,
                    "attempt": attempt + 1,
                }
            except Exception as e:
                last_err = str(e)
                # 재시도 전 짧게 쉬기(서버 과부하 방지)
                time.sleep(0.2)

        return {
            "file": name,
            "local_path": local_path,
            "size": size,
            "ok": False,
            "error": last_err or "알 수 없는 오류",
            "seconds": 0.0,
            "remote_dir": self.remote_dir,
            "attempt": self.retries + 1,
        }

    def run(self):
        files = self._list_files()
        total = len(files)
        done = ok = fail = 0
        results = []

        if total == 0:
            report = {
                "ok": False,
                "message": "업로드할 파일이 없습니다.",
                "total": 0,
                "success": 0,
                "fail": 0,
                "results": [],
                "remote_dir": self.remote_dir,
            }
            self.finished_report.emit(report)
            return

        ensured, err = self._ensure_remote_dir()
        if not ensured:
            report = {
                "ok": False,
                "message": f"원격 폴더 준비 실패: {err}",
                "total": total,
                "success": 0,
                "fail": total,
                "results": [],
                "remote_dir": self.remote_dir,
            }
            self.finished_report.emit(report)
            return

        # ✅ 동시 업로드
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as ex:
                future_map = {ex.submit(self._upload_one, p): p for p in files}

                for fut in concurrent.futures.as_completed(future_map):
                    res = fut.result()
                    results.append(res)

                    done += 1
                    if res.get("ok"):
                        ok += 1
                    else:
                        fail += 1

                    self.file_result.emit(res)
                    self.progress.emit(done, total, ok, fail)

                    if self._cancel_event.is_set():
                        break
        except Exception as e:
            report = {
                "ok": False,
                "message": f"업로드 도중 예외: {e}",
                "total": total,
                "success": ok,
                "fail": max(fail, total - ok),
                "results": results,
                "remote_dir": self.remote_dir,
            }
            self.finished_report.emit(report)
            return

        report = {
            "ok": (fail == 0),
            "message": "완료",
            "total": total,
            "success": ok,
            "fail": fail,
            "results": results,
            "remote_dir": self.remote_dir,
        }
        self.finished_report.emit(report)
