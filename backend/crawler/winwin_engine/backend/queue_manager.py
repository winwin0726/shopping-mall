import threading
import time
import json
import traceback
from backend.database import get_db

class QueueManager:
    """
    DB 기반의 작업 큐를 관리하고 워커 스레드를 통해 작업을 순차 처리하는 매니저 클래스.
    """
    def __init__(self):
        self.db = get_db()
        self.handlers = {}
        self.is_running = False
        self.worker_thread = None

    def register_handler(self, task_type: str, func):
        """특정 작업 타입(task_type)에 실행될 콜백 함수를 등록합니다."""
        self.handlers[task_type] = func

    def rollback_running_jobs(self):
        """서버 재시작 등 비정상 종료로 인해 RUNNING 상태로 남은 작업을 복구합니다."""
        with self.db.lock:
            conn = self.db.connect()
            c = conn.cursor()
            c.execute('''
                UPDATE job_queue 
                SET status=CASE WHEN retry_count < 3 THEN 'PENDING' ELSE 'FAILED' END,
                    retry_count=CASE WHEN retry_count < 3 THEN retry_count + 1 ELSE retry_count END,
                    error_msg='System restarted while running',
                    updated_at=CURRENT_TIMESTAMP
                WHERE status='RUNNING'
            ''')
            conn.commit()
            conn.close()

    def add_job(self, task_type: str, payload_dict: dict):
        """새로운 작업을 DB 큐에 대기(PENDING) 상태로 추가합니다."""
        with self.db.lock:
            conn = self.db.connect()
            c = conn.cursor()
            c.execute('''
                INSERT INTO job_queue (task_type, payload_json)
                VALUES (?, ?)
            ''', (task_type, json.dumps(payload_dict, ensure_ascii=False)))
            conn.commit()
            conn.close()

    def has_active_job(self, task_type: str):
        """특정 작업이 이미 대기/실행 중인지 확인합니다."""
        with self.db.lock:
            conn = self.db.connect()
            c = conn.cursor()
            c.execute('''
                SELECT COUNT(*)
                FROM job_queue
                WHERE task_type=? AND status IN ('PENDING', 'RUNNING')
            ''', (task_type,))
            count = c.fetchone()[0]
            conn.close()
            return count > 0

    def add_unique_job(self, task_type: str, payload_dict: dict):
        """같은 작업 타입이 이미 대기/실행 중이면 새 작업을 추가하지 않습니다."""
        with self.db.lock:
            conn = self.db.connect()
            c = conn.cursor()
            c.execute('''
                SELECT COUNT(*)
                FROM job_queue
                WHERE task_type=? AND status IN ('PENDING', 'RUNNING')
            ''', (task_type,))
            active_count = c.fetchone()[0]
            if active_count:
                conn.close()
                return False
            c.execute('''
                INSERT INTO job_queue (task_type, payload_json)
                VALUES (?, ?)
            ''', (task_type, json.dumps(payload_dict, ensure_ascii=False)))
            conn.commit()
            conn.close()
            return True

    def get_queue_status(self):
        """현재 큐의 대기/진행/완료/실패 현황을 반환합니다."""
        with self.db.lock:
            conn = self.db.connect()
            c = conn.cursor()
            c.execute('SELECT status, COUNT(*) FROM job_queue GROUP BY status')
            rows = c.fetchall()
            conn.close()
            status_dict = {row[0]: row[1] for row in rows}
            return {
                "pending": status_dict.get("PENDING", 0),
                "running": status_dict.get("RUNNING", 0),
                "completed": status_dict.get("COMPLETED", 0),
                "failed": status_dict.get("FAILED", 0)
            }

    def start_worker(self):
        """백그라운드 큐 처리 워커를 시작합니다."""
        if self.is_running: return
        self.is_running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="WinWinQueueWorker")
        self.worker_thread.start()

    def stop_worker(self):
        """백그라운드 워커를 종료합니다."""
        self.is_running = False

    def _worker_loop(self):
        while self.is_running:
            job = self._fetch_next_job()
            if job:
                job_id, task_type, payload_json, retry_count = job
                self._process_job(job_id, task_type, payload_json, retry_count)
            else:
                time.sleep(2) # 작업이 없으면 2초 대기

    def _fetch_next_job(self):
        with self.db.lock:
            conn = self.db.connect()
            c = conn.cursor()
            c.execute('''
                SELECT id, task_type, payload_json, retry_count
                FROM job_queue 
                WHERE status = 'PENDING'
                ORDER BY created_at ASC LIMIT 1
            ''')
            row = c.fetchone()
            if row:
                job_id, task_type = row[0], row[1]
                c.execute("UPDATE job_queue SET status='RUNNING', updated_at=CURRENT_TIMESTAMP WHERE id=?", (job_id,))
                if task_type == "POST":
                    c.execute('''
                        UPDATE job_queue
                        SET status='FAILED',
                            error_msg='Duplicate POST job auto-cancelled',
                            updated_at=CURRENT_TIMESTAMP
                        WHERE task_type='POST' AND status='PENDING' AND id<>?
                    ''', (job_id,))
                conn.commit()
            conn.close()
            return row

    def _process_job(self, job_id, task_type, payload_json, retry_count):
        try:
            payload = json.loads(payload_json)
            handler = self.handlers.get(task_type)
            if handler:
                handler(payload)
                self._update_job_status(job_id, 'COMPLETED', '')
            else:
                error_msg = f"[Queue] No handler registered for task type: {task_type}"
                print(error_msg)
                self._update_job_status(job_id, 'FAILED', error_msg)
        except Exception as e:
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            print(f"[Queue Error] Job {job_id} failed: {e}")
            if retry_count < 3:
                # 3번까지는 실패 시 재시도 대기열로 복귀
                self._update_job_status(job_id, 'PENDING', error_msg, retry_count + 1)
            else:
                self._update_job_status(job_id, 'FAILED', error_msg, retry_count)

    def _update_job_status(self, job_id, status, error_msg, retry_count=None):
        with self.db.lock:
            conn = self.db.connect()
            c = conn.cursor()
            if retry_count is not None:
                c.execute('''
                    UPDATE job_queue 
                    SET status=?, error_msg=?, retry_count=?, updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                ''', (status, error_msg, retry_count, job_id))
            else:
                c.execute('''
                    UPDATE job_queue 
                    SET status=?, error_msg=?, updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                ''', (status, error_msg, job_id))
            conn.commit()
            conn.close()

# Singleton instance
queue_manager_instance = None
def get_queue_manager():
    global queue_manager_instance
    if queue_manager_instance is None:
        queue_manager_instance = QueueManager()
    return queue_manager_instance
