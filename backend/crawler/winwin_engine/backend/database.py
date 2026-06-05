import sqlite3
import json
import os
import threading
import hashlib
import datetime

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_FILE = os.path.join(_PROJECT_ROOT, 'system_settings.json')

def get_system_settings():
    default_settings = {
        "forbidden_words": [],
        "min_image_width": 200,
        "min_image_height": 200,
        "use_dynamic_ai_rules": False,
        "ai_budget_mode": "economy",
        "ai_translate_during_crawl": False,
        "ai_use_vision_during_crawl": False,
        "ai_use_critic_review": False,
        "ai_use_image_ordering": False,
        "ai_analysis_product_limit": 30,
        "ai_analysis_telemetry_limit": 120,
        "crawl_operation_mode": "balanced",
        "prefer_api_image_urls": True,
        "save_crawl_snapshots": True,
        "max_item_retries": 2,
        "download_fail_skip_threshold": 3,
        "registration_guard_level": "normal",
        "auto_load_last_products_on_start": True,
        "block_resources": True,
        "translation_engine": "gemini",
        "deepl_api_key": "",
        "font_size_step": 3,
        "enable_auto_recovery": True,
        "auto_recovery_retry_limit": 3,
        "sqlite_timeout_seconds": 30.0,
        "session_heartbeat_check": True
    }
    if not os.path.exists(SETTINGS_FILE):
        return default_settings
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return default_settings
            merged = dict(default_settings)
            merged.update(data)
            return merged
    except Exception:
        return default_settings

def save_system_settings(settings):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

DB_PATH = os.path.join(_PROJECT_ROOT, "TEMP_CRAWLED", "winwin.db")

class CrawlDB:
    """
    Thread-safe SQLite Database manager for crawled products.
    """
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.lock = threading.RLock()
        self._init_db()

    def connect(self):
        settings = get_system_settings()
        timeout = settings.get("sqlite_timeout_seconds", 30.0)
        conn = sqlite3.connect(self.db_path, timeout=timeout)
        conn.execute(f"PRAGMA busy_timeout={int(timeout * 1000)}")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self.lock:
            conn = self.connect()
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS crawled_products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT,
                    title TEXT,
                    product_code TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data_json TEXT
                )
            ''')
            # Phase 5: LLM Translation Caching
            c.execute('''
                CREATE TABLE IF NOT EXISTS translation_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_hash TEXT UNIQUE,
                    source_text TEXT,
                    translated_text TEXT,
                    category TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Phase 6: Operational Quality Improvements (Post History & Job Queue)
            c.execute('''
                CREATE TABLE IF NOT EXISTS crawled_products_backup (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT,
                    title TEXT,
                    product_code TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data_json TEXT
                )
            ''')
            # Phase 6: Operational Quality Improvements (Post History & Job Queue)
            c.execute('''
                CREATE TABLE IF NOT EXISTS post_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_code TEXT,
                    content_signature TEXT,
                    platform TEXT,
                    account_profile TEXT,
                    status TEXT,
                    error_reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS vendor_crawl_history (
                    vendor_id TEXT PRIMARY KEY,
                    vendor_name TEXT,
                    last_crawled_date TEXT,
                    crawled_count INTEGER,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS job_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_type TEXT,
                    payload_json TEXT,
                    status TEXT DEFAULT 'PENDING',
                    retry_count INTEGER DEFAULT 0,
                    error_msg TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS crawl_telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT,
                    event_type TEXT,
                    vendor_id TEXT,
                    vendor_name TEXT,
                    reason TEXT,
                    raw_text TEXT,
                    metadata_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 리워드 포인트 시스템 테이블 생성
            c.execute('''
                CREATE TABLE IF NOT EXISTS user_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    points INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS point_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    points_changed INTEGER,
                    reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # 지능형 자동화 스케줄러 테이블 생성
            c.execute('''
                CREATE TABLE IF NOT EXISTS scheduler_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    interval_type TEXT, -- 'daily', 'interval'
                    interval_value TEXT, -- 예: '09:00', '4' (시간단위)
                    source_platform TEXT, -- '웨이상(Szwego)'
                    target_platforms TEXT, -- JSON 배열
                    crawling_count INTEGER DEFAULT 10,
                    delay_min INTEGER DEFAULT 15,
                    delay_max INTEGER DEFAULT 45,
                    is_active INTEGER DEFAULT 1,
                    last_run_at TEXT,
                    next_run_at TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # 최초 1회 기본 포인트 설정
            c.execute("SELECT COUNT(*) FROM user_points")
            if c.fetchone()[0] == 0:
                c.execute("INSERT INTO user_points (points) VALUES (0)")
 
            c.execute("PRAGMA table_info(scheduler_tasks)")
            sched_cols = {row[1] for row in c.fetchall()}
            if "delay_min" not in sched_cols:
                c.execute("ALTER TABLE scheduler_tasks ADD COLUMN delay_min INTEGER DEFAULT 15")
            if "delay_max" not in sched_cols:
                c.execute("ALTER TABLE scheduler_tasks ADD COLUMN delay_max INTEGER DEFAULT 45")

            c.execute("PRAGMA table_info(crawled_products_backup)")

            c.execute("PRAGMA table_info(crawled_products_backup)")
            backup_cols = {row[1] for row in c.fetchall()}
            if "backup_group_id" not in backup_cols:
                c.execute("ALTER TABLE crawled_products_backup ADD COLUMN backup_group_id TEXT")
            if "backup_name" not in backup_cols:
                c.execute("ALTER TABLE crawled_products_backup ADD COLUMN backup_name TEXT")

            c.execute("PRAGMA table_info(post_history)")

            post_history_cols = {row[1] for row in c.fetchall()}
            if "content_signature" not in post_history_cols:
                c.execute("ALTER TABLE post_history ADD COLUMN content_signature TEXT")
            c.execute('CREATE INDEX IF NOT EXISTS idx_post_history_check ON post_history(product_code, platform, status)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_post_history_content_check ON post_history(content_signature, platform, status)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_job_queue_status ON job_queue(status, created_at)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_crawl_telemetry_platform ON crawl_telemetry(platform, created_at)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_crawl_telemetry_vendor ON crawl_telemetry(vendor_id, event_type, created_at)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_crawled_products_code ON crawled_products(product_code)')
            conn.commit()
            conn.close()

    def truncate_all(self):
        with self.lock:
            conn = self.connect()
            try:
                c = conn.cursor()
                c.execute('DELETE FROM crawled_products')
                conn.commit()
            finally:
                conn.close()

    def add_product(self, product_dict: dict) -> int:
        platform = product_dict.get("platform", "Unknown")
        title = product_dict.get("title", "")
        product_code = product_dict.get("product_code", "")
        data_json = json.dumps(product_dict, ensure_ascii=False)

        with self.lock:
            conn = self.connect()
            try:
                c = conn.cursor()
                c.execute('''
                    INSERT INTO crawled_products (platform, title, product_code, data_json)
                    VALUES (?, ?, ?, ?)
                ''', (platform, title, product_code, data_json))
                row_id = c.lastrowid
                conn.commit()
                return row_id
            finally:
                conn.close()

    def add_products_bulk(self, products: list):
        with self.lock:
            conn = self.connect()
            try:
                c = conn.cursor()
                for prod in products:
                    platform = prod.get("platform", "Unknown")
                    title = prod.get("title", "")
                    product_code = prod.get("product_code", "")
                    data_json = json.dumps(prod, ensure_ascii=False)
                    c.execute('''
                        INSERT INTO crawled_products (platform, title, product_code, data_json)
                        VALUES (?, ?, ?, ?)
                    ''', (platform, title, product_code, data_json))
                    prod["db_id"] = c.lastrowid
                conn.commit()
            finally:
                conn.close()

    def get_all_products(self):
        """Returns a list of dicts (the original JSON payloads)"""
        with self.lock:
            conn = self.connect()
            try:
                c = conn.cursor()
                c.execute('SELECT id, data_json FROM crawled_products ORDER BY id ASC')
                rows = c.fetchall()
            finally:
                conn.close()

            results = []
            for row in rows:
                try:
                    item = json.loads(row[1])
                    item["db_id"] = row[0]
                    results.append(item)
                except:
                    pass
            return results

    def count_all_products(self):
        """Returns the total number of crawled products."""
        with self.lock:
            conn = self.connect()
            try:
                c = conn.cursor()
                c.execute('SELECT COUNT(*) FROM crawled_products')
                count = c.fetchone()[0]
                return count
            finally:
                conn.close()

    def get_products_batch(self, offset, limit):
        """Returns a batch of products starting at offset with the given limit."""
        with self.lock:
            conn = self.connect()
            try:
                c = conn.cursor()
                c.execute('SELECT id, data_json FROM crawled_products ORDER BY id ASC LIMIT ? OFFSET ?', (limit, offset))
                rows = c.fetchall()
            finally:
                conn.close()

            results = []
            for row in rows:
                try:
                    item = json.loads(row[1])
                    item["db_id"] = row[0]
                    results.append(item)
                except:
                    pass
            return results

    def overwrite_all_products(self, products: list):
        """Replaces entire table with new product list"""
        with self.lock:
            conn = self.connect()
            try:
                c = conn.cursor()
                c.execute('DELETE FROM crawled_products')
                for prod in products:
                    platform = prod.get("platform", "Unknown")
                    title = prod.get("title", "")
                    product_code = prod.get("product_code", "")
                    data_json = json.dumps(prod, ensure_ascii=False)
                    c.execute('''
                        INSERT INTO crawled_products (platform, title, product_code, data_json)
                        VALUES (?, ?, ?, ?)
                    ''', (platform, title, product_code, data_json))
                    prod["db_id"] = c.lastrowid
                conn.commit()
            finally:
                conn.close()

    def update_product_by_index(self, index: int, product_dict: dict):
        """Updates a product at the given logical index (0-based, ordered by id ASC)."""
        db_id = product_dict.get("db_id")
        if db_id is not None:
            self.update_product_by_id(db_id, product_dict)
            return

        with self.lock:
            conn = self.connect()
            try:
                c = conn.cursor()
                c.execute('SELECT id FROM crawled_products ORDER BY id ASC LIMIT 1 OFFSET ?', (index,))
                row = c.fetchone()
                if row:
                    row_id = row[0]
                    platform = product_dict.get("platform", "Unknown")
                    title = product_dict.get("title", "")
                    product_code = product_dict.get("product_code", "")
                    data_json = json.dumps(product_dict, ensure_ascii=False)
                    c.execute('''
                        UPDATE crawled_products
                        SET platform=?, title=?, product_code=?, data_json=?
                        WHERE id=?
                    ''', (platform, title, product_code, data_json, row_id))

                    # [안전망] 사용자가 번역/수정한 내용을 백업 테이블에도 실시간 동기화하여 백업 복구 시 날아가지 않도록 방지
                    if product_code:
                        c.execute('''
                            UPDATE crawled_products_backup
                            SET title=?, data_json=?
                            WHERE product_code=?
                        ''', (title, data_json, product_code))

                    conn.commit()
            finally:
                conn.close()

    def update_product_by_id(self, db_id: int, product_dict: dict):
        """Updates a product using its physical database id."""
        with self.lock:
            conn = self.connect()
            try:
                c = conn.cursor()
                platform = product_dict.get("platform", "Unknown")
                title = product_dict.get("title", "")
                product_code = product_dict.get("product_code", "")
                data_json = json.dumps(product_dict, ensure_ascii=False)
                c.execute('''
                    UPDATE crawled_products
                    SET platform=?, title=?, product_code=?, data_json=?
                    WHERE id=?
                ''', (platform, title, product_code, data_json, db_id))

                # [안전망] 사용자가 번역/수정한 내용을 백업 테이블에도 실시간 동기화하여 백업 복구 시 날아가지 않도록 방지
                if product_code:
                    c.execute('''
                        UPDATE crawled_products_backup
                        SET title=?, data_json=?
                        WHERE product_code=?
                    ''', (title, data_json, product_code))

                conn.commit()
            finally:
                conn.close()

    def delete_product_by_index(self, index: int):
        """Deletes a product at the given logical index."""
        with self.lock:
            conn = self.connect()
            try:
                c = conn.cursor()
                c.execute('SELECT id FROM crawled_products ORDER BY id ASC LIMIT 1 OFFSET ?', (index,))
                row = c.fetchone()
                if row:
                    row_id = row[0]
                    c.execute('DELETE FROM crawled_products WHERE id=?', (row_id,))
                    conn.commit()
            finally:
                conn.close()

    def delete_product_by_id(self, db_id: int):
        """Deletes a product using its physical database id."""
        with self.lock:
            conn = self.connect()
            try:
                c = conn.cursor()
                c.execute('DELETE FROM crawled_products WHERE id=?', (db_id,))
                conn.commit()
            finally:
                conn.close()

    def delete_products_bulk_by_indices(self, indices: list):
        """Deletes multiple products by their logical indices."""
        with self.lock:
            conn = self.connect()
            try:
                c = conn.cursor()
                for index in sorted(indices, reverse=True):
                    c.execute('SELECT id FROM crawled_products ORDER BY id ASC LIMIT 1 OFFSET ?', (index,))
                    row = c.fetchone()
                    if row:
                        row_id = row[0]
                        c.execute('DELETE FROM crawled_products WHERE id=?', (row_id,))
                conn.commit()
            finally:
                conn.close()

    def delete_products_bulk_by_ids(self, db_ids: list):
        """Deletes multiple products using their physical database ids."""
        if not db_ids:
            return
        with self.lock:
            conn = self.connect()
            try:
                c = conn.cursor()
                limit = 999
                for i in range(0, len(db_ids), limit):
                    chunk = db_ids[i:i+limit]
                    placeholders = ",".join("?" for _ in chunk)
                    c.execute(f'DELETE FROM crawled_products WHERE id IN ({placeholders})', chunk)
                conn.commit()
            finally:
                conn.close()

    def backup_current_products(self, custom_name="", product_codes=None):
        """현재 crawled_products 테이블의 내용을 새로운 그룹으로 스냅샷 백업합니다."""
        with self.lock:
            conn = self.connect()
            try:
                c = conn.cursor()
                now = datetime.datetime.now()
                group_id = now.strftime("backup_%Y%m%d_%H%M%S_%f")
                b_name = custom_name.strip() if custom_name else now.strftime("%y년 %m월 %d일 %H:%M 백업본")

                if product_codes is not None:
                    # SQLite 매개변수 개수 제한(999개)을 극복하기 위해 청크 단위로 나누어 인서트합니다.
                    limit = 999
                    for i in range(0, len(product_codes), limit):
                        chunk = product_codes[i:i+limit]
                        placeholders = ",".join("?" for _ in chunk)
                        query = f'''
                            INSERT INTO crawled_products_backup (platform, title, product_code, created_at, data_json, backup_group_id, backup_name)
                            SELECT platform, title, product_code, created_at, data_json, ?, ? FROM crawled_products
                            WHERE product_code IN ({placeholders})
                        '''
                        c.execute(query, [group_id, b_name] + chunk)
                else:
                    c.execute('''
                        INSERT INTO crawled_products_backup (platform, title, product_code, created_at, data_json, backup_group_id, backup_name)
                        SELECT platform, title, product_code, created_at, data_json, ?, ? FROM crawled_products
                    ''', (group_id, b_name))
                    
                conn.commit()
                return group_id
            finally:
                conn.close()

    def get_backup_products_by_group(self, group_id):
        """특정 백업 그룹의 상품 데이터를 반환합니다."""
        with self.lock:
            conn = self.connect()
            try:
                c = conn.cursor()
                if group_id == 'legacy':
                    c.execute('SELECT data_json FROM crawled_products_backup WHERE backup_group_id IS NULL ORDER BY id ASC')
                else:
                    c.execute('SELECT data_json FROM crawled_products_backup WHERE backup_group_id = ? ORDER BY id ASC', (group_id,))
                rows = c.fetchall()
            finally:
                conn.close()

            results = []
            for row in rows:
                try:
                    results.append(json.loads(row[0]))
                except:
                    pass
            return results

    def delete_backup_products_by_group_indices(self, group_id, indices):
        """특정 백업 그룹에서 원본 정렬 인덱스 기준으로 선택 상품을 삭제합니다."""
        if not indices:
            return 0

        safe_indices = []
        for index in indices:
            try:
                index_int = int(index)
            except (TypeError, ValueError):
                continue
            if index_int >= 0:
                safe_indices.append(index_int)

        if not safe_indices:
            return 0

        with self.lock:
            conn = self.connect()
            try:
                c = conn.cursor()
                deleted = 0

                # 큰 인덱스부터 삭제해야 앞쪽 항목의 OFFSET이 밀리지 않습니다.
                for index in sorted(set(safe_indices), reverse=True):
                    if group_id == 'legacy':
                        c.execute(
                            'SELECT id FROM crawled_products_backup WHERE backup_group_id IS NULL ORDER BY id ASC LIMIT 1 OFFSET ?',
                            (index,)
                        )
                    else:
                        c.execute(
                            'SELECT id FROM crawled_products_backup WHERE backup_group_id = ? ORDER BY id ASC LIMIT 1 OFFSET ?',
                            (group_id, index)
                        )
                    row = c.fetchone()
                    if row:
                        c.execute('DELETE FROM crawled_products_backup WHERE id=?', (row[0],))
                        deleted += c.rowcount

                conn.commit()
                return deleted
            finally:
                conn.close()

    def delete_backup_groups(self, group_ids):
        """선택한 백업 슬롯 전체를 삭제합니다."""
        if not group_ids:
            return 0

        safe_group_ids = []
        for group_id in group_ids:
            group_id = str(group_id or "").strip()
            if group_id:
                safe_group_ids.append(group_id)

        if not safe_group_ids:
            return 0

        with self.lock:
            conn = self.connect()
            try:
                c = conn.cursor()
                deleted = 0
                for group_id in sorted(set(safe_group_ids)):
                    if group_id == 'legacy':
                        c.execute('DELETE FROM crawled_products_backup WHERE backup_group_id IS NULL')
                    else:
                        c.execute('DELETE FROM crawled_products_backup WHERE backup_group_id = ?', (group_id,))
                    deleted += c.rowcount

                conn.commit()
                return deleted
            finally:
                conn.close()

    def get_backup_groups_info(self):
        """백업 세션(그룹) 목록을 반환합니다."""
        with self.lock:
            conn = self.connect()
            try:
                c = conn.cursor()
                c.execute('''
                    SELECT IFNULL(backup_group_id, 'legacy'),
                           MAX(IFNULL(backup_name, '이전 백업(덮어쓰기됨)')),
                           COUNT(*),
                           MAX(created_at)
                    FROM crawled_products_backup
                    GROUP BY IFNULL(backup_group_id, 'legacy')
                    ORDER BY MAX(created_at) DESC
                ''')
                rows = c.fetchall()
            finally:
                conn.close()

            groups = []
            for r in rows:
                groups.append({
                    "backup_group_id": r[0],
                    "backup_name": r[1],
                    "count": r[2],
                    "last_date": r[3]
                })
            return groups


    # --- Phase 6: Operational Methods ---
    def check_is_posted(self, product_code: str, platform: str, content_signature: str = "") -> bool:
        """이전 포스팅 이력이 있는지 다중 조건으로 안전하게 검사합니다. (SUCCESS 상태만 중복으로 간주)"""
        if not product_code and not content_signature:
            return False
        with self.lock:
            conn = self.connect()
            c = conn.cursor()
            try:
                if content_signature:
                    c.execute('''
                        SELECT 1 FROM post_history
                        WHERE content_signature = ? AND platform = ? AND status = 'SUCCESS'
                    ''', (content_signature, platform))
                    if c.fetchone():
                        return True
                if product_code:
                    c.execute('''
                        SELECT 1 FROM post_history
                        WHERE product_code = ? AND platform = ? AND status = 'SUCCESS'
                    ''', (product_code, platform))
                    if c.fetchone():
                        return True
                return False
            except Exception as e:
                print(f"Error checking duplicate post: {e}")
                return False
            finally:
                conn.close()

    def is_already_posted(self, product_code: str, platform: str, content_signature: str = "") -> bool:
        """해당 상품/콘텐츠가 특정 플랫폼에 성공적으로 게시된 이력이 있는지 확인합니다."""
        if not product_code and not content_signature:
            return False
        with self.lock:
            conn = self.connect()
            c = conn.cursor()
            if content_signature:
                c.execute('''
                    SELECT 1 FROM post_history
                    WHERE content_signature = ? AND platform = ? AND status = 'SUCCESS'
                ''', (content_signature, platform))
            else:
                c.execute('''
                    SELECT 1 FROM post_history
                    WHERE product_code = ? AND platform = ? AND status = 'SUCCESS'
                ''', (product_code, platform))
            row = c.fetchone()
            conn.close()
            return bool(row)

    def add_post_history(self, product_code: str, platform: str, account_profile: str, status: str, error_reason: str = "", content_signature: str = ""):
        """게시 성공, 실패, 혹은 드라이런 기록을 저장합니다."""
        with self.lock:
            conn = self.connect()
            c = conn.cursor()
            c.execute('''
                INSERT INTO post_history (product_code, content_signature, platform, account_profile, status, error_reason)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (product_code, content_signature, platform, account_profile, status, error_reason))
            conn.commit()
            conn.close()

    def get_latest_post_status_map(self):
        """콘텐츠 해시/플랫폼별 최신 게시 상태를 반환합니다."""
        with self.lock:
            conn = self.connect()
            c = conn.cursor()
            c.execute('''
                SELECT product_code, content_signature, platform, status, error_reason
                FROM post_history
                ORDER BY id ASC
            ''')
            rows = c.fetchall()
            conn.close()

        status_map = {}
        for product_code, content_signature, platform, status, error_reason in rows:
            if not platform:
                continue
            if content_signature:
                key = (f"signature:{content_signature}", platform)
            elif product_code:
                key = (f"code:{product_code}", platform)
            else:
                continue
            status_map[key] = {
                "status": status,
                "error_reason": error_reason or ""
            }
        return status_map

    def update_vendor_crawl_history(self, vendor_id: str, vendor_name: str, last_crawled_date: str, crawled_count: int):
        with self.lock:
            conn = self.connect()
            c = conn.cursor()
            try:
                c.execute('''
                    INSERT OR REPLACE INTO vendor_crawl_history
                    (vendor_id, vendor_name, last_crawled_date, crawled_count, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (vendor_id, vendor_name, last_crawled_date, crawled_count))
                conn.commit()
            except Exception as e:
                print(f"Error updating vendor history: {e}")
            finally:
                conn.close()

    def get_all_vendor_crawl_history(self):
        with self.lock:
            conn = self.connect()
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            try:
                c.execute('SELECT * FROM vendor_crawl_history')
                rows = c.fetchall()
                return [dict(row) for row in rows]
            except Exception as e:
                print(f"Error getting vendor history: {e}")
                return []
            finally:
                conn.close()

    def record_crawl_event(self, platform: str, event_type: str, vendor_id: str = "",
                           vendor_name: str = "", reason: str = "", raw_text: str = "",
                           metadata: dict | None = None):
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        raw_text = (raw_text or "")[:4000]
        with self.lock:
            conn = self.connect()
            c = conn.cursor()
            try:
                c.execute('''
                    INSERT INTO crawl_telemetry
                    (platform, event_type, vendor_id, vendor_name, reason, raw_text, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (platform, event_type, vendor_id, vendor_name, reason, raw_text, metadata_json))
                conn.commit()
            except Exception as e:
                print(f"Error recording crawl telemetry: {e}")
            finally:
                conn.close()

    def get_recent_crawl_events(self, platform: str | None = None, event_types: list | None = None,
                                limit: int = 300):
        with self.lock:
            conn = self.connect()
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            try:
                where = []
                params = []
                if platform:
                    where.append("platform = ?")
                    params.append(platform)
                if event_types:
                    placeholders = ",".join("?" for _ in event_types)
                    where.append(f"event_type IN ({placeholders})")
                    params.extend(event_types)
                where_sql = "WHERE " + " AND ".join(where) if where else ""
                params.append(int(limit))
                c.execute(f'''
                    SELECT * FROM crawl_telemetry
                    {where_sql}
                    ORDER BY id DESC
                    LIMIT ?
                ''', params)
                rows = c.fetchall()
                results = []
                for row in rows:
                    item = dict(row)
                    try:
                        item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
                    except Exception:
                        item["metadata"] = {}
                    results.append(item)
                return results
            except Exception as e:
                print(f"Error getting crawl telemetry: {e}")
                return []
            finally:
                conn.close()

    # --- Job Queue Helper Methods ---
    def add_job(self, task_type: str, payload: dict) -> int:
        """새로운 작업을 큐에 추가합니다."""
        payload_str = json.dumps(payload, ensure_ascii=False)
        with self.lock:
            conn = self.connect()
            c = conn.cursor()
            try:
                c.execute('''
                    INSERT INTO job_queue (task_type, payload_json, status, retry_count)
                    VALUES (?, ?, 'PENDING', 0)
                ''', (task_type, payload_str))
                row_id = c.lastrowid
                conn.commit()
                return row_id
            except Exception as e:
                print(f"Error adding job to queue: {e}")
                return -1
            finally:
                conn.close()

    # --- Scheduler Task Helper Methods ---
    def add_scheduler_task(self, name: str, interval_type: str, interval_value: str,
                           source_platform: str, target_platforms: list, crawling_count: int,
                           delay_min: int = 15, delay_max: int = 45) -> int:
        import json
        target_platforms_str = json.dumps(target_platforms, ensure_ascii=False)
        with self.lock:
            conn = self.connect()
            c = conn.cursor()
            try:
                c.execute('''
                    INSERT INTO scheduler_tasks (name, interval_type, interval_value, source_platform, target_platforms, crawling_count, delay_min, delay_max, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                ''', (name, interval_type, interval_value, source_platform, target_platforms_str, crawling_count, delay_min, delay_max))
                row_id = c.lastrowid
                conn.commit()
                return row_id
            finally:
                conn.close()

    def get_all_scheduler_tasks(self) -> list:
        import json
        with self.lock:
            conn = self.connect()
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            try:
                c.execute('SELECT * FROM scheduler_tasks ORDER BY id DESC')
                rows = c.fetchall()
                results = []
                for r in rows:
                    item = dict(r)
                    try:
                        item["target_platforms"] = json.loads(item["target_platforms"] or "[]")
                    except:
                        item["target_platforms"] = []
                    results.append(item)
                return results
            finally:
                conn.close()

    def get_scheduler_task(self, task_id: int) -> dict:
        import json
        with self.lock:
            conn = self.connect()
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            try:
                c.execute('SELECT * FROM scheduler_tasks WHERE id = ?', (task_id,))
                row = c.fetchone()
                if row:
                    item = dict(row)
                    try:
                        item["target_platforms"] = json.loads(item["target_platforms"] or "[]")
                    except:
                        item["target_platforms"] = []
                    return item
                return None
            finally:
                conn.close()

    def delete_scheduler_task(self, task_id: int):
        with self.lock:
            conn = self.connect()
            c = conn.cursor()
            try:
                c.execute('DELETE FROM scheduler_tasks WHERE id = ?', (task_id,))
                conn.commit()
            finally:
                conn.close()

    def toggle_scheduler_task(self, task_id: int) -> bool:
        with self.lock:
            conn = self.connect()
            c = conn.cursor()
            try:
                c.execute('SELECT is_active FROM scheduler_tasks WHERE id = ?', (task_id,))
                row = c.fetchone()
                if row:
                    new_state = 0 if row[0] == 1 else 1
                    c.execute('UPDATE scheduler_tasks SET is_active = ? WHERE id = ?', (new_state, task_id))
                    conn.commit()
                    return bool(new_state)
                return False
            finally:
                conn.close()

    def update_scheduler_task_run_time(self, task_id: int, last_run: str, next_run: str):
        with self.lock:
            conn = self.connect()
            c = conn.cursor()
            try:
                c.execute('''
                    UPDATE scheduler_tasks
                    SET last_run_at = ?, next_run_at = ?
                    WHERE id = ?
                ''', (last_run, next_run, task_id))
                conn.commit()
            finally:
                conn.close()

    def get_next_pending_job(self):
        """PENDING 상태인 다음 작업을 가져옵니다."""
        with self.lock:
            conn = self.connect()
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            try:
                c.execute('''
                    SELECT id, task_type, payload_json, status, retry_count, error_msg, created_at, updated_at
                    FROM job_queue
                    WHERE status = 'PENDING'
                    ORDER BY id ASC
                    LIMIT 1
                ''')
                row = c.fetchone()
                if row:
                    job = dict(row)
                    job["payload"] = json.loads(job["payload_json"]) if job["payload_json"] else {}
                    return job
                return None
            except Exception as e:
                print(f"Error fetching next pending job: {e}")
                return None
            finally:
                conn.close()

    def update_job_status(self, job_id: int, status: str, error_msg: str = None, increment_retry: bool = False):
        """작업의 상태와 에러 메시지를 업데이트하고, 선택적으로 재시도 횟수를 증가시킵니다."""
        with self.lock:
            conn = self.connect()
            c = conn.cursor()
            try:
                if increment_retry:
                    c.execute('''
                        UPDATE job_queue
                        SET status = ?, error_msg = ?, retry_count = retry_count + 1, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (status, error_msg, job_id))
                else:
                    c.execute('''
                        UPDATE job_queue
                        SET status = ?, error_msg = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                      ''', (status, error_msg, job_id))
                conn.commit()
            except Exception as e:
                print(f"Error updating job status: {e}")
            finally:
                conn.close()

    def get_job_stats(self) -> dict:
        """작업 큐 상태별 통계를 반환합니다."""
        with self.lock:
            conn = self.connect()
            c = conn.cursor()
            try:
                c.execute('''
                    SELECT status, COUNT(*)
                    FROM job_queue
                    GROUP BY status
                ''')
                rows = c.fetchall()
                stats = {"PENDING": 0, "RUNNING": 0, "COMPLETED": 0, "FAILED": 0}
                for status, count in rows:
                    if status in stats:
                        stats[status] = count
                return stats
            except Exception as e:
                print(f"Error getting job stats: {e}")
                return {}
            finally:
                conn.close()

    def get_all_jobs(self, limit: int = 50) -> list:
        """전체 작업 목록을 조회합니다."""
        with self.lock:
            conn = self.connect()
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            try:
                c.execute('''
                    SELECT id, task_type, payload_json, status, retry_count, error_msg, created_at, updated_at
                    FROM job_queue
                    ORDER BY id DESC
                    LIMIT ?
                ''', (limit,))
                rows = c.fetchall()
                jobs = []
                for row in rows:
                    job = dict(row)
                    job["payload"] = json.loads(job["payload_json"]) if job["payload_json"] else {}
                    jobs.append(job)
                return jobs
            except Exception as e:
                print(f"Error getting all jobs: {e}")
                return []
            finally:
                conn.close()

    def get_user_points(self) -> int:
        """사용자의 현재 잔여 포인트 크레딧을 조회합니다."""
        with self.lock:
            conn = self.connect()
            c = conn.cursor()
            try:
                c.execute("SELECT points FROM user_points LIMIT 1")
                row = c.fetchone()
                return row[0] if row else 0
            except Exception as e:
                print(f"Error getting user points: {e}")
                return 0
            finally:
                conn.close()

    def add_points(self, amount: int, reason: str) -> int:
        """사용자에게 크레딧 포인트를 적립하고 이력을 남깁니다."""
        with self.lock:
            conn = self.connect()
            try:
                c = conn.cursor()
                c.execute("SELECT points FROM user_points LIMIT 1")
                row = c.fetchone()
                current = row[0] if row else 0
                new_points = current + amount
                
                if row:
                    c.execute("UPDATE user_points SET points = ?, updated_at = CURRENT_TIMESTAMP", (new_points,))
                else:
                    c.execute("INSERT INTO user_points (points) VALUES (?)", (new_points,))
                
                c.execute("INSERT INTO point_history (points_changed, reason) VALUES (?, ?)", (amount, reason))
                conn.commit()
                return new_points
            except Exception as e:
                conn.rollback()
                print(f"Error adding points: {e}")
                raise e
            finally:
                conn.close()

    def get_point_history(self, limit: int = 50) -> list:
        """최근 포인트 적립 및 변동 이력을 조회합니다."""
        with self.lock:
            conn = self.connect()
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            try:
                c.execute('''
                    SELECT id, points_changed, reason, created_at
                    FROM point_history
                    ORDER BY id DESC
                    LIMIT ?
                ''', (limit,))
                rows = c.fetchall()
                return [dict(row) for row in rows]
            except Exception as e:
                print(f"Error getting point history: {e}")
                return []
            finally:
                conn.close()

# Singleton instance
db_instance = None
def get_db():
    global db_instance
    if db_instance is None:
        db_instance = CrawlDB()
    return db_instance

# --- LLM Caching Helpers ---
import hashlib

def get_cached_translation(source_text: str, category: str, image_key: str = ""):
    """주어진 원문과 카테고리에 대한 캐시된 번역 결과를 반환합니다."""
    if not source_text: return None
    db = get_db()

    # image_key(사진 파일명/경로)를 캐시 해시에 포함하여 텍스트가 같아도 사진이 다르면 구분함 (브랜드 충돌 방지)
    hash_str = f"{category}_{source_text}_{image_key}"
    source_hash = hashlib.md5(hash_str.encode('utf-8')).hexdigest()

    with db.lock:
        conn = db.connect()
        c = conn.cursor()
        c.execute('SELECT translated_text FROM translation_cache WHERE source_hash = ?', (source_hash,))
        row = c.fetchone()
        conn.close()

        if row:
            return row[0]
        return None

def set_cached_translation(source_text: str, translated_text: str, category: str, image_key: str = ""):
    """성공한 번역 결과를 DB에 캐싱합니다."""
    if not source_text or not translated_text: return
    db = get_db()
    hash_str = f"{category}_{source_text}_{image_key}"
    source_hash = hashlib.md5(hash_str.encode('utf-8')).hexdigest()

    with db.lock:
        conn = db.connect()
        c = conn.cursor()
        try:
            c.execute('''
                INSERT OR REPLACE INTO translation_cache (source_hash, source_text, translated_text, category)
                VALUES (?, ?, ?, ?)
            ''', (source_hash, source_text, translated_text, category))
            conn.commit()
        except Exception as e:
            pass
        finally:
            conn.close()
