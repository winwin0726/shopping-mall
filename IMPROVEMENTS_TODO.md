# LUXAI 쇼핑몰 — 문제점 & 개선점 전수 리스트 (작은 단계별 해결용)

> 작성: 2026-06-05 · 범위: 활성 앱 코드(backend FastAPI + frontend Next.js 16). `winwin_engine`(벤더링) 제외.
> **유료 서비스 연동(실 PortOne 결제, 유료 VTON/Gemini 실 API 구축)은 범위에서 제외** — 아래 "Z. 제외" 참조.
> 각 항목은 독립적으로 처리 가능한 "작은 단계"이며, 완료 시 `[x]` 체크.

---

## A. 버그 (실제 동작이 깨지는 것 — 최우선)

- [x] **A1. `next.config.ts` 이미지 도메인 포트 불일치** — `remotePatterns`가 `localhost:8000`인데 백엔드는 **8002**. 또 폴백 이미지 호스트(`cdn-icons-png.flaticon.com`) 미등록 → `next/image`로 백엔드 업로드/폴백 이미지 로드 실패. → 포트 8002로 수정 + 필요한 호스트 추가.
- [x] **A2. datetime 'Z' 파싱 크래시 근본 방어** — 데모 1건(`hq_products` id=23)은 정규화 완료했으나, 'Z'/ISO 형식이 다시 들어오면 SQLAlchemy(파이썬 3.10)가 또 크래시. → 저장 정규화 또는 tolerant 처리로 재발 방지.
- [x] **A3. 장바구니 수량 0 업데이트 시 `HTTPException(204)` 남용**(`cart.py` update_cart_item) — 정상 삭제를 예외로 던짐. → 정상 응답/204 표준화.
- [x] **A4. `generate_ai_banner` except의 `text_response` 미바인딩 가능**(`admin.py`) — 초기 단계 에러 시 NameError로 메시지 깨짐. → 안전 처리.
- [x] **A5. JWT 토큰 만료 설정 불일치** — `config.py`는 60분, `security.py`는 7일(`60*24*7`)로 정의. 실제 사용되는 건 security.py. → 단일화.

## B. 보안

- [x] **B1. 저장형 XSS** — 상품 상세(`product/[id]/page.tsx:592`)가 `description_html`을 `dangerouslySetInnerHTML`로 무정화 렌더. 크롤러/AI/리치에디터 HTML에 스크립트 포함 가능. → DOMPurify 등 sanitize.
- [x] **B2. 파일 업로드 검증 부족**(`upload.py`) — 확장자 화이트리스트/용량 제한 없음, content-type만 신뢰. SVG/HTML 업로드→서빙 시 XSS. → 확장자·크기 검증.
- [x] **B3. 크롤러 webhook 기본 토큰 하드코딩**(`crawler.py` `LUXAI-WINWIN-TOKEN-1234`) — 미변경 시 우회 가능. → 기본값 제거/환경변수 강제.
- [x] **B4. 카카오/밴드 비밀번호 평문 저장**(`theme_config.crawlerSettings`) — → 저장 제외 또는 암호화.
- [x] **B5. JWT/시크릿 설정 이중화 + 약한 기본값** — `config.SECRET_KEY`(미사용)와 `security.JWT_SECRET_KEY`(실사용, 하드코딩 기본값) 혼재. → 단일 소스 + 기본값 강제 교체.
- [x] **B6. 노출 시크릿/세션 파일 정리** (확인 결과 `.env`/`auth_state.json` 이미 미추적, `sql_app.db`는 의도된 데모데이터 — 충족. 실제 키 로테이션은 사용자 직접) — 루트 `auth_state.json`(브라우저 세션 상태 커밋됨), `backend/.env`, `NEXTAUTH_SECRET` → git 추적 제외 + 로테이션.
- [x] **B7. 시드 관리자 2개**(`admin@example.com`, `admin@luxai.com`) 동일 비번 → 공격면. 1개로 축소/비번 분리.
- [x] **B8. 입력 검증** — 리뷰/문의 길이 제한 + 회원가입 비밀번호 최소길이(8) 검증 추가. (레이트리밋(빈도 제한)은 인프라 후속 — slowapi 등)

## C. 죽은 코드 / 정리

- [x] **C1. 이중 인증 스택 제거** — 실제로는 localStorage JWT 사용. 미사용 `next-auth`(`app/api/auth/[...nextauth]/route.ts`, `Providers.tsx` SessionProvider 등) 제거 또는 일원화.
- [x] **C2. `middleware.ts` 정리** — 주석 인코딩 깨짐(모지바케) + 빈 미들웨어(matcher: []). → 삭제 또는 재작성.
- [x] **C3. 스케줄러 가짜 타겟 URL**(`scheduler.py` `example-weishang-album.com`) — 매일 02:00 무조건 실패. → 비활성/실소스 연동.
- [x] **C4. VTON mock 잔재** (호출처 없는 `pre_generate_fitting`/`generate_hailuo_5scene_video` + 미존재 도메인 폴백 제거. 사용 중인 `extract_transparent_clothing`/`smart_layering`/`smart_fit`은 보존) — 미존재 도메인 폴백(`cdn.ai-mall.com`, `ai-worker:8080`), 하드코딩 product-id(1/2/3) 매핑, Unsplash 폴백. → 정리/주석화.
- [x] **C5. 유틸/디버그 정리** (stale `backend_error.log` + 옛경로 1회용 `fix_admin.py` 제거. `check_db.py`/`download_model.py`/`tmp/seed_pending.py`는 유용/사용자자산이라 보존) — `download_model.py` print, `fix_admin.py`/`check_db.py`/`tmp/`, `backend_error.log` 처리 판단.

## D. 일관성 / 유지보수성

- [x] **D1. 프론트 API 호출 일원화 (광범위·고가치)** (31개 파일 → `API_URL` 일원화, 중복 import 병합, 잘못된 폴백 8000/8001 제거. authFetch 전환은 점진 후속) — 35+ 파일이 raw `fetch` + 잘못된 폴백(`localhost:8000/8001`)을 직접 사용. `lib/api.ts`의 `API_URL`/`authFetch`로 통일. (파일별로 쪼개서 단계 처리)
- [x] **D2. Pydantic v1 잔재 제거** — `.dict()`→`.model_dump()`(admin 3곳), `class Config/orm_mode`→`model_config={"from_attributes":True}`.
- [x] **D3. Gemini 호출 코드 통합** (공용 `utils/gemini.py`로 3곳 통합 + 크롤러 동기호출 블로킹 해소 `run_in_executor`. 부팅/등록 검증 완료, 실제 호출은 Gemini 키 필요) — admin 배너/autofill + crawler mapping 3곳 중복 → `ai_translator`(httpx async)로 통합.
- [x] **D4. 매직 상수/URL 정리** (products 폴백이미지 상수화, vton `os.getenv("BACKEND_URL")`→`settings.BACKEND_URL`) — 폴백 이미지 URL, 기본가격(30000/39000), `os.getenv("BACKEND_URL")` vs `settings.BACKEND_URL` 혼용 단일화.
- [x] **D5. 상품 응답 필드 일관화** (목록에 sale_price/discount_rate 추가, 표시 이미지 단일 규칙 `_display_image`) — 목록은 `base_price`(할인가 무시), 다른 곳은 `sale_price`; 이미지도 `ai_fitting_image_url`/`transparent`/`images[0]` 제각각. → 표준화.

## E. 미완성 기능 (유료 무관)

- [x] **E1. 상품 리뷰 표시/조회** — "상품별 리뷰 목록" API 없음 + 상품 상세에 리뷰 미표시. (작성/내리뷰만 존재) → 공개 조회 API + 상세 UI.
- [x] **E2. 리뷰 구매검증/중복방지** — 아무나 무제한 작성 가능. → 구매자만/중복 방지(선택적).
- [x] **E3. 장바구니 담기 시 재고 검증** — 결제 때만 체크. → 담기/수량변경 시도 검증.

## F. 성능

- [x] **F1. N+1 쿼리 제거** (cart/wishlist/reviews/orders → joinedload 일괄 로드) — cart/wishlist/reviews/orders/products에서 루프마다 상품·카테고리 단건 조회. → `joinedload`/`selectinload`.
- [x] **F2. async 내 동기 blocking I/O** (크롤러 Gemini=D3에서 run_in_executor, VTON 누끼 다운로드=httpx async 전환) — `crawler.run_gemini_mapping`(urllib), `vton.extract_transparent_clothing` 이미지 다운로드(urllib)가 이벤트 루프 블로킹. → httpx async/executor.

## G. 데이터 / 마이그레이션 / 인프라

- [x] **G1. 마이그레이션 전략 통일** (main.py 흩어진 PRAGMA 3블록 → `utils/db_migrate.run_lightweight_migrations()` 단일화. 정식 alembic은 추후) — 현재 `create_all` + PRAGMA 폴백 산재. → alembic 정식화 또는 일관된 부트 마이그레이션.
- [x] **G2. 크롤러 동시성 안전화** (bool 플래그 → `threading.Lock`, wechat QR 서버GUI는 `ENABLE_WECHAT_QR_LOGIN` 옵트인) — 모듈 전역 단일 `crawler_engine`/`_is_crawler_running` 락 경합. `wechat_qr_login` 서버 GUI 구동 재설계.

## H. UX / 관리자

- [x] **H1. 관리자 통계 가짜 데이터 제거** (tenant_stats의 random 가짜매출 제거 → 실제 집계만) — `get_tenant_stats`가 매출 0일 때 랜덤 가짜값 반환(`is_demo`). → 실제 빈상태 UI.
- [x] **H2. 더미 지표 정리** (order_stats의 하드코딩 trend "up" → None) — `revenue_trend:"up"` 등 하드코딩 트렌드.
- [x] **H3. 프론트 에러/로딩 처리** (장바구니 수량변경·담기 실패 시 서버 메시지(재고부족 등) 사용자 표시. 전면 표준화는 점진 과제) — 다수 `catch {}` 무시, 로딩/실패 상태 일관화.

---

## I. 크롤러 도킹 (외부 윈윈크롤러 → 쇼핑몰 webhook) — 추가 작업

> 진단: 관리자 'AI 수집'(`scrape-platform`, 서버 내장 방식)은 다중 결함(`winwin59` 누락·`playwright`/`google-genai` 미설치·sys.path 오류·`/static` 이미지 경로)으로 사실상 비동작. → 사용자 결정에 따라 **webhook 수신 방식**을 정식 도킹으로 채택·정비.

- [x] **webhook 수신부 견고화** (`/api/crawler/webhook`)
  - Gemini 매핑 실패/키없음에도 **원본 payload 로 폴백 등록**(도킹 끊김 방지)
  - 원격 이미지 **`/uploads/crawler` 로 영구 재호스팅**(`_rehost_images`, httpx) + http URL 정규화 (기존 `/static` 깨진 링크 문제 해소)
  - **중복 전송 방지**(출처URL+제목), `kr_name` None 방지, 빈 payload 400 검증, 가격 환율×마진 폴백
  - 검증 9/9: 토큰거부·빈payload거부·키없이폴백등록·가격·이미지재호스팅·중복무시
- [ ] (참고) 서버 내장 `scrape-platform` 방식은 보류 — 필요 시 playwright+chromium 설치, `winwin59→core.pricing` 임포트 수정, sys.path/이미지 경로 수정, 웨이상 서버 로그인 필요

## Z. 범위 제외 (유료 서비스 — 요청에 따라 보류)

- 실 PortOne 결제 연동 + `payment/verify` 프론트 연동 (PG 계정/키 필요)
- 실 VTON 엔진(IDM-VTON 등)·Hailuo 영상·유료 Gemini 파이프라인 구축 (현재 mock 유지)
- httpOnly 쿠키 인증 전면 전환(대규모) — 필요 시 별도 논의
