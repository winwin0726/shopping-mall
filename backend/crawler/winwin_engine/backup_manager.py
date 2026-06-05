# -*- coding: utf-8 -*-
"""backup_manager.py

winwin58.py(메인)에서 호출하는 BackupManager.

- band_profile_optimized(프로필) 백업/복원/정리 기능을 QThread로 실행
- QProgressDialog + QEventLoop로 UI는 멈추지 않으면서, 호출부에서는 True/False를 바로 받을 수 있게 설계

✅ 외부 파일은 '유지' (backup_thread.py / restore_thread.py / clean_thread.py 그대로 사용)

사용 예)
    mgr = BackupManager(self)
    mgr.start_backup(compress=True, analyze_first=True)
    mgr.start_restore()          # 최근 백업 복원
    mgr.start_clean('normal')    # light/normal/deep
"""

import os
import sys
import time
from typing import Optional

from PyQt5.QtCore import QEventLoop
from PyQt5.QtWidgets import QApplication, QProgressDialog, QMessageBox

from backup_thread import BackupThread
from restore_thread import RestoreThread
from clean_thread import CleanThread


class BackupManager:
    def __init__(self, parent=None, profile_dir: Optional[str] = None, backup_base_dir: Optional[str] = None):
        self.parent = parent

        # 실행 파일 기준 경로(현재 작업폴더 변화에 덜 민감)
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0])) if sys.argv and sys.argv[0] else os.getcwd()
        self.base_dir = base_dir

        self.profile_dir = profile_dir or os.path.join(self.base_dir, "band_profile_optimized")
        self.backup_base_dir = backup_base_dir or os.path.join(self.base_dir, "band_profile_backup")

        self._thread = None
        self._progress = None

    # -------------------------
    # 내부 유틸
    # -------------------------
    def _log(self, msg: str):
        """winwin58.py에 log()가 있으면 그쪽으로, 없으면 print."""
        try:
            if self.parent and hasattr(self.parent, "log") and callable(getattr(self.parent, "log")):
                self.parent.log(msg)
                return
        except Exception:
            pass
        print(msg)

    def _ensure_dir(self, path: str):
        os.makedirs(path, exist_ok=True)

    def _make_progress(self, title: str) -> QProgressDialog:
        p = QProgressDialog("준비 중...", "취소", 0, 100, self.parent)
        p.setWindowTitle(title)
        p.setWindowModality(True)
        p.setAutoClose(False)
        p.setAutoReset(False)
        p.setMinimumDuration(0)
        p.setValue(0)
        return p

    def _finish_popup(self, ok: bool, title: str, msg: str):
        """메시지박스는 실패해도(부모창 상태 등) 프로그램이 죽지 않게."""
        try:
            if not self.parent:
                return
            if ok:
                QMessageBox.information(self.parent, title, msg)
            else:
                QMessageBox.warning(self.parent, title, msg)
        except Exception:
            self._log(f"[{title}] {msg}")

    def _pick_latest_backup_dir(self) -> Optional[str]:
        """backup_base_dir 아래에서 가장 최근(수정시간 기준) 백업 폴더를 찾는다."""
        if not os.path.isdir(self.backup_base_dir):
            return None

        candidates = []
        for name in os.listdir(self.backup_base_dir):
            p = os.path.join(self.backup_base_dir, name)
            if not os.path.isdir(p):
                continue
            zip_path = os.path.join(p, "band_profile_backup.zip")
            dir_path = os.path.join(p, "band_profile_backup")
            if os.path.exists(zip_path) or os.path.isdir(dir_path):
                candidates.append(p)

        if not candidates:
            return None

        candidates.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        return candidates[0]

    def _run_blocking(self, thread, title: str, finished_adapter):
        """thread 실행 후 QEventLoop로 끝날 때까지 기다리고 결과 반환."""
        app = QApplication.instance()
        if app is None:
            raise RuntimeError("QApplication이 초기화되지 않았습니다. (PyQt 실행 구조 확인 필요)")

        loop = QEventLoop()
        result = {"ok": False, "msg": "", "extra": None}
        cancelled = {"v": False}

        self._progress = self._make_progress(title)

        def on_progress(v, text):
            try:
                self._progress.setValue(int(v))
                if text:
                    self._progress.setLabelText(str(text))
            except Exception:
                pass

        def on_log(text):
            self._log(str(text))

        def on_cancel():
            cancelled["v"] = True
            try:
                if hasattr(thread, "cancel"):
                    thread.cancel()
            except Exception:
                pass

        def on_finished(*args):
            ok, msg, extra = finished_adapter(*args)
            result["ok"] = bool(ok)
            result["msg"] = str(msg)
            result["extra"] = extra
            try:
                self._progress.setValue(100)
                self._progress.close()
            except Exception:
                pass
            loop.quit()

        # 시그널 연결
        if hasattr(thread, "progress_signal"):
            thread.progress_signal.connect(on_progress)
        if hasattr(thread, "log_signal"):
            thread.log_signal.connect(on_log)
        thread.finished_signal.connect(on_finished)

        self._progress.canceled.connect(on_cancel)

        # 실행
        self._thread = thread
        thread.start()
        self._progress.show()

        # 완료 대기(메인 이벤트는 계속 돌기 때문에 UI 멈춤 최소화)
        loop.exec_()

        if cancelled["v"] and result["ok"]:
            result["ok"] = False
            result["msg"] = "사용자가 작업을 취소했습니다."

        return result["ok"], result["msg"], result["extra"]

    # -------------------------
    # 공개 API (winwin58.py에서 호출)
    # -------------------------
    def start_backup(self, compress: bool = True, analyze_first: bool = True) -> bool:
        """band_profile_optimized를 백업."""
        try:
            if not os.path.isdir(self.profile_dir):
                self._finish_popup(False, "백업 실패", f"프로필 폴더가 없습니다:\n{self.profile_dir}")
                return False

            self._ensure_dir(self.backup_base_dir)

            # 타임스탬프 폴더
            stamp = time.strftime("backup_%y%m%d_%H%M%S")
            backup_dir = os.path.join(self.backup_base_dir, stamp)
            self._ensure_dir(backup_dir)

            # BackupThread가 zip을 backup_dir 내부에 생성하도록 "band_profile_backup" 하위 폴더를 target으로 지정
            backup_target = os.path.join(backup_dir, "band_profile_backup")
            self._ensure_dir(backup_target)

            th = BackupThread(
                source_dir=self.profile_dir,
                backup_dir=backup_target,
                analyze_first=analyze_first,
                compress=compress,
            )

            def finished_adapter(ok: bool, size_mb: float, msg: str):
                extra = {"size_mb": size_mb, "backup_dir": backup_dir}
                return ok, msg, extra

            ok, msg, _ = self._run_blocking(th, "밴드 프로필 백업", finished_adapter)
            self._finish_popup(ok, "백업 결과", msg)
            return ok

        except Exception as e:
            self._log(f"백업 매니저 오류: {e}")
            self._finish_popup(False, "백업 오류", str(e))
            return False

    def start_restore(self, backup_dir: Optional[str] = None) -> bool:
        """가장 최근 백업(또는 지정한 backup_dir)에서 band_profile_optimized를 복원."""
        try:
            self._ensure_dir(os.path.dirname(self.profile_dir))

            selected = backup_dir or self._pick_latest_backup_dir()
            if not selected:
                self._finish_popup(False, "복원 실패", f"백업 폴더가 없습니다:\n{self.backup_base_dir}")
                return False

            th = RestoreThread(backup_dir=selected, profile_dir=self.profile_dir)

            def finished_adapter(ok: bool, msg: str):
                return ok, msg, {"backup_dir": selected}

            ok, msg, _ = self._run_blocking(th, "밴드 프로필 복원", finished_adapter)
            self._finish_popup(ok, "복원 결과", msg)
            return ok

        except Exception as e:
            self._log(f"복원 매니저 오류: {e}")
            self._finish_popup(False, "복원 오류", str(e))
            return False

    def start_clean(self, clean_mode: str = "normal") -> bool:
        """band_profile_optimized 정리(light/normal/deep)."""
        try:
            if not os.path.isdir(self.profile_dir):
                self._finish_popup(False, "정리 실패", f"프로필 폴더가 없습니다:\n{self.profile_dir}")
                return False

            clean_mode = (clean_mode or "normal").strip().lower()
            if clean_mode not in ("light", "normal", "deep"):
                clean_mode = "normal"

            th = CleanThread(profile_dir=self.profile_dir, clean_mode=clean_mode)

            def finished_adapter(ok: bool, cleaned_mb: float, msg: str):
                return ok, msg, {"cleaned_mb": cleaned_mb, "mode": clean_mode}

            ok, msg, _ = self._run_blocking(th, "밴드 프로필 정리", finished_adapter)
            self._finish_popup(ok, "정리 결과", msg)
            return ok

        except Exception as e:
            self._log(f"정리 매니저 오류: {e}")
            self._finish_popup(False, "정리 오류", str(e))
            return False
