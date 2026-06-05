"""database.py LIMIT 100 제거 스크립트"""
path = r'd:\안티그래비티\winwin크롤러2\backend\database.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old_query = "c.execute('SELECT data_json, created_at FROM crawled_products_backup ORDER BY id DESC LIMIT 100')"
new_query = "c.execute('SELECT data_json, created_at FROM crawled_products_backup ORDER BY id ASC')"

# wait, api_server.py's get_backup_info NO LONGER uses get_backup_info_db() rows!
# I completely rewrote get_backup_info() in api_server.py to use `db.get_backup_products()` !
# Let's verify this!
