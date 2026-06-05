import os
import sys
import json
import time

# 윈도우 한글(CP949) 이모지 출력 깨짐 방지 
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from weishang_crawler import WeishangCrawler

print("======================================================")
print(" 🚀 [Winwin Crawler 3.3] 전 업체(287개) 일괄 AI 딥러닝 프로파일러 시작!")
print("======================================================")

if len(sys.argv) < 2:
    print("❌ API 키가 인수로 제공되지 않아 종료합니다.")
    sys.exit(1)
api_key = sys.argv[1].strip()
if not api_key:
    print("❌ API 키가 비어있어 종료합니다.")
    sys.exit(1)

vendor_file = "weishang_vendors.json"
try:
    with open(vendor_file, "r", encoding="utf-8") as f:
        vendor_list = json.load(f)
except Exception as e:
    print(f"❌ {vendor_file} 파일을 읽는 중 오류 발생: {e}")
    sys.exit(1)

print(f"\n📦 총 {len(vendor_list)}개의 업체가 등록되어 있습니다.")

def _log(msg, level="INFO", broadcast=False):
    print(f"[{level}] {msg}")

crawler = WeishangCrawler(log_func=_log)

# 이미 post_structure 가 있는 신규 프로파일 업체는 건너뛰기 가능 (원한다면 수정)
for idx, vendor in enumerate(vendor_list):
    name = vendor.get('name', 'Unknown')
    url = vendor.get('url', '')
    
    if 'post_structure' in vendor:
        print(f"⏭️ [{name}] 이미 최신 프로파일링이 완료되었습니다. 건너뜁니다.")
        continue

    print(f"\n======================================================")
    print(f" 🕵️‍♂️ [{idx+1}/{len(vendor_list)}] 프리미엄 업체 심화 분석 시작: {name}")
    print(f"======================================================")
    
    try:
        result = crawler.profile_vendor_style(url, api_key)
        
        if result and isinstance(result, dict):
            # ★ 핵심: AI 분석 결과를 해당 업체 레코드에 머지
            vendor.update(result)
            # 즉시 DB 파일에 저장 (매 업체 완료 시마다 안전 저장)
            with open(vendor_file, "w", encoding="utf-8") as f:
                json.dump(vendor_list, f, ensure_ascii=False, indent=2)
            ps = result.get('post_structure', 'N/A')[:60]
            print(f"✨ [{name}] AI 프로파일링 완료 & DB 저장 성공! (구조: {ps}...)")
        else:
            print(f"⚠️ [{name}] AI 딥러닝 실패 또는 데이터 부족.")
    except Exception as e:
        import traceback
        print(f"❌ [{name}] 분석 중 에러 발생: {e}")
        traceback.print_exc()
        
    print(f"⏳ 과부하 방지: 3초 대기...")
    time.sleep(3)

print("\n🎉 287개 업체 일괄 딥러닝 분석 태스크가 모두 종료되었습니다!")
