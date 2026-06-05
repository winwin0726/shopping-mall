# LUXAI 쇼핑몰 통합 패키지 종합 가이드 및 개발 이력서

이 문서는 LUXAI 쇼핑몰 프로젝트(FastAPI Backend + Next.js Frontend)를 한국 PC 등으로 이관하여 즉시 개발 및 운영 작업을 개시할 수 있도록, 지금까지의 개발 및 고도화 내역, 그리고 서버 기동 방법을 총망라하여 정리한 종합 가이드입니다.

---

## 1. 프로젝트 주요 고도화 및 패치 내역

### 1) AI 피팅룸 3D 마네킹 연동 및 핏 보정
- **리소스 탑재:** 남성용(man_base.png) 및 여성용(woman_base.png) 투명 3D 마네킹 템플릿을 생성하여 `frontend/public/mockups/`에 영구 배치 완료.
- **성별 인식 기반 자동 핏 매핑 (vton.py & SmartFittingStudio.tsx):**
  - DB의 카테고리명을 판별하여 아바타 성별을 자동 스위칭합니다.
  - 남녀 신장/어깨 차이에 따른 상하의 배율(Ratio) 및 위치 오프셋(Y-Offset) 물리 수식을 적용하여 왜곡 없는 자연스러운 착용 핏을 구현했습니다.
  - 신발/가방의 bottom absolute 레이아웃 좌표도 성별에 맞게 세분화했습니다.

### 2) AI 배경 제거(누끼) 사전 생성 (Pre-generation) 파이프라인
- **비용/속도 $0화 완성:** 사용자가 피팅할 때마다 실시간 AI rembg 연산을 수행하던 기존의 10초 딜레이 및 GPU 리소스 소모 오버헤드를 완전히 걷어냈습니다.
- **선행 가공 트리거 연동:**
  - **수동 상품 등록/수정 시:** 어드민 API(`admin.py`의 `create_product` 및 `update_product`)를 통해 백그라운드 태스크 등록.
  - **크롤러 스마트 수집 시:** 스마트 수집 API(`crawler.py`의 `start_crawler`) 및 웹훅 API(`crawler_webhook`)를 통해 등록 즉시 백그라운드 누끼 생성 작동.
- **Windows asyncio 환경 호환성 핫픽스:**
  - 윈도우 환경에서 비동기 프로세스(`create_subprocess_exec`) 구동 시 발생하는 `NotImplementedError` 한계를 극복하기 위해, 백그라운드 스레드 풀 위에서 `subprocess.run`으로 rembg CLI를 안전하게 위임 기동(`loop.run_in_executor`)하도록 설계했습니다.
  - 이로 인해 한글 경로(`에이전트그룹`, `쇼핑몰`) 특유의 인코딩 및 따옴표 해석 오류가 원천 해결되었습니다.

### 3) 스마트 URL 일괄 크롤러 복구 및 이식
- **일괄 백그라운드 수집화:** 기존 동기식 단일 상품 폼 대입 방식에서, 여러 URL을 입력받아 백그라운드 스레드에서 순차 스캔하여 직접 APPROVED(승인) 상품으로 등록하는 기존 URL 수집 방식으로 완벽 이식했습니다.
- **수집 가공 자동화:** 수집되는 즉시 Gemini 2.5 Flash를 이용해 자연스러운 한국어로 정제하고, 어드민에 세팅된 환율 및 마진율 공식에 따라 원화 판매가를 자동 산출하며, 본문 내 사이즈 규격을 파싱하여 재고 수량을 `size_stock_config`에 99개씩 자동 탑재합니다.

---

## 2. 프로젝트 디렉토리 구조

```text
쇼핑몰/
├── backend/                  # FastAPI 백엔드 서버 폴더
│   ├── ai_engine/            # VTON 및 AI 누끼 처리 엔진 (models 폴더 내 u2net.onnx 빌드 완료)
│   ├── crawler/              # 윈윈크롤러3 통합 엔진 및 어댑터 모듈
│   ├── routers/              # API 라우터 (admin, crawler, auth, cart 등)
│   ├── uploads/              # 수집/VTON 이미지 정적 적재 폴더 (transparent 등)
│   ├── .env                  # 백엔드 환경변수 (Gemini API Key 탑재)
│   └── sql_app.db            # SQLite 데이터베이스 (칫솔 등 수집 완료 데이터 포함)
├── frontend/                 # Next.js 프론트엔드 서버 폴더
│   ├── public/               # 마네킹 핏 원본 및 정적 파일
│   └── src/                  # Next.js 소스 코드 (SmartFittingStudio.tsx 등)
├── start_servers.bat         # 프론트/백엔드 동시 가동 스크립트 (Windows용)
└── README_TOTAL_PATCH.md     # 본 가이드 문서
```

---

## 3. 이관 후 초기 기동 방법 (가이드)

한국 PC로 본 패키지를 옮긴 후, 아래 단계에 따라 의존성을 새로 빌드하고 서버를 기동해 주세요. (가상환경 venv 및 node_modules는 용량 최적화를 위해 압축 대상에서 제외되었습니다.)

### 1단계: 프론트엔드 의존성 빌드
```bash
cd frontend
npm install
```

### 2단계: 백엔드 가상환경 구축 및 라이브러리 설치
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```
*   *참고:* 백엔드 기동에 필요한 U2Net 모델 파일(`u2net.onnx`, 176MB)은 이미 `backend/ai_engine/models/` 경로에 빌드되어 있으므로, 추가적인 모델 다운로드 대기 없이 즉시 로컬 누끼 연산이 가능합니다.

### 3단계: 쇼핑몰 서버 동시 가동
- 루트 폴더(`쇼핑몰/`)에 배치된 `start_servers.bat` 파일을 실행합니다.
- 자동으로 백엔드(8001 포트)와 프론트엔드(3000 포트)가 기동됩니다.
  - **쇼핑몰 메인:** `http://localhost:3000`
  - **어드민 대시보드:** `http://localhost:3000/admin`
  - **백엔드 Swagger API Docs:** `http://localhost:8001/docs`

---

## 4. 데이터베이스 및 최종 상태 검증 증명
- 본 패키지에 동봉된 데이터베이스(`sql_app.db`)는 네이버 칫솔 등 AI 일괄 수집 테스트가 완료된 실제 데이터를 온전히 포함하고 있습니다.
- DB 내 수집 상품의 `transparent_item_image_url` 필드가 로컬 누끼 이미지 경로(`http://localhost:8000/uploads/transparent/item_xxxx.png`)로 채워져 있어, 피팅룸에서 즉시 0초 로딩 피팅이 가동됩니다.
