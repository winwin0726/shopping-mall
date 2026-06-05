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

class MobileSyncThread(QThread):
    command_received = pyqtSignal(str)
    
    def __init__(self, username, crawler_ui_ref):
        super().__init__()
        self.username = username
        self.crawler_ui = crawler_ui_ref
        self.running = True
        self.notifications_queue = []  # 알림 큐 (모바일에 전송할 이벤트)
        import socket
        try:
            self.hwid = socket.gethostname()
        except:
            self.hwid = "UNKNOWN-PC"
    
    def add_notification(self, msg, ntype="info"):
        """알림 큐에 메시지 추가 (다음 sync 시 모바일로 전송)"""
        import datetime as _dt
        self.notifications_queue.append({
            "msg": msg, "type": ntype,
            "time": _dt.datetime.now().strftime("%H:%M:%S")
        })
        # 최대 20개 유지
        if len(self.notifications_queue) > 20:
            self.notifications_queue = self.notifications_queue[-20:]
    
    def _collect_tabs_status(self):
        """PC 크롤러 UI에서 각 탭별 상태를 수집하여 딕셔너리로 반환"""
        tabs = {}
        ui = self.crawler_ui
        if not ui:
            return tabs
        
        # 카카오 크롤링 상태
        kakao_crawl = {"status": "idle", "log": "대기 중", "count": 0}
        if hasattr(ui, 'crawling_thread') and ui.crawling_thread is not None:
            thread = ui.crawling_thread
            if hasattr(thread, 'isRunning') and thread.isRunning():
                cls_name = thread.__class__.__name__
                if 'Kakao' in cls_name or 'kakao' in cls_name:
                    kakao_crawl["status"] = "running"
                    kakao_crawl["log"] = "크롤링 진행 중..."
        if hasattr(ui, 'crawled_products'):
            kakao_crawl["count"] = len(ui.crawled_products)
        tabs["kakao_crawl"] = kakao_crawl
        
        # 밴드 크롤링 상태
        band_crawl = {"status": "idle", "log": "대기 중", "count": 0}
        if hasattr(ui, 'crawling_thread') and ui.crawling_thread is not None:
            thread = ui.crawling_thread
            if hasattr(thread, 'isRunning') and thread.isRunning():
                cls_name = thread.__class__.__name__
                if 'Band' in cls_name or 'band' in cls_name:
                    band_crawl["status"] = "running"
                    band_crawl["log"] = "밴드 크롤링 진행 중..."
        tabs["band_crawl"] = band_crawl
        
        # 웨이상 크롤링 상태
        weishang_crawl = {"status": "idle", "log": "대기 중", "count": 0}
        if hasattr(ui, 'weishang_thread') and ui.weishang_thread is not None:
            if hasattr(ui.weishang_thread, 'isRunning') and ui.weishang_thread.isRunning():
                weishang_crawl["status"] = "running"
                weishang_crawl["log"] = "웨이상 크롤링 진행 중..."
        tabs["weishang_crawl"] = weishang_crawl
        
        # 카카오 포스팅 상태
        kakao_post = {"status": "idle", "log": "대기 중", "count": 0}
        if hasattr(ui, 'is_posting_active') and ui.is_posting_active:
            if hasattr(ui, 'current_posting_platform') and 'kakao' in str(getattr(ui, 'current_posting_platform', '')).lower():
                kakao_post["status"] = "running"
                kakao_post["log"] = "카카오 포스팅 진행 중..."
            elif hasattr(ui, 'kakao_posting_active') and ui.kakao_posting_active:
                kakao_post["status"] = "running"
                kakao_post["log"] = "카카오 포스팅 진행 중..."
        if hasattr(ui, 'posted_count_kakao'):
            kakao_post["count"] = ui.posted_count_kakao
        tabs["kakao_post"] = kakao_post
        
        # 밴드 포스팅 상태
        band_post = {"status": "idle", "log": "대기 중", "count": 0}
        if hasattr(ui, 'is_posting_active') and ui.is_posting_active:
            if hasattr(ui, 'current_posting_platform') and 'band' in str(getattr(ui, 'current_posting_platform', '')).lower():
                band_post["status"] = "running"
                band_post["log"] = "밴드 포스팅 진행 중..."
            elif hasattr(ui, 'band_posting_active') and ui.band_posting_active:
                band_post["status"] = "running"
                band_post["log"] = "밴드 포스팅 진행 중..."
        if hasattr(ui, 'posted_count_band'):
            band_post["count"] = ui.posted_count_band
        tabs["band_post"] = band_post
        
        return tabs
    
    def _collect_results_preview(self):
        """최근 크롤링 결과 메타데이터를 수집 (이미지 파일 전송 X, 텍스트 정보만)"""
        results = []
        ui = self.crawler_ui
        if not ui or not hasattr(ui, 'crawled_products'):
            return results
        
        # 최근 10개만 역순으로
        products = ui.crawled_products[-10:]
        for p in reversed(products):
            results.append({
                "title": str(p.get("title", ""))[:60],
                "price": str(p.get("sale_price", "")),
                "images": len(p.get("image_files", [])),
                "time": str(p.get("created_at", ""))[:16],
                "thumb": ""  # PythonAnywhere 무료 계정 용량 제한으로 이미지 URL 생략
            })
        
        return results
            
    def run(self):
        import requests, time, json
        while self.running:
            try:
                # 상태 확인 로직
                status = "대기 중 / 오프라인"
                log_msg = "초기화 됨"
                
                if self.crawler_ui:
                    if hasattr(self.crawler_ui, 'is_crawling_active') and self.crawler_ui.is_crawling_active:
                        status = "수집 모듈 가동 중 🚀"
                    elif hasattr(self.crawler_ui, 'is_posting_active') and self.crawler_ui.is_posting_active:
                        status = "포스팅 모듈 가동 중 📤"
                    else:
                        status = "대기 중 (Idle) 💤"
                        
                    if hasattr(self.crawler_ui, 'latest_log_msg'):
                        log_msg = self.crawler_ui.latest_log_msg
                
                # v2 확장 데이터 수집
                tabs_status = self._collect_tabs_status()
                results_preview = self._collect_results_preview()
                
                data = {
                    "username": self.username,
                    "hwid": self.hwid,
                    "status": status,
                    "log_msg": log_msg,
                    "tabs_status": json.dumps(tabs_status, ensure_ascii=False),
                    "results_preview": json.dumps(results_preview, ensure_ascii=False),
                    "notifications": json.dumps(self.notifications_queue, ensure_ascii=False)
                }
                res = requests.post("https://hagisq.pythonanywhere.com/api/v1/sync", json=data, timeout=5)
                if res.status_code == 200:
                    cmd = res.json().get("command")
                    if cmd:
                        self.command_received.emit(cmd)
            except Exception as e:
                pass
            time.sleep(3)
