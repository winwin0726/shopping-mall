import os
import sys
import datetime
import threading

# --- APScheduler 자동 설치 가드 ---
try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ImportError:
    import subprocess
    print("⏰ [스케줄러] APScheduler 라이브러리가 존재하지 않아 pip 자동 설치를 시도합니다...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "apscheduler"])
        from apscheduler.schedulers.background import BackgroundScheduler
        print("⏰ [스케줄러] APScheduler 설치 및 로드 성공!")
    except Exception as e:
        print(f"❌ [스케줄러] APScheduler 자동 설치 실패: {e}")
        raise

# 백그라운드 스케줄러 글로벌 인스턴스
_scheduler = None
_scheduler_lock = threading.Lock()

def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    with _scheduler_lock:
        if _scheduler is None:
            _scheduler = BackgroundScheduler(timezone="Asia/Seoul")
            _scheduler.start()
            print("💓 [스케줄러] APScheduler 백그라운드 엔진 기동 완료!")
        return _scheduler

def run_scheduled_job(task_id: int):
    """지정 스케줄러 태스크가 발동했을 때 백그라운드 크롤링 및 업로드 체이닝"""
    from backend.database import get_db, get_system_settings
    from backend.crawler_engine import get_engine
    
    db = get_db()
    task = db.get_scheduler_task(task_id)
    if not task or not task.get("is_active"):
        return
        
    engine = get_engine()
    
    # 중복 실행 방지
    if engine.crawling_thread and engine.crawling_thread.is_alive():
        engine.add_log(f"⏰ [스케줄러] '{task['name']}' 스케줄 시간이나, 현재 다른 크롤링이 진행 중이므로 작업을 스킵합니다.", "WARNING", False)
        return
        
    engine.add_log(f"⏰ [스케줄러] '{task['name']}' 스케줄 작업 실행 시작 (수집 갯수: {task.get('crawling_count')}개)", "INFO", False)

    # 1. 크롤링 파라미터 빌드
    system_ai_settings = get_system_settings()
    
    # 가상의 StartCrawlRequest 모방을 위한 데이터 구성
    from backend.api_server import _get_gemini_key, _get_telegram_credentials, _apply_ai_budget_policy, _apply_crawl_operation_policy
    from backend.constants.prompts import DEFAULT_COMMON_PROMPT
    
    class TempTransOptions:
        def __init__(self):
            self.enable = True
            self.api_key = _get_gemini_key()
            self.category = "남성의류"
            self.prefix = "AUTO"
            self.naver_fx = float(system_ai_settings.get("naver_fx", "227.8") if "naver_fx" in system_ai_settings else 227.8)
            self.rules_text = DEFAULT_COMMON_PROMPT
            
        def dict(self):
            return self.__dict__
            
    class TempRequest:
        def __init__(self):
            self.platform = task.get("source_platform") or "웨이상(Szwego)"
            self.count = task.get("crawling_count") or 10
            self.startDate = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
            self.endDate = datetime.datetime.now().strftime("%Y-%m-%d")
            self.crawlAllDates = True
            self.append = False
            self.headless = True  # 무인 스케줄러이므로 창 숨김
            self.ghost_mode = False
            self.skip_vision = False
            self.use_critic = False
            self.require_price = True
            self.disable_grouping = False
            self.grouping_mode = "merge_color_options"
            self.vendorUrl = ""
            self.transOptions = TempTransOptions()
            self.telegramToken = ""
            self.telegramChatId = ""
            
    req = TempRequest()
    resolved_telegram_token, resolved_telegram_chat_id = _get_telegram_credentials()
    req.telegramToken = resolved_telegram_token
    req.telegramChatId = resolved_telegram_chat_id
    
    # 웨이상 즐겨찾기 또는 등록된 벤더 목록 URL 가져오기
    try:
        vendors_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "weishang_vendors.json")
        if os.path.exists(vendors_path):
            import json
            with open(vendors_path, "r", encoding="utf-8") as f:
                v_list = json.load(f)
                
            # 즐겨찾기에 등록된 URL이 있다면 우선 사용, 없으면 전체 업체 사용
            fav_ids = []
            # 프로필 리스트 등에서 즐겨찾기 바인딩도 가능하나, 범용적으로 전체 벤더 중 URL 유효한 것 병합
            urls = [v["url"] for v in v_list if v.get("url")]
            if urls:
                req.vendorUrl = "\n".join(urls[:5]) # 스케줄 부하 분산을 위해 우선 최대 상위 5개 업체만 자동 수집
            else:
                req.vendorUrl = "https://www.szwego.com/static/index.html?t=1712852296766#/followed"
    except Exception as e:
        engine.add_log(f"⏰ [스케줄러] 업체 URL 조회 실패: {e}", "ERROR", False)
        
    ai_policy = _apply_ai_budget_policy(system_ai_settings, req)
    crawl_policy = _apply_crawl_operation_policy(system_ai_settings)
    
    settings = {
        "platform": req.platform,
        "count": req.count,
        "startDate": req.startDate,
        "endDate": req.endDate,
        "crawlAllDates": req.crawlAllDates,
        "append": req.append,
        "headless": req.headless,
        "ghost_mode": req.ghost_mode,
        "skip_vision": req.skip_vision,
        "use_critic": req.use_critic,
        "require_price": req.require_price,
        "use_dynamic_ai_rules": bool(system_ai_settings.get("use_dynamic_ai_rules", False)),
        "ai_budget_mode": ai_policy["ai_budget_mode"],
        "ai_translate_during_crawl": ai_policy["ai_translate_during_crawl"],
        "ai_use_vision_during_crawl": ai_policy["ai_use_vision_during_crawl"],
        "ai_use_critic_review": ai_policy["ai_use_critic_review"],
        "ai_use_image_ordering": ai_policy["ai_use_image_ordering"],
        "ai_analysis_product_limit": ai_policy["ai_analysis_product_limit"],
        "ai_analysis_telemetry_limit": ai_policy["ai_analysis_telemetry_limit"],
        "crawl_operation_mode": crawl_policy["crawl_operation_mode"],
        "prefer_api_image_urls": crawl_policy["prefer_api_image_urls"],
        "save_crawl_snapshots": crawl_policy["save_crawl_snapshots"],
        "max_item_retries": crawl_policy["max_item_retries"],
        "download_fail_skip_threshold": crawl_policy["download_fail_skip_threshold"],
        "registration_guard_level": crawl_policy["registration_guard_level"],
        "block_resources": crawl_policy.get("block_resources", True),
        "disable_grouping": req.disable_grouping,
        "grouping_mode": req.grouping_mode,
        "vendorUrl": req.vendorUrl,
        "transOptions": req.transOptions.dict(),
        "telegramToken": resolved_telegram_token,
        "telegramChatId": resolved_telegram_chat_id
    }
    
    def async_crawl_and_post():
        try:
            # 1. 크롤링 동기 실행 (서브스레드 안에서 실행됨)
            engine.run_crawling(settings)
            
            # 2. 크롤링 종료 후 올리기 체이닝 실행
            target_platforms = task.get("target_platforms") or []
            if target_platforms and len(engine.crawled_products) > 0:
                engine.add_log(f"⏰ [스케줄러] 수집 완료({len(engine.crawled_products)}건). 자동으로 {target_platforms} 올리기를 대기열에 추가합니다.", "SUCCESS", False)
                
                indices = list(range(len(engine.crawled_products)))
                
                from backend.queue_manager import get_queue_manager
                qm = get_queue_manager()
                qm.add_job("POST", {
                    "platforms": target_platforms,
                    "category": "자동분류",
                    "delayMin": task.get("delay_min") if task.get("delay_min") is not None else 15,
                    "delayMax": task.get("delay_max") if task.get("delay_max") is not None else 45,
                    "dry_run": False,
                    "skip_duplicate_posts": True,
                    "selected_indices": indices
                })
        except Exception as err:
            engine.add_log(f"❌ [스케줄러] 백그라운드 크롤링/올리기 오류: {err}", "ERROR", False)
            
    threading.Thread(target=async_crawl_and_post, daemon=True).start()
    
    # 3. 데이터베이스 상태 시각 갱신
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    next_dt = None
    if task.get("interval_type") == "interval":
        next_dt = datetime.datetime.now() + datetime.timedelta(hours=int(task.get("interval_value") or 4))
    else:
        # daily 스케줄
        try:
            h, m = map(int, task.get("interval_value").split(":"))
            today = datetime.datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)
            if today < datetime.datetime.now():
                next_dt = today + datetime.timedelta(days=1)
            else:
                next_dt = today
        except:
            next_dt = datetime.datetime.now() + datetime.timedelta(days=1)
            
    next_str = next_dt.strftime("%Y-%m-%d %H:%M:%S") if next_dt else "-"
    db.update_scheduler_task_run_time(task_id, now_str, next_str)

def sync_active_scheduler_tasks():
    """DB에 등록되어 있는 활성 스케줄링 태스크들을 APScheduler 엔진에 동기화 등록"""
    sched = get_scheduler()
    
    # 기존 scheduler_job 들 초기화
    for job in sched.get_jobs():
        if job.id.startswith("task_"):
            sched.remove_job(job.id)
            
    from backend.database import get_db
    db = get_db()
    tasks = db.get_all_scheduler_tasks()
    
    for t in tasks:
        if not t.get("is_active"):
            continue
            
        job_id = f"task_{t['id']}"
        interval_value = t.get("interval_value")
        
        try:
            if t.get("interval_type") == "interval":
                # 시간 간격 주기 예약 (hours)
                hours = int(interval_value or 4)
                sched.add_job(
                    run_scheduled_job,
                    trigger="interval",
                    hours=hours,
                    id=job_id,
                    args=[t["id"]],
                    coalesce=True,
                    max_instances=1
                )
            elif t.get("interval_type") == "daily":
                # 매일 특정 시각 예약 ("09:00" 등)
                h, m = map(int, interval_value.split(":"))
                sched.add_job(
                    run_scheduled_job,
                    trigger="cron",
                    hour=h,
                    minute=m,
                    id=job_id,
                    args=[t["id"]],
                    coalesce=True,
                    max_instances=1
                )
        except Exception as e:
            print(f"❌ [스케줄러] 태스크 {t['id']} 등록 에러: {e}")
