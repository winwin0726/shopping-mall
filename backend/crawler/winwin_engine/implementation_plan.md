# Winwin Crawler 3.3 운영 품질 개선 플랜

본 기획안은 대규모 자동화 환경에서 발생할 수 있는 사고를 방지하고, 복구 가능성과 작업 가시성을 높이기 위해 4가지 핵심 우선순위 기능을 구현하는 계획입니다.

> [!IMPORTANT]
> 본 기획은 백엔드 구조(DB, 통신 방식)의 큰 변화를 수반하므로 사용자 피드백이 필수적입니다.
> 확인 후 동의하시거나 수정할 부분을 말씀해주시면 즉시 개발에 착수합니다.

## User Review Required

- 작업 큐(Job Queue) 시스템을 구축할 때 메모리(Memory)에만 저장할지, SQLite(DB)에 기록해서 껐다 켜도 재시작 가능하게 할지 결정이 필요합니다. (기본 제안: SQLite 기반 영구 저장 큐)
- 상품 중복 기준: "동일한 상품 코드(또는 URL)가 과거에 성공적으로 게시된 적이 있으면" 중복으로 처리하여 게시를 막거나 경고를 띄우는 방식이 맞는지 확인해주세요.

## Proposed Changes

---

### 1. Database Schema Extension (`backend/database.py`)

기존 SQLite 데이터베이스(`winwin.db`)에 이력 및 큐 관리를 위한 2개의 테이블을 추가합니다.

#### [MODIFY] `backend/database.py`
- `post_history` 테이블 생성
  - 컬럼: `id`, `product_code`, `platform`, `account_profile`, `status` (SUCCESS, FAIL, DRY_RUN), `error_reason`, `created_at`
- `job_queue` 테이블 생성
  - 컬럼: `id`, `task_type` (CRAWL, TRANSLATE, POST), `payload_json`, `status` (PENDING, RUNNING, COMPLETED, FAILED), `retry_count`, `error_msg`, `created_at`, `updated_at`
- 중복 감지 메서드 추가: `check_is_posted(product_code, platform)`

---

### 2. Job Queue System (`backend/queue_manager.py` 신설)

작업이 중간에 멈추거나 실패해도 전체 파이프라인이 붕괴되지 않도록 관리하는 큐 매니저를 도입합니다.

#### [NEW] `backend/queue_manager.py`
- 백그라운드 워커 스레드 생성
- DB의 `job_queue` 테이블에서 `PENDING` 상태의 작업을 가져와 순차 실행
- 에러 발생 시 `status='FAILED'` 처리 후 큐 진행은 유지 (재시도 로직 포함)
- API로 큐 상태(현재 남은 작업량, 진행 중인 작업 등)를 반환하는 기능 제공

---

### 3. Dry-run Mode & History Logging (`backend/api_server.py` 등)

실제 게시가 일어나기 전 최종 확인을 하거나, 게시 요청 시 드라이런 모드로 작동하도록 백엔드 로직을 개선합니다.

#### [MODIFY] `backend/api_server.py` & `crawler_engine.py`
- 기존 `/api/start_posting` 파라미터에 `dry_run: boolean` 추가
- 로직 수정: `dry_run == true` 일 경우 셀레니움/웹드라이버의 "글쓰기 버튼" 클릭 직전까지만 진행하고, 결과 JSON을 생성하여 `post_history`에 `DRY_RUN` 상태로 저장.
- 게시 성공/실패 시 예외를 잡아 `error_reason`과 함께 `post_history`에 DB 기록.

---

### 4. Frontend UI/UX Updates (`web-ui/src/...`)

백엔드의 개선된 기능을 프론트엔드에서 제어하고 확인할 수 있도록 화면을 구성합니다.

#### [MODIFY] `KakaoPage.jsx` (혹은 분리될 컴포넌트)
- **미리보기/드라이런 토글 버튼**: "게시 전 테스트(Dry-run) 모드" 스위치 추가
- **작업 현황판 (Job Queue Dashboard)**: 대기중, 진행중, 실패한 작업 개수를 실시간(혹은 주기적)으로 보여주는 작은 패널 추가
- **중복 경고 UI**: 이미 게시된 이력이 있는 상품에 대해 테이블 열이나 뱃지로 "⚠️ 기게시됨" 표시
- **게시 이력 버튼**: 과거 게시 성공/실패 기록을 보여주는 모달 버튼 추가

## Verification Plan

### Automated/Manual Tests
1. **DB 스키마 검증**: 재시작 시 `post_history`와 `job_queue` 테이블이 정상 생성되는지 확인
2. **드라이런 검증**: 드라이런 체크 후 게시 실행 시, 실제 네이버밴드/카카오스토리에 글이 올라가지 않으면서 성공(Dry-run) 이력이 남는지 확인
3. **중복 차단 검증**: 동일 상품 코드를 2번 게시할 때, 두 번째는 UI에서 "기게시됨" 상태가 표시되고, 설정에 따라 스킵되는지 확인
4. **작업 큐 검증**: 고의로 1개의 상품에서 에러를 유발했을 때, 다음 상품 게시는 정상적으로 큐에서 꺼내어 실행되는지 확인
