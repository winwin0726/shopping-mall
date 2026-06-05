"""
run_all_profiling.py - 254개 업체 자동 순차 프로파일링
====================================================
첫 5개 테스트 배치가 이미 실행 중이므로, 나머지를 20개씩 배치로 전송합니다.
이전 배치가 완료될 때까지 기다린 후 다음 배치를 전송합니다.
"""

import json
import os
import sys
import time
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENDOR_FILE = os.path.join(BASE_DIR, "weishang_vendors.json")
OVERRIDE_FILE = os.path.join(BASE_DIR, "backend", "ai_dynamic_overrides.json")
API_URL = "http://localhost:8001/api/profile_vendors_bulk"
STATUS_URL = "http://localhost:8001/api/status"

BATCH_SIZE = 20
SKIP_FIRST_N = 5  # 이미 첫 5개는 테스트 배치로 실행됨


def get_target_ids():
    """프로파일링 대상 업체 ID 목록을 반환합니다."""
    with open(VENDOR_FILE, "r", encoding="utf-8") as f:
        vendors = json.load(f)
    
    already = set()
    try:
        with open(OVERRIDE_FILE, "r", encoding="utf-8") as f:
            overrides = json.load(f)
        for k, v in overrides.items():
            if k not in ("_meta", "global") and isinstance(v, dict) and v.get("price_regex"):
                already.add(k)
    except Exception:
        pass

    all_ids = [v["id"] for v in vendors if v.get("id")]
    return [vid for vid in all_ids if vid not in already]


def send_batch(vendor_ids, batch_num, total_batches):
    """배치를 서버에 전송합니다."""
    payload = json.dumps({
        "vendor_ids": vendor_ids,
        "api_key": ""
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
            print(f"  ✅ 배치 {batch_num}/{total_batches} 전송 성공: {result.get('message', '')}")
            return True
    except Exception as e:
        print(f"  ❌ 배치 {batch_num}/{total_batches} 전송 실패: {e}")
        return False


def wait_with_progress(seconds, message=""):
    """진행 표시가 있는 대기"""
    print(f"  ⏱️ {message} ({seconds}초 대기)")
    for i in range(0, seconds, 30):
        remaining = seconds - i
        print(f"    ... 남은 시간: {remaining}초")
        time.sleep(min(30, remaining))


def main():
    target_ids = get_target_ids()
    remaining = target_ids[SKIP_FIRST_N:]  # 첫 5개는 이미 실행됨

    print(f"{'='*60}")
    print(f"🚀 254개 업체 일괄 프로파일링")
    print(f"{'='*60}")
    print(f"전체 대상: {len(target_ids)}개")
    print(f"이미 실행됨: {SKIP_FIRST_N}개 (첫 테스트 배치)")
    print(f"이번 실행: {len(remaining)}개")
    print(f"배치 크기: {BATCH_SIZE}개")
    print(f"예상 소요: 업체당 ~2분 × {len(remaining)}개 = ~{len(remaining)*2/60:.0f}시간")
    print(f"{'='*60}")
    print()

    # 첫 배치가 끝날 때까지 대기 (5개 × 2.5분 = ~12분)
    print(f"📌 첫 테스트 배치 5개 완료 대기 중...")
    wait_with_progress(720, "첫 테스트 배치 완료 대기")

    # 나머지 배치 순차 실행
    batches = [remaining[i:i+BATCH_SIZE] for i in range(0, len(remaining), BATCH_SIZE)]
    total_batches = len(batches)

    print(f"\n📦 총 {total_batches}개 배치로 나머지 실행 시작\n")

    for idx, batch in enumerate(batches):
        batch_num = idx + 1
        print(f"\n{'─'*40}")
        print(f"🔄 배치 {batch_num}/{total_batches} ({len(batch)}개 업체)")

        success = send_batch(batch, batch_num, total_batches)
        if not success:
            retry = input("  재시도? (y/n): ").strip().lower()
            if retry == 'y':
                send_batch(batch, batch_num, total_batches)

        if idx < len(batches) - 1:
            wait_seconds = len(batch) * 120  # 업체당 2분 대기
            wait_with_progress(wait_seconds, f"배치 {batch_num} 처리 대기")

    print(f"\n{'='*60}")
    print(f"🎉 전체 일괄 프로파일링 요청 완료!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
