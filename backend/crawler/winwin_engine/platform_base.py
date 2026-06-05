"""
platform_base.py
────────────────
소스 크롤러 / 타겟 포스터 추상 인터페이스 정의.

모든 플랫폼 구현체(KakaoCrawler, BandCrawler, KakaoPoster, BandPoster)는
이 파일의 추상 클래스를 상속하여 구현한다.

공통 게시물 스키마 (크롤러가 반환 / 포스터가 입력받는 dict 형식)
────────────────────────────────────────────────────────────────
{
    "title":        str,   # 제목 (첫 줄 or 가공된 제목)
    "body":         str,   # 본문 HTML 또는 텍스트
    "raw_description": str,# 원본 텍스트 (가공 전)
    "product_code": str,   # 상품 코드
    "image_files":  list,  # 로컬 저장된 이미지 파일명 목록
    "price_input":  str,   # 도매가 원본 문자열
    "sale_price":   str,   # 계산된 판매가
    "created_at":   str,   # "YYYY-MM-DD HH:MM:SS"
    "source":       str,   # "kakao" | "band"
    "full_text":    str,   # 전체 원문 (이미지 대체 텍스트 포함)
}
"""

from abc import ABC, abstractmethod
from typing import Optional, Callable


class SourceCrawler(ABC):
    """
    소스 플랫폼 크롤러 추상 클래스.

    구현체: KakaoCrawler, BandCrawler
    """

    def __init__(self):
        # 로그 출력 함수 (winwin58.py의 self.log 또는 print)
        self._log_func: Optional[Callable] = None
        # 중지 플래그
        self.stop_flag: bool = False

    # ── 로그 헬퍼 ─────────────────────────────────────────────────────────
    def set_log_func(self, func: Callable):
        """UI 로그 함수를 주입한다. (선택적)"""
        self._log_func = func

    def log(self, msg: str, level: str = "INFO"):
        """로그 메시지 출력 (주입된 함수 우선, 없으면 print)."""
        try:
            if callable(self._log_func):
                self._log_func(msg, level, True)
            else:
                print(f"[{level}] {msg}")
        except Exception:
            print(f"[{level}] {msg}")

    # ── 추상 메서드 ───────────────────────────────────────────────────────
    @abstractmethod
    def login(self, user_id: str, user_pw: str, profile_name: str = "메인") -> bool:
        """
        플랫폼 로그인.

        Returns:
            True  → 로그인 성공 (또는 이미 로그인 상태)
            False → 실패
        """
        ...

    @abstractmethod
    def crawl(
        self,
        start_date,
        end_date,
        max_count: int,
        selected_cat_text: str,
        target_folder: str,
    ) -> list[dict]:
        """
        게시물 크롤링.

        Returns:
            공통 게시물 스키마 dict 의 list
        """
        ...

    @abstractmethod
    def quit(self):
        """드라이버/브라우저 종료."""
        ...

    def stop(self):
        """크롤링 중지 요청."""
        self.stop_flag = True
        self.log("크롤링 중지 요청 접수")


class TargetPoster(ABC):
    """
    타겟 플랫폼 포스터 추상 클래스.

    구현체: BandPoster, KakaoPoster
    """

    def __init__(self):
        self._log_func: Optional[Callable] = None
        self.stop_flag: bool = False

    # ── 로그 헬퍼 ─────────────────────────────────────────────────────────
    def set_log_func(self, func: Callable):
        self._log_func = func

    def log(self, msg: str, level: str = "INFO"):
        try:
            if callable(self._log_func):
                self._log_func(msg, level, True)
            else:
                print(f"[{level}] {msg}")
        except Exception:
            print(f"[{level}] {msg}")

    # ── 추상 메서드 ───────────────────────────────────────────────────────
    @abstractmethod
    def login(self, user_id: str = "", user_pw: str = "") -> bool:
        """
        플랫폼 로그인.

        Returns:
            True → 성공, False → 실패
        """
        ...

    @abstractmethod
    def post(self, item: dict) -> bool:
        """
        게시물 1건 포스팅.

        Args:
            item: 공통 게시물 스키마 dict

        Returns:
            True → 성공, False → 실패
        """
        ...

    @abstractmethod
    def quit(self):
        """드라이버/브라우저 종료."""
        ...

    def stop(self):
        """포스팅 중지 요청."""
        self.stop_flag = True
        self.log("포스팅 중지 요청 접수")
