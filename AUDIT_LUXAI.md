# LUXAI 쇼핑몰 전수조사 보고서 & 개선 체크리스트

> 작성일: 2026-06-05 · 범위: 백엔드(FastAPI) + 프론트(Next.js). `backend/crawler/winwin_engine`(234파일 벤더링 앱)은 아키텍처/리스크 수준만 다룸.
> 단계: **A(치명 보안 수정·완료)** → **B(심층 분석·완료)** → **C(본 문서/체크리스트)** → **2차 개선(체크리스트 일괄 반영·완료)**

---

## 0. 시스템 개요

| 구분 | 내용 |
|---|---|
| 백엔드 | FastAPI + SQLAlchemy, **포트 8002** (`start_servers.bat`) |
| 프론트 | Next.js 16 / React 19, 포트 3000 |
| DB | `config.DATABASE_URL`(기본 SQLite `sql_app.db`)로 단일화. 환경변수로 교체 가능 |
| 인증 | 백엔드 JWT 단일화. 어드민=role ADMIN 가드 |
| 시드 관리자 | `admin@example.com` / `admin1234` (role=ADMIN, 비번은 `SEED_ADMIN_PASSWORD` 로 오버라이드 가능) |
| AI | Gemini(번역/카피), rembg 누끼, PIL 합성 VTON. 단일 피팅·일부 흐름은 목 |

---

## 1. A단계 — 치명 보안 수정 ✅

| 항목 | 변경 파일 | 검증 |
|---|---|---|
| 어드민 API 인증·인가 게이트(`get_current_admin`+`is_active`) | `utils/deps.py`, `main.py` | 익명 401 / 회원 403 / 관리자 200 |
| 주문 `/admin/*` 4개, 크롤러 엔드포인트(webhook은 토큰) 보호 | `routers/orders.py`, `routers/crawler.py` | ✅ |
| 업로드는 "로그인 사용자"로 보호(고객 VTON 유지) | `main.py`, `routers/upload.py` | 익명 401 / 회원 통과 |
| 로그인 시 비활성 계정 차단 | `routers/auth.py` | ✅ |
| 공용 `authFetch`+단일 `API_URL`, 13개 컴포넌트 연동 | `frontend/src/lib/api.ts` 외 | tsc 0 에러 |
| 어드민 페이지 실제 가드(next-auth 제거→JWT+role) | `app/admin/page.tsx` | ✅ |
| next-auth 러버스탬프 제거→백엔드 검증 | `app/api/auth/[...nextauth]/route.ts` | ✅ |
| 결제 금액 서버 재계산(위변조 방지) | `routers/orders.py` | 위조 1원→198,000원 |

> **운영 변경점**: 어드민은 role=ADMIN 계정으로 `/login` 로그인 후 `/admin` 접근.

---

## 2. B단계 — 심층 분석 요약
- **결제**: 프론트가 시뮬레이션(`@portone` 미사용), `payment/verify` 미호출, 재고/쿠폰/적립 미연동.
- **VTON**: 단일 피팅은 스톡사진 목, 캐시 무한증가, 누끼 실패 시 원본 저장.
- **크롤러**: `ai_translator`가 `.env` 미로딩+`kr_name` 하드코딩으로 고장, 스케줄러 더미주입, 수집이미지 `/static` 404.
- **winwin_engine**: PyQt5 데스크톱 앱을 모킹 브리지로 구동, 번들 비밀파일, 격리 권장.

---

## 3. 개선 체크리스트

### ✅ 2차 개선에서 반영 완료
- [x] 결제 시 **재고 차감 + 품절 검증**(409) — `orders.py` create_order/checkout_cart
- [x] 결제 **dummy 자동승인 제거 → `PAYMENTS_DEV_MODE` 명시화**(운영 fail-closed) — `orders.py`,`config.py`
- [x] `ai_translator` 정상화(`settings.GEMINI_API_KEY`+실제 파싱, 하드코딩 제거) — `crawler/ai_translator.py`
- [x] 스케줄러 더미상품 주입 비활성 — `scheduler.py`
- [x] 포트 하드코딩 정리(`localhost:8001`→`settings.BACKEND_URL`) — `admin.py`,`upload.py`
- [x] DB 설정 단일화(`config.DATABASE_URL`↔`database.py`) + 빈 `fastapi_shop.db` 제거
- [x] `GET /api/auth/me` 멱등화 + `POST /me/visit-reward` 분리 — `auth.py`,`useAuth.ts`
- [x] 빌드차단 타입에러 수정(`ProductsTab.tsx:899` `size_stock_config`)
- [x] 디버그 `print` 제거(`auth.py`), 목 엔드포인트 제거(`products.py`)
- [x] `main.py` 중복 import 정리 + CORS 환경변수화(`CORS_ORIGINS`)
- [x] `_vton_cache` 상한(FIFO) + 누끼 실패 시 원본 저장 금지(`None` 반환) — `vton.py`
- [x] throwaway 스크립트(`tmp_*.py`) + 빈 DB 정리
- [x] 비밀키 **부분 env화**: `JWT_SECRET_KEY`, `SEED_ADMIN_PASSWORD` 환경변수 오버라이드(기본값 유지)

### ✅ 3차 개선 (이번 세션 반영 · 스모크 10/10 + 프론트 tsc 0에러)
- [x] **`requirements.txt` 완성(설치 가능화)** — 실제 코드가 쓰는데 누락됐던 `httpx`,`Pillow`,`beautifulsoup4`,`selenium`,`webdriver-manager`,`email-validator` 추가, 잘못된 `cors` 제거. 누끼(`rembg`/`onnxruntime`)는 lazy 로딩이라 주석 안내. → 신규 venv 설치 후 백엔드 부팅·로그인·상품·인증 스모크 확인.
- [x] **쿠폰 사용 / 적립금 차감을 체크아웃에 반영** — `GET /api/auth/me/coupons`(내 쿠폰 목록) 신설, `orders.checkout/cart`·`orders`에 `coupon_id`·`used_points` 처리(서버측 **소유/미사용/잔액 검증** → 할인 적용 → 쿠폰 사용처리 + 적립금 차감). `Order`에 `discount_amount`/`used_points` 컬럼 + PRAGMA 폴백 마이그레이션. `CheckoutModal`에 쿠폰 선택·적립금 입력 UI + 할인내역/최종금액 표시. (`orders.py`,`auth.py`,`schemas.py`,`models.py`,`main.py`,`CheckoutModal.tsx`)
- [x] **게스트 허용 인증 의존성** `get_current_user_optional` 추가 — 비로그인 buy-now는 유지하되, 로그인 시 쿠폰/적립금 사용 + 주문 소유자를 토큰 기준으로 안전 매핑. (`utils/deps.py`)
- [x] **데이터 버그픽스** — `hq_products` id=23 의 `created_at='2026-06-02T12:00:00Z'`(ISO `Z` 접미사)가 Python 3.10 SQLAlchemy 파싱 실패를 일으켜 **어드민 상품 API·해당 상품 체크아웃을 500 크래시**시키던 문제. DB datetime 값 정규화로 해결(코드 삽입 경로 없음 = 데모데이터 1건).

### 🔴 남은 치명 (외부 키/제품 결정 필요)
- [ ] **실제 PortOne 결제 연동** + 프론트 `payment/verify` 호출(현재는 `PAYMENTS_DEV_MODE=True`로 데모 통과) — PG 계정·키 필요
- [ ] **비밀키 실제 로테이션·분리**: 노출된 `backend/.env`(Gemini), `NEXTAUTH_SECRET`, 루트 `auth_state.json` — 사용자 직접 조치
- [x] ~~쿠폰 사용/적립금 차감을 체크아웃에 반영~~ → **3차 개선에서 완료**(위 참조)
- [ ] 크롤러 카카오/밴드 비밀번호 평문 저장 암호화 — winwin 연계

### 🟠 남은 주요 (구조 변경)
- [ ] 마이그레이션 전략 통일(alembic vs `create_all`+PRAGMA) — DB 마이그레이션 리스크로 보류
- [ ] 크롤러 전역 락(`_is_crawler_running`) 안전화, `wechat_qr_login` 서버 GUI 구동 재설계
- [ ] winwin 수집 이미지 `/static` 경로 정합(또는 `/uploads` 이동) — winwin 격리와 연계

### 🟡 남은 품질
- [ ] JWT localStorage→httpOnly 쿠키 전환(XSS 완화) — 대규모 인증 변경
- [ ] 정식 테스트 스위트 도입(현재는 변경분 스모크 검증만 수행)
- [ ] `winwin_engine` 별도 서비스로 격리

---

## 4. 비고
- 1차(A)·2차 개선 항목은 코드 반영 후 백엔드 스모크 + 프론트 tsc(0 에러)로 검증 완료.
- `fix_admin.py`,`check_db.py`는 운영 유틸 가능성이 있어 삭제하지 않고 보존(필요 시 사용자 판단으로 정리).
- 세션 메모리 `luxai-mall-audit-and-security`에 핵심 진행상황 기록됨.
