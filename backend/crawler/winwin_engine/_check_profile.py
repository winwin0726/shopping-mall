import json, os, datetime

f = r'c:\programing\윈윈크롤러2\weishang_vendors.json'
mod_time = os.path.getmtime(f)
mod_dt = datetime.datetime.fromtimestamp(mod_time)
print(f"파일 마지막 수정: {mod_dt}")
print(f"파일 크기: {os.path.getsize(f):,} bytes")
print()

v = json.load(open(f, 'r', encoding='utf-8'))
total = len(v)
has_profile = sum(1 for x in v if x.get('profile_rules'))
has_regex = sum(1 for x in v if x.get('price_regex'))
has_boundary = sum(1 for x in v if x.get('boundary_signals'))
no_profile = sum(1 for x in v if not x.get('profile_rules'))

print("=== 실시간 확인 (지금 파일에서 직접 읽음) ===")
print(f"전체: {total}")
print(f"profile_rules 있음: {has_profile}")
print(f"profile_rules 없음: {no_profile}")
print(f"price_regex 있음: {has_regex}")
print(f"boundary_signals 있음: {has_boundary}")
print()

print(f"=== 아직 프로파일 안 된 업체 ({no_profile}개) ===")
for i, x in enumerate(v):
    if not x.get('profile_rules'):
        vid = x.get('id', '?')[:25]
        nm = x.get('name', '?')[:30]
        print(f"  {i+1}. {vid}... | {nm}")
