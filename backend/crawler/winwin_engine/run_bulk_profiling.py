"""
run_bulk_profiling.py - 259개 업체 일괄 AI 프로파일링 실행 스크립트
================================================================
이 스크립트는 현재 실행 중인 FastAPI 서버(8001포트)에 
벌크 프로파일링 API를 호출합니다.

사용법:
    python run_bulk_profiling.py
"""

import json
import os
import sys
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENDOR_FILE = os.path.join(BASE_DIR, "weishang_vendors.json")
API_URL = "http://localhost:8001/api/profile_vendors_bulk"


def main():
    # 1. 업체 목록 로드
    try:
        with open(VENDOR_FILE, "r", encoding="utf-8") as f:
            vendors = json.load(f)
    except Exception as e:
        print(f"❌ 업체 파일 로드 실패: {e}")
        sys.exit(1)

    # 2. 이미 AI 규칙이 있는 업체는 제외 (선택)
    override_file = os.path.join(BASE_DIR, "backend", "ai_dynamic_overrides.json")
    already_profiled = set()
    try:
        with open(override_file, "r", encoding="utf-8") as f:
            overrides = json.load(f)
        for k, v in overrides.items():
            if k not in ("_meta", "global") and isinstance(v, dict):
                # price_regex가 이미 설정된 업체는 기존 규칙 유지
                if v.get("price_regex"):
                    already_profiled.add(k)
    except Exception:
        pass

    # 3. 프로파일링 대상 업체 ID 추출
    all_ids = [v["id"] for v in vendors if v.get("id")]
    target_ids = [vid for vid in all_ids if vid not in already_profiled]

    print(f"📊 전체 업체: {len(all_ids)}개")
    print(f"📊 이미 프로파일링 완료(price_regex 있음): {len(already_profiled)}개")
    print(f"📊 프로파일링 대상: {len(target_ids)}개")
    print()

    if not target_ids:
        print("✅ 모든 업체가 이미 프로파일링되었습니다.")
        return

    # 4. 배치 분할 (한 번에 너무 많이 보내면 타임아웃 위험)
    BATCH_SIZE = 20  # 20개씩 나눠서 실행
    batches = [target_ids[i:i+BATCH_SIZE] for i in range(0, len(target_ids), BATCH_SIZE)]

    print(f"📦 {len(batches)}개 배치로 나누어 실행합니다 (배치당 {BATCH_SIZE}개)")
    print(f"⏱️  예상 소요시간: 업체당 약 2-3분 × {len(target_ids)}개 = 약 {len(target_ids) * 2.5 / 60:.0f}시간")
    print()

    input("⚠️  계속 진행하려면 Enter 키를 누르세요... (Ctrl+C로 취소)")

    for batch_idx, batch in enumerate(batches):
        print(f"\n{'='*60}")
        print(f"🚀 배치 {batch_idx + 1}/{len(batches)} 시작 ({len(batch)}개 업체)")
        print(f"{'='*60}")

        payload = json.dumps({
            "vendor_ids": batch,
            "api_key": ""  # 서버에 이미 설정된 API 키 사용
        }).encode("utf-8")

        req = urllib.request.Request(
            API_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                print(f"✅ 배치 {batch_idx + 1} 응답: {result.get('message', result)}")
        except Exception as e:
            print(f"❌ 배치 {batch_idx + 1} 실패: {e}")
            print("   서버가 실행 중인지 확인하세요: http://localhost:8001")
            retry = input("   다시 시도하시겠습니까? (y/n): ")
            if retry.lower() == 'y':
                try:
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        result = json.loads(resp.read().decode("utf-8"))
                        print(f"✅ 재시도 성공: {result.get('message', result)}")
                except Exception as e2:
                    print(f"❌ 재시도 실패: {e2}")
                    continue
            else:
                continue

        # 배치 사이 대기 (FastAPI 백그라운드 태스크는 순차 처리)
        if batch_idx < len(batches) - 1:
            import time
            wait_time = len(batch) * 150  # 업체당 약 2.5분 = 150초 대기
            print(f"\n⏱️  다음 배치까지 {wait_time}초 대기 (현재 배치 처리 중)...")
            print(f"   서버 콘솔에서 진행 상황을 확인하세요.")
            time.sleep(wait_time)

    print(f"\n{'='*60}")
    print(f"🎉 전체 일괄 프로파일링 요청 완료!")
    print(f"   서버 콘솔에서 최종 진행 상황을 확인하세요.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
