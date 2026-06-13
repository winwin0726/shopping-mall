import json
import httpx
import logging
import os
import sys
import asyncio
import urllib.request
import re
from google.oauth2 import service_account
import google.auth.transport.requests

logger = logging.getLogger(__name__)

# 윈윈 엔진 경로 수동 주입
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENGINE_BACKEND_DIR = os.path.join(BASE_DIR, "winwin_engine", "backend")
if ENGINE_BACKEND_DIR not in sys.path:
    sys.path.insert(0, ENGINE_BACKEND_DIR)

class AITranslatorPipeline:
    def __init__(self):
        # Vertex AI GCP 마스터 키 경로 및 리소스 설정
        self.creds_path = r"D:\에이전트그룹\crawlerwin(마스터키 제미나이 VERTEX AI API키).json"
        self.project_id = "crawlerwin"
        self.location = "us-central1"
        self.model_name = "gemini-2.5-flash"
        self.model_endpoint = (
            f"https://{self.location}-aiplatform.googleapis.com/v1/projects/{self.project_id}/locations/{self.location}/publishers/google/models/{self.model_name}:generateContent"
        )

    def _get_gcp_access_token(self) -> str:
        if not os.path.exists(self.creds_path):
            logger.error(f"GCP service account key file not found at: {self.creds_path}")
            return ""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                self.creds_path,
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            auth_req = google.auth.transport.requests.Request()
            credentials.refresh(auth_req)
            return credentials.token
        except Exception as e:
            logger.error(f"Failed to acquire GCP OAuth2 token: {str(e)}", exc_info=True)
            return ""

    def _get_naver_exchange_rate(self) -> float:
        """네이버 실시간 환율 수집 유틸 (실패 시 200.0)"""
        try:
            url = "https://m.search.naver.com/p/csearch/content/qapirender.nhn?key=calculator&pkid=141&q=%ED%99%98%EC%9C%A8&where=m&u1=keb&u6=standardUnit&u7=0&u3=CNY&u4=KRW&u8=down&u2=1"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            resp = urllib.request.urlopen(req, timeout=5).read().decode('utf-8')
            data = json.loads(resp)
            val_str = str(data['country'][1]['value']).replace(',', '')
            rate = float(val_str)
            logger.info(f"Successfully fetched Naver exchange rate: {rate}")
            return rate
        except Exception as e:
            logger.warning(f"Failed to fetch Naver exchange rate, falling back to 200.0: {e}")
            return 200.0

    async def translate_product_info(
        self, 
        cn_title: str, 
        cn_desc: str, 
        wholesale_price_krw: int = 0,
        category_name: str = "의류",
        vendor_name: str = "Unknown",
        original_source_url: str = ""
    ) -> dict:
        """
        GCP 마스터 서비스 계정 키를 기반으로 Vertex AI Gemini 모델을 호출하여 
        윈윈크롤러 3.3의 업데이터 번역 지침과 출력 양식에 맞추어 번역을 실행하고
        파이썬 연산기반의 ㄷㄱ 및 상품코드를 조립하여 반환한다.
        """
        fallback = {
            "kr_name": (f"[수집] {cn_title}".strip())[:50],
            "kr_description": cn_desc or "",
            "description_html": f"<div class='product-description'>{cn_desc or ''}</div>",
            "product_code": "",
            "sale_price": wholesale_price_krw
        }

        # 1. ㄷㄱ 및 상품코드 연산용 데이터 추출 및 임포트
        import pricing_logic
        import weishang_price

        # 실시간 네이버 기준 환율 + 5 적용
        naver_fx = self._get_naver_exchange_rate()
        fx = naver_fx + 5.0

        # 업체명 추출 (original_source_url이 윈윈 포맷이면 파싱)
        if original_source_url and original_source_url.startswith("winwin://"):
            m = re.match(r"winwin://([^/]+)", original_source_url)
            if m:
                extracted_vendor = m.group(1).split("/")[0].strip()
                if extracted_vendor and extracted_vendor != "Unknown":
                    vendor_name = extracted_vendor

        # 위안화 원가(cost) 추출
        text_for_price = f"{cn_title}\n{cn_desc}\n{original_source_url}"
        extracted_price, conf, reason = weishang_price.smart_extract_price(text_for_price)
        try:
            cost = int(float(extracted_price)) if extracted_price and extracted_price != "-" else 0
        except Exception:
            cost = 0

        # 위안화 단가 미추출 시 원화 도매원가 기준 역산 폴백
        if cost == 0 and wholesale_price_krw > 0:
            cost = int(wholesale_price_krw / fx)
            logger.info(f"Falling back to cost calculation via wholesale_price_krw: {cost} Yuan")

        # 2. ㄷㄱ 및 상품코드 정밀 계산
        product_code, computed_dg_won, dg_display_str, calc_log = await asyncio.to_thread(
            pricing_logic.generate_product_code_and_price,
            vendor_name, cost, category_name, cn_title, cn_desc, fx
        )

        token = self._get_gcp_access_token()
        if not token:
            logger.warning("GCP access token not set. Returning passthrough translation.")
            return fallback

        # 3. 윈윈 3.3 스타일 공통 번역 지침서 로드
        style_prompt = ""
        style_prompt_path = os.path.join(ENGINE_BACKEND_DIR, "my_style_prompt_공통.txt")
        if os.path.exists(style_prompt_path):
            try:
                with open(style_prompt_path, "r", encoding="utf-8") as f:
                    style_prompt = f.read().strip()
            except Exception as e:
                logger.warning(f"Failed to read my_style_prompt_공통.txt: {e}")

        # 4. Gemini 프롬프트 작성
        prompt = (
            "당신은 한국의 고급 의류/잡화 쇼핑몰 MD이자 윈윈크롤러 전용 업데이터입니다.\n"
            "제공된 중국어 패션 상품 정보를 지침에 맞춰 자연스러운 한국어로 정제하세요.\n\n"
            "🚨 [중요 번역 지침]\n"
            "- 중국어 한자는 100% 완벽하게 한글로 변환하여 출력하세요 (한자 잔존 절대 금지).\n"
            "- 제목에 '[ 브랜드명 ]' 등 대괄호 태그는 금지합니다. 자연스럽게 '브랜드명 상품명' 포맷으로 만드세요.\n"
            "- '이탈리아' 단어는 절대 금지 ➡️ 무조건 '이태리'로 치환하여 작성하세요.\n"
            "- '정품' 단어는 절대 금지 ➡️ 무조건 '정규품싱크'로 치환하여 작성하세요.\n"
            "- '복각' 단어는 절대 금지 ➡️ 무조건 '재현'으로 치환하여 작성하세요.\n"
            "- '러닝화' 단어는 절대 금지 ➡️ 무조건 '런닝화' 혹은 '스니커즈'로 치환하여 작성하세요.\n"
            "- 잘 나온 제품, 잘 된 편, 느낌, 무드, 분위기, 실루엣, 소장가치 높은 등의 흐릿하고 과장된 소매식 문구는 절대 금지합니다.\n"
            "- 상품 설명(description_lines)은 미사여구 없이 원단, 로고, 마감, 라벨 등 실물 사양 위주로 간결하게 2~3줄 이내의 짧은 리스트로 리턴하세요.\n"
            "- 컬러와 사이즈는 한글로 자연스럽게 번역하세요.\n"
            "- 사이즈 권장 목록은 예시: ['S ▶ 남성 95 추천', 'M ▶ 남성 100 추천'] 형태로 카테고리에 맞추어 한글로 생성하세요.\n\n"
            f"[사장님 고유 문체 지침]\n{style_prompt}\n\n"
            f"중국어 상품명: {cn_title}\n"
            f"중국어 상품설명: {cn_desc}\n"
            f"카테고리: {category_name}"
        )

        response_schema = {
            "type": "OBJECT",
            "properties": {
                "kr_name": {"type": "STRING", "description": "브랜드명 + 한글 상품명 (예: '프라다 바람막이 후드 자켓'). 50자 이내."},
                "description_lines": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "원단/마감 사양 정보 위주의 간결한 2~3개 설명 문장 배열. 절대 3개 문장을 넘지 말 것."},
                "colors": {"type": "STRING", "description": "한글 컬러명 목록 (예: '블랙 / 네이비')"},
                "sizes": {"type": "STRING", "description": "한글/숫자 사이즈 목록 (예: 'S / M / L' 또는 '230 ~ 280')"},
                "size_recommendations": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "구체적인 한국 권장 사이즈 목록 (예: ['S ▶ 남성 95 추천', 'M ▶ 남성 100 추천'])"}
            },
            "required": ["kr_name", "description_lines", "colors", "sizes", "size_recommendations"]
        }

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "maxOutputTokens": 8192,
                "temperature": 0.2,
                "responseMimeType": "application/json",
                "responseSchema": response_schema
            }
        }
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                response = await client.post(
                    self.model_endpoint, json=payload, headers=headers
                )
                response.raise_for_status()
                data = response.json()

                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                # 마크다운 코드펜스 제거
                if text.startswith("```"):
                    text = "\n".join(
                        ln for ln in text.splitlines() if not ln.strip().startswith("```")
                    ).strip()

                parsed = json.loads(text)
                
                # AI 번역 결과물 추출
                kr_name = (parsed.get("kr_name") or fallback["kr_name"]).strip()[:50]
                description_lines = parsed.get("description_lines") or [cn_desc]
                colors = parsed.get("colors") or "상세참조"
                sizes = parsed.get("sizes") or "Free"
                size_recommendations = parsed.get("size_recommendations") or []

                # 제목 브랜드 중복 정규화 및 보정
                try:
                    from pricing_logic import extract_brand_from_text
                    d_brand = extract_brand_from_text(cn_title + "\n" + cn_desc, parsed.get("kr_name", ""))
                    if d_brand:
                        _t_clean = kr_name
                        # 괄호 및 특수문자 제거
                        _t_clean = re.sub(r'[\[\]\(\)\{\}\<\>【】]', ' ', _t_clean)
                        _t_clean = re.sub(r'\s+', ' ', _t_clean).strip()
                        
                        # 중복 매핑 방지 거름망
                        _brand_aliases_lower = [d_brand.lower(), "샤넬", "루이비통", "구찌", "디올", "에르메스", "셀린느", "프라다", "생로랑", "보테가베네타", "펜디", "버버리", "미우미우", "발렌시아가", "로에베", "고야드", "톰브라운", "스톤아일랜드", "몽클레어", "크롬하츠"]
                        for alias in _brand_aliases_lower:
                            _t_clean = re.sub(r'^' + re.escape(alias) + r'\s*', '', _t_clean, flags=re.IGNORECASE)
                        
                        # 최종 강제 포맷 "브랜드명 상품명"
                        kr_name = f"{d_brand} {_t_clean.strip()}".strip()[:50]
                except Exception as ex:
                    logger.warning(f"Brand normalization failed: {ex}")

                # 5. 윈윈크롤러 3.3 기본 출력 형식(코드블록 템플릿) 조립
                lines = []
                lines.append(f"{kr_name}")
                lines.append("ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ")
                lines.append("")
                for d_line in description_lines:
                    # '✔ ' 기호가 없는 경우 자동으로 추가
                    clean_line = d_line.strip().lstrip("✔").strip()
                    lines.append(f"✔ {clean_line}")
                lines.append("")
                lines.append("ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ")
                lines.append(f"✔ 컬러 : {colors}")
                lines.append("")
                
                # 카테고리가 신발(mm단위)인 경우와 의류인 경우 분기 대응
                cat_lower = category_name.lower()
                is_shoes = any(k in cat_lower for k in ["신발", "슬리퍼", "샌들", "스니커즈", "부츠", "로퍼", "뮬", "구두", "운동화"])
                
                lines.append(f"✔ 사이즈 : {sizes}")
                for rec in size_recommendations:
                    lines.append(f"  {rec}")
                
                lines.append("ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ")
                # 배송 문구 가이드 준수
                is_bag = any(k in cat_lower for k in ["가방", "백"])
                if is_bag:
                    lines.append("✔ 특송 : 입고 후 2 ~ 3일 (100%통관)")
                else:
                    lines.append("✔ 2박특송 : 입고 후 2 ~ 3일")
                    lines.append("   (개인통관부호 필수)")
                lines.append("")
                lines.append(f"{product_code}")
                lines.append(f"ㄷㄱ {dg_display_str}")

                formatted_desc = "\n".join(lines)
                desc_html_content = formatted_desc.replace('\n', '<br>')
                formatted_html = f"<div class='product-description'>{desc_html_content}</div>"

                logger.info("WinwinCrawler 3.3 formatted translation successful.")
                return {
                    "kr_name": kr_name,
                    "kr_description": formatted_desc,
                    "description_html": formatted_html,
                    "product_code": product_code,
                    "sale_price": computed_dg_won
                }

        except Exception as e:
            logger.error(f"AI Translation failed: {e}")
            return fallback
