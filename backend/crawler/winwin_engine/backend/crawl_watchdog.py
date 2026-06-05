"""
crawl_watchdog.py — 크롤링 자체 감시 에이전트 (CrawlWatchdog)
================================================================
크롤링 세션이 끝날 때마다 자동으로 로그와 수집 결과를 분석하여:
1. 과잉 병합 문제를 감지하고
2. 단가 없는 업체를 자동 분류하고 (has_price: false)
3. 텍스트 부족 포스팅에 AI 비전 병합 검증 플래그를 설정하고
4. 일일 품질 리포트를 생성합니다.

자동 보정 정책 (B 모드):
  - 경미: 단가 없는 업체 분류, 비전 AI 병합 강제화 → 자동 반영
  - 중대: 포스팅 타입 변경 → 리포트만 (사용자 확인 후 반영)
"""

import os
import json
import re
import datetime
from pathlib import Path

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_DIR = Path(_PROJECT_ROOT) / "data" / "watchdog_reports"
OVERRIDES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_dynamic_overrides.json")


# ──────────────────────────────────────────
# 이상 유형 상수
# ──────────────────────────────────────────
class AnomalyType:
    OVER_MERGE = "과잉_병합"           # 한 상품에 이미지가 너무 많음
    NO_PRICE_VENDOR = "단가_없는_업체"  # 가격이 아예 없는 업체 → 자동 분류
    TEXT_EMPTY = "텍스트_부족_비전필요"  # 텍스트 없는 포스팅 → AI 비전 병합 검증 필요


class AnomalySeverity:
    AUTO_FIX = "auto_fix"       # 자동 보정 (경미)
    REPORT_ONLY = "report_only" # 리포트만 (중대 — 사용자 확인 필요)


# ──────────────────────────────────────────
# CrawlWatchdog 메인 클래스
# ──────────────────────────────────────────
class CrawlWatchdog:
    """크롤링 세션 품질 감시 에이전트"""

    def __init__(self, log_func=None, gemini_api_key=""):
        self.log_func = log_func or print
        self.api_key = gemini_api_key
        self.vendor_stats = {}      # vendor_id → 통계 dict
        self.alerts = []            # 감지된 이상 항목 리스트
        self.corrections = []       # 자동 보정 내역 리스트
        self.session_start = datetime.datetime.now()

    def _log(self, msg, level="INFO"):
        """내부 로그 출력"""
        try:
            self.log_func(f"🐕 [워치독] {msg}", level, False)
        except Exception:
            print(f"🐕 [워치독] {msg}")

    # ──────────────────────────────────────
    # 1단계: 업체별 세션 통계 수집
    # ──────────────────────────────────────
    def collect_vendor_stats(self, vendor_id, vendor_name, products, session_logs=None):
        """
        크롤링 완료된 업체의 수집 결과를 분석하여 통계를 수집합니다.
        
        Args:
            vendor_id: 업체 고유 ID
            vendor_name: 업체 이름
            products: 수집된 상품 리스트 (dict 목록)
            session_logs: 해당 업체의 로그 문자열 (선택)
        """
        if not products:
            products = []

        img_counts = []
        price_detected_count = 0
        text_lengths = []
        
        for p in products:
            # 이미지 수 통계
            n_imgs = len(p.get("image_files", []) or p.get("image_urls", []) or [])
            img_counts.append(n_imgs)
            # 가격 파싱 성공 여부
            if p.get("price_detected", False):
                price_detected_count += 1
            # 텍스트 길이
            text_lengths.append(len(p.get("original_chinese", "") or ""))

        total = len(products)
        avg_images = sum(img_counts) / max(1, total)
        max_images = max(img_counts) if img_counts else 0
        price_rate = (price_detected_count / max(1, total)) * 100
        short_text_count = sum(1 for t in text_lengths if t < 10)
        short_text_rate = (short_text_count / max(1, total)) * 100

        # 다운로드 실패 통계 (로그에서 추출)
        dl_fail_count = 0
        dl_total_count = 0
        if session_logs:
            dl_fail_count = len(re.findall(r"직접 다운로드 실패|다운로드 스킵", session_logs))
            dl_total_count = len(re.findall(r"리스트 직접 다운로드|다운로드 버튼", session_logs))

        # 병합 통계 (로그에서 추출)
        merge_count = 0
        split_count = 0
        if session_logs:
            merge_count = len(re.findall(r"보충컷으로 병합|직접 병합|직전 상품에 병합", session_logs))
            split_count = len(re.findall(r"새 상품으로 분리|새 상품 확정|새 상품 포스팅으로 절단", session_logs))

        stats = {
            "vendor_id": vendor_id,
            "vendor_name": vendor_name,
            "total_products": total,
            "avg_images": round(avg_images, 1),
            "max_images": max_images,
            "price_rate": round(price_rate, 1),
            "short_text_rate": round(short_text_rate, 1),
            "dl_fail_count": dl_fail_count,
            "dl_total_count": dl_total_count,
            "dl_fail_rate": round((dl_fail_count / max(1, dl_total_count)) * 100, 1),
            "merge_count": merge_count,
            "split_count": split_count,
            "collected_at": datetime.datetime.now().isoformat(),
        }

        self.vendor_stats[vendor_id] = stats
        self._log(
            f"📊 {vendor_name}: 상품 {total}개, "
            f"평균 이미지 {avg_images:.0f}장, 최대 {max_images}장, "
            f"가격 파싱 {price_rate:.0f}%, 텍스트부족 {short_text_rate:.0f}%"
        )

    # ──────────────────────────────────────
    # 2단계: 이상 탐지 (규칙 기반)
    # ──────────────────────────────────────
    def detect_anomalies(self):
        """모든 업체 통계를 분석하여 이상 항목을 감지합니다."""
        self.alerts = []

        for vid, stats in self.vendor_stats.items():
            vname = stats.get("vendor_name", vid)

            # 규칙 1: 과잉 병합 — 한 상품에 이미지 40장 초과
            if stats["max_images"] > 40:
                self.alerts.append({
                    "vendor_id": vid,
                    "vendor_name": vname,
                    "type": AnomalyType.OVER_MERGE,
                    "severity": AnomalySeverity.REPORT_ONLY,  # 중대: 포스팅 타입 변경 필요
                    "detail": f"최대 이미지 {stats['max_images']}장 (40장 초과). posting_type을 'single'로 변경 검토 필요.",
                    "suggestion": {"posting_type": "single"},
                })

            # 규칙 2: 단가 없는 업체 자동 분류
            # 가격 파싱 성공률 5% 이하 = 단가 자체가 없는데 일부 숫자가 오탐된 업체로 간주 → has_price: false 설정
            # 가격 파싱 성공률 5% 초과 ~ 59% = 가격이 있지만 패턴이 맞지 않음 → 리포트만
            if stats["total_products"] >= 2:
                if stats["price_rate"] <= 5:
                    # 단가가 아예 없는 (혹은 오탐률이 극히 낮은) 업체 → 자동 분류
                    self.alerts.append({
                        "vendor_id": vid,
                        "vendor_name": vname,
                        "type": AnomalyType.NO_PRICE_VENDOR,
                        "severity": AnomalySeverity.AUTO_FIX,
                        "detail": f"가격 파싱 {stats['price_rate']}% (전체 {stats['total_products']}개 중). 단가 없는 업체로 분류합니다.",
                        "suggestion": {"has_price": False, "no_price_vendor": True},
                    })
                elif stats["price_rate"] < 60:
                    # 가격이 있지만 파싱이 안 되는 경우 → 패턴 재분석 필요
                    self.alerts.append({
                        "vendor_id": vid,
                        "vendor_name": vname,
                        "type": AnomalyType.NO_PRICE_VENDOR,
                        "severity": AnomalySeverity.REPORT_ONLY,
                        "detail": f"가격 파싱 {stats['price_rate']:.0f}%. 가격 패턴이 존재하나 추출 실패. 업체 관리에서 가격 regex 확인 필요.",
                        "suggestion": {"needs_price_reanalysis": True},
                    })

            # 규칙 3: 텍스트 부족 → AI 비전 병합 검증 필수화
            # 텍스트 없는 포스팅은 다른 포스팅의 보충 사진일 수 있으므로
            # AI 비전으로 동일 상품인지 확인 후 병합해야 함
            if stats["total_products"] >= 2 and stats["short_text_rate"] > 30:
                self.alerts.append({
                    "vendor_id": vid,
                    "vendor_name": vname,
                    "type": AnomalyType.TEXT_EMPTY,
                    "severity": AnomalySeverity.AUTO_FIX,
                    "detail": (
                        f"텍스트 10자 미만 비율 {stats['short_text_rate']:.0f}%. "
                        f"텍스트 없는 포스팅은 다른 상품의 보충 사진일 가능성이 높습니다. "
                        f"AI 비전 병합 검증을 강제 활성화합니다."
                    ),
                    "suggestion": {"force_vision_merge": True},
                })

        if self.alerts:
            self._log(f"⚠️ 이상 감지 {len(self.alerts)}건", "WARNING")
            for a in self.alerts:
                icon = "🔧" if a["severity"] == AnomalySeverity.AUTO_FIX else "📋"
                action = "자동 보정" if a["severity"] == AnomalySeverity.AUTO_FIX else "수동 확인 필요"
                self._log(f"  {icon} [{a['type']}] {a['vendor_name']}: {a['detail']} → {action}", "WARNING")
        else:
            self._log("✅ 이상 없음 — 모든 업체 정상 범위")

        return self.alerts

    # ──────────────────────────────────────
    # 3단계: 자동 보정 (경미한 것만)
    # ──────────────────────────────────────
    def auto_correct(self):
        """AUTO_FIX 등급의 이상만 자동으로 ai_dynamic_overrides.json에 반영합니다."""
        auto_alerts = [a for a in self.alerts if a["severity"] == AnomalySeverity.AUTO_FIX]
        if not auto_alerts:
            self._log("자동 보정 대상 없음")
            return

        # 현재 overrides 파일 로드
        overrides = {}
        if os.path.exists(OVERRIDES_PATH):
            try:
                with open(OVERRIDES_PATH, "r", encoding="utf-8") as f:
                    overrides = json.load(f)
            except Exception:
                overrides = {}

        for alert in auto_alerts:
            vid = alert["vendor_id"]
            suggestion = alert.get("suggestion", {})
            if not suggestion:
                continue

            # overrides에 해당 업체가 없으면 새로 생성
            vendor_data = overrides.get(vid, {})
            if not vendor_data:
                vendor_data = {"vendor_id": vid}
            changes_made = []

            # 단가 없는 업체 → has_price: false 자동 설정
            if suggestion.get("no_price_vendor"):
                vendor_data["has_price"] = False
                changes_made.append("has_price=False (단가 없는 업체)")

            # 텍스트 부족 → AI 비전 병합 검증 강제 활성화
            if suggestion.get("force_vision_merge"):
                vendor_data["force_vision_merge"] = True
                changes_made.append("force_vision_merge=True (텍스트 없는 포스팅 비전 AI 검증)")

            if changes_made:
                overrides[vid] = vendor_data
                change_desc = ", ".join(changes_made)
                self.corrections.append({
                    "vendor_id": vid,
                    "vendor_name": alert["vendor_name"],
                    "type": alert["type"],
                    "changes": changes_made,
                    "timestamp": datetime.datetime.now().isoformat(),
                })
                self._log(f"🔧 자동 보정 완료: {alert['vendor_name']} → {change_desc}")

        # overrides 파일 저장
        if self.corrections:
            try:
                with open(OVERRIDES_PATH, "w", encoding="utf-8") as f:
                    json.dump(overrides, f, ensure_ascii=False, indent=2)
                self._log(f"💾 ai_dynamic_overrides.json 업데이트 완료 ({len(self.corrections)}건)")
            except Exception as e:
                self._log(f"❌ overrides 파일 저장 실패: {e}", "ERROR")

        # 단가 없는 업체는 weishang_vendors.json에도 반영
        self._update_vendor_list_no_price()

    def _update_vendor_list_no_price(self):
        """단가 없는 업체를 weishang_vendors.json에서 자동 분류합니다."""
        no_price_vendors = [
            a for a in self.alerts
            if a.get("type") == AnomalyType.NO_PRICE_VENDOR
            and a.get("severity") == AnomalySeverity.AUTO_FIX
        ]
        if not no_price_vendors:
            return

        vendor_file = os.path.join(_PROJECT_ROOT, "backend", "weishang_vendors.json")
        if not os.path.exists(vendor_file):
            return

        try:
            with open(vendor_file, "r", encoding="utf-8") as f:
                vendors = json.load(f)

            no_price_ids = {a["vendor_id"] for a in no_price_vendors}
            updated = False
            for v in vendors:
                if v.get("id") in no_price_ids:
                    if v.get("has_price") is not False:
                        v["has_price"] = False
                        v["no_price_auto_detected"] = True
                        self._log(f"📁 {v.get('name', v.get('id'))}: 단가 없는 업체로 자동 분류 완료")
                        updated = True

            if updated:
                with open(vendor_file, "w", encoding="utf-8") as f:
                    json.dump(vendors, f, ensure_ascii=False, indent=2)
                self._log("💾 weishang_vendors.json 업데이트 완료 (단가 없는 업체 분류)")
        except Exception as e:
            self._log(f"⚠️ 업체 목록 업데이트 실패: {e}", "WARNING")

    # ──────────────────────────────────────
    # 4단계: 세션 리포트 생성
    # ──────────────────────────────────────
    def generate_report(self):
        """세션 품질 리포트를 JSON 파일로 저장합니다."""
        REPORT_DIR.mkdir(parents=True, exist_ok=True)

        session_end = datetime.datetime.now()
        duration = (session_end - self.session_start).total_seconds()

        total_products = sum(s["total_products"] for s in self.vendor_stats.values())
        total_vendors = len(self.vendor_stats)

        report = {
            "session_id": self.session_start.strftime("%Y%m%d_%H%M%S"),
            "session_start": self.session_start.isoformat(),
            "session_end": session_end.isoformat(),
            "duration_seconds": round(duration),
            "duration_human": f"{int(duration // 60)}분 {int(duration % 60)}초",
            "summary": {
                "total_vendors": total_vendors,
                "total_products": total_products,
                "anomaly_count": len(self.alerts),
                "auto_fix_count": len(self.corrections),
                "report_only_count": len([a for a in self.alerts if a["severity"] == AnomalySeverity.REPORT_ONLY]),
            },
            "vendor_stats": self.vendor_stats,
            "alerts": self.alerts,
            "corrections": self.corrections,
        }

        # 파일 저장
        filename = f"watchdog_{report['session_id']}.json"
        filepath = REPORT_DIR / filename
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            self._log(f"📄 세션 리포트 저장: {filepath}")
        except Exception as e:
            self._log(f"❌ 리포트 저장 실패: {e}", "ERROR")

        # 요약 로그 출력
        self._log("=" * 50)
        self._log(f"📊 세션 리포트 요약")
        self._log(f"   업체: {total_vendors}개 | 상품: {total_products}개 | 소요: {report['duration_human']}")
        if self.alerts:
            auto_count = len(self.corrections)
            manual_count = len(self.alerts) - auto_count
            self._log(f"   ⚠️ 이상: {len(self.alerts)}건 (자동 보정 {auto_count}건, 수동 확인 {manual_count}건)")
        else:
            self._log("   ✅ 이상 없음")
        self._log("=" * 50)

        return report

    # ──────────────────────────────────────
    # 전체 분석 실행 (원클릭)
    # ──────────────────────────────────────
    def run_full_analysis(self):
        """감지 → 보정 → 리포트 생성을 순서대로 실행합니다."""
        self._log("🔍 세션 분석 시작...")
        self.detect_anomalies()
        self.auto_correct()
        report = self.generate_report()
        self._log("✅ 세션 분석 완료")
        return report


# ──────────────────────────────────────────
# 최신 리포트 조회 유틸리티
# ──────────────────────────────────────────
def get_latest_report():
    """가장 최근 워치독 리포트를 반환합니다."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    reports = sorted(REPORT_DIR.glob("watchdog_*.json"), reverse=True)
    if not reports:
        return None
    try:
        with open(reports[0], "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def get_report_list(limit=20):
    """최근 워치독 리포트 목록을 반환합니다."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    reports = sorted(REPORT_DIR.glob("watchdog_*.json"), reverse=True)[:limit]
    result = []
    for rpath in reports:
        try:
            with open(rpath, "r", encoding="utf-8") as f:
                data = json.load(f)
                result.append({
                    "session_id": data.get("session_id"),
                    "session_start": data.get("session_start"),
                    "duration_human": data.get("duration_human"),
                    "total_vendors": data.get("summary", {}).get("total_vendors", 0),
                    "total_products": data.get("summary", {}).get("total_products", 0),
                    "anomaly_count": data.get("summary", {}).get("anomaly_count", 0),
                    "auto_fix_count": data.get("summary", {}).get("auto_fix_count", 0),
                })
        except Exception:
            pass
    return result
