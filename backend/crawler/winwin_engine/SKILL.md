---
name: winwin_crawler_optimization
description: Winwin 크롤러 통합 자동화 파이프라인 최적화 및 유지보수 가이드 (React + FastAPI)
---

# Winwin 크롤러 아키텍처 및 최적화 가이드 (SKILL.md)

이 문서는 `Winwin 크롤러 3.3` (React 기반 웹 UI + FastAPI 백엔드) 아키텍처에 대한 핵심 원칙과 기능 확장, 버그 수정 시 지켜야 할 일관성 있는 행동 강령을 담고 있습니다. 과거 PyQt5 기반의 모놀리식(Monolithic) 스크립트 방식은 모두 폐기되었으며, 본 문서의 지침을 최우선으로 따릅니다.

## 1. 코어 아키텍처 이해

현재 크롤러는 철저한 **모듈러(Modular) 아키텍처**로 구성되어 있습니다.

- **프론트엔드 (UI)**: `web-ui/` 폴더 하위의 **React + Vite + Tailwind CSS**
  - 주요 페이지: `KakaoPage.jsx` (단일 대시보드 역할 수행)
- **백엔드 (API & 엔진)**: `backend/` 폴더 하위의 **FastAPI** 서버 (`api_server.py`)
- **크롤링 및 포스팅 엔진**: `crawler_engine.py`가 전체 데이터 파이프라인을 관장하며, 각 플랫폼별 로직은 `platforms/` 디렉토리에 캡슐화되어 있습니다.
- **데이터베이스**: 로컬 JSON 파일 의존성을 탈피하고, ACID 트랜잭션을 보장하는 **SQLite (`database.py`)** 기반으로 전환되었습니다.
- **AI 파이프라인**: 구글 Gemini API를 활용한 실시간 번역, 카테고리 감지(Vision AI), 단가 산출 로직(`pricing_logic.py`)이 엔진에 깊게 결합되어 있습니다.

## 2. 최우선 최적화 및 코딩 원칙 (행동 강령)

### 2.1. 프론트엔드-백엔드 분리 (Decoupling)
- UI 컴포넌트(React)에서 직접 크롤링 로직이나 브라우저 제어를 시도하지 마십시오.
- UI는 오직 REST API(`fetch`)와 WebSocket을 통해서만 백엔드와 통신해야 합니다.
- 백엔드의 파이썬 엔진(`crawler_engine.py`)은 UI 블로킹 없이 별도의 `threading.Thread` 위에서 비동기적으로 동작하며, `self.notify_update()`를 통해 WebSocket으로 상태 변경을 UI에 브로드캐스트합니다.

### 2.2. 실시간 AI 번역 및 큐(Queue) 처리
- **수집 즉시 번역 (Real-time Pipeline)**: 크롤링 루프가 끝날 때까지 대기하지 않습니다. 크롤러(`weishang`, `kakao`, `band` 등)가 항목을 하나 가져오면, `CrawlerEngine` 내의 `ThreadPoolExecutor(max_workers=3)`에 즉시 서브밋(Submit)되어 병렬로 번역이 진행됩니다.
- 구글 API의 Rate Limit 방어를 위해 반드시 스레드 풀의 Worker 개수를 3~4개로 제한하여 처리해야 합니다.

### 2.3. 단가 계산 로직 (Pricing Logic) 투명성
- 상품의 카테고리, 밴더(업체명), 환율 등 다중 변수에 따른 복잡한 계산식은 `pricing_logic.py`에 격리되어 있습니다.
- 모든 가격 산출은 추적(Audit)이 가능해야 하므로, 산출 결과뿐만 아니라 `calc_log` (산출 근거 로그)를 반드시 함께 반환하여 UI(`EditModal`)에 노출시켜야 합니다.

### 2.4. 데이터베이스 및 캐싱 안정성
- 상태가 변경(수집 추가, 번역 완료, 포스팅 완료 등)될 때마다 즉시 `get_db().update_product_by_index()` 등을 호출하여 DB에 커밋해야 합니다. 프로그램 강제 종료 시에도 데이터 유실이 없어야 합니다.
- AI API 비용 절감을 위해, 번역 결과는 텍스트 해시와 카테고리를 키(Key)로 삼아 DB에 캐싱되며, 동일 원문에 대해서는 API 호출을 우회(`Cache Hit`)합니다.

### 2.5. 프롬프트 시스템 (수동 룰 + 백엔드 강제 룰)
- **절대 원칙**: UI 쪽에 복잡한 기본 템플릿(프롬프트)을 하드코딩하거나 캐싱하지 마십시오.
- 모든 고품질 번역 양식과 레이아웃(칼각)은 백엔드의 `my_style_prompt_*.txt` 파일들에 저장되어 있습니다.
- UI의 번역 지침 칸은 사용자가 일회성 예외 규칙을 적을 때만 사용하며, 백엔드 엔진이 이를 결합하여 최종 프롬프트를 생성합니다.

## 3. 대표적인 유지보수/프롬프트 예시
- "프론트엔드의 `EditModal`에서 UI가 어색해. Tailwind 클래스를 수정해서 썸네일 그리드 형태로 바꿔줘." -> `web-ui/src/pages/KakaoPage.jsx` 수정
- "새로운 도매처(weishang)의 URL 패턴이 변경되었어." -> `backend/platforms/weishang/crawler.py` 내부 정규식 및 선택자(Selector) 수정
- "남성의류 번역 시 사이즈 표기법을 바꾸고 싶어." -> `backend/my_style_prompt_남성의류.txt` 파일 수정

## 4. 로드맵 및 확장 방향
✅ **1단계**: 단일 모놀리식 ➡️ FastAPI + React 기반 서비스 아키텍처 전환 완료
✅ **2단계**: JSON 파일 ➡️ SQLite 데이터베이스 전환 완료
✅ **3단계**: 크롤링 후 일괄 번역 ➡️ 수집 즉시 백그라운드 병렬 번역(실시간 파이프라인) 완료
🔜 **4단계**: 텔레그램 봇 연동을 통한 파이프라인 완료 자동 알림 구축 (에러 발생 시에도 실시간 알림)
🔜 **5단계**: Vision AI 기반의 완전 자동 검수 시스템 (이미지 판별을 통한 불량 데이터 필터링)

---
**주의**: 이 지침을 위반하고 프론트엔드와 백엔드의 책임을 섞거나, `crawler_engine.py` 내부에 하드코딩된 대규모 프롬프트를 다시 심는 행위는 엄격히 금지됩니다.
