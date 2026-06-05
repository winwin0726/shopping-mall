import os
import json
import logging
from google import genai
from google.genai import types

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("StyleProfiler")

class StyleProfiler:
    def __init__(
        self,
        category="공통",
        data_file=None,
        output_file=None,
        source_label="카카오스토리",
        sample_limit=1000,
        max_context_chars=180000,
        api_key=None,
    ):
        self.category = category
        self.source_label = source_label
        self.sample_limit = sample_limit
        self.max_context_chars = max_context_chars
        self.data_file = data_file or f"user_post_history_{category}.json"
        self.output_file = output_file or f"my_style_prompt_{category}.txt"
        
        # Winwin Crawler의 환경변수에서 API 키 로드
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            # .env 파일에서 수동으로 파싱 시도
            env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
            if os.path.exists(env_path):
                with open(env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("GEMINI_API_KEY="):
                            self.api_key = line.split("=", 1)[1].strip()
                            break
            
            if not self.api_key:
                logger.warning("GEMINI_API_KEY 환경변수가 설정되지 않았거나 .env 파일에 키가 없습니다.")
            
    def generate_style_profile(self):
        """수집된 JSON 데이터를 기반으로 사용자의 말투, 기호, 톤앤매너 추출"""
        logger.info(f"🧠 AI 스타일 프로파일러 가동 시작... (분석 데이터: {self.data_file})")
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_path = os.path.join(base_dir, self.data_file)
        out_path = os.path.join(base_dir, self.output_file)
        
        if not os.path.exists(data_path):
            error_msg = f"❌ 데이터 파일이 없습니다. (사이드 창에서 브라우저가 완전히 떴을 때 확인을 누르셨나요?) [{data_path}]"
            logger.error(error_msg)
            return False, error_msg
            
        with open(data_path, 'r', encoding='utf-8') as f:
            posts = json.load(f)
            
        if not posts:
            error_msg = "❌ 데이터 파일이 비어 있습니다. 해당 카카오스토리 채널에 게시물이 없거나 크롤링에 실패했습니다."
            logger.error(error_msg)
            return False, error_msg
            
        # 프롬프트에 주입할 컨텍스트 구성
        sample_posts = posts[:self.sample_limit]
        context_text = ""
        for i, post in enumerate(sample_posts):
            content = str(post.get("content", "")).strip()
            if not content:
                continue
            title = str(post.get("title", "")).strip()
            product_code = str(post.get("product_code", "")).strip()
            sale_price = str(post.get("sale_price", "")).strip()
            image_count = post.get("image_count", "")
            meta = []
            if title:
                meta.append(f"제목={title}")
            if product_code:
                meta.append(f"상품코드={product_code}")
            if sale_price:
                meta.append(f"판매가={sale_price}")
            if image_count != "":
                meta.append(f"사진수={image_count}")
            meta_text = " | ".join(meta)
            context_text += f"\n--- [포스팅 {i+1}] {meta_text} ---\n{content}\n"
            if len(context_text) >= self.max_context_chars:
                context_text = context_text[:self.max_context_chars]
                break
            
        logger.info(f"  📊 총 {len(sample_posts)}개의 과거 포스팅 텍스트 분석 중...")
        
        client = genai.Client(api_key=self.api_key)
        
        system_instruction = f"""당신은 텍스트 스타일과 운영 규칙을 역설계하는 최고 수준의 쇼핑몰 포스팅 프로파일러입니다.
제공되는 [과거 포스팅 데이터]는 사용자가 실제로 {self.source_label}에 올려온 상품 포스팅입니다.
당신의 임무는 이 데이터를 분석하여, 앞으로 AI가 중국어 상품 원문을 한국어 판매글로 만들 때 **'사용자가 직접 업데이트한 글처럼'** 일관되게 나오도록 하는 "글쓰기 기준서(Prompt Template)"를 작성하는 것입니다.

출력물은 다른 군더더기 없이 오직 '스타일 지침서' 내용만 작성해야 합니다.

[분석 포인트]
1. 톤앤매너: 친근한 말투인지, 딱딱하고 시크한 B2B 말투인지? 존댓말/반말 여부.
2. 자주 쓰는 기호: 글머리 기호(✔, ▶, -, ㅡ, ✨, 💡 등)를 어떤 위치에 어떻게 쓰는지?
3. 줄바꿈 및 여백: 문장과 문장 사이, 구획을 나눌 때 줄바꿈을 얼마나 길게 하는지, ㅡㅡㅡ 같은 구분선을 쓰는지?
4. 순서 패턴: 제목 -> 특징 -> 사이즈 -> 배송정보 -> 가격 등의 순서 규칙 파악.
5. 카테고리별 차이: 남성의류/여성의류/신발/가방/지갑/시계/잡화에서 제목, 사이즈, 소재, 배송 문구가 어떻게 달라지는지?
6. 가격/코드 규칙: 상품코드와 ㄷㄱ가 본문 하단에서 어떤 순서와 형태로 붙는지 분석하되, 새 글 작성 AI가 직접 가격/코드를 계산하지 않도록 분리 규칙을 명확히 적을 것.
7. 금칙어/특이사항: 중국 원문 가격(P150, ¥150, 单价 등), 업체 내부 표현, 불필요한 원문을 어떻게 걸러내고 있는지?
8. 일괄 생성 기준: 여러 업체/여러 카테고리라도 거의 같은 양식으로 나오게 만드는 공통 골격과 예외 규칙을 정리할 것.

[출력 형식]
반드시 아래의 구조로 지침서를 작성하세요:
■ 작성 톤앤매너: (여기에 분석결과 명시)
■ 기호 및 구분선 규칙: (여기에 분석결과 명시)
■ 상세 구조(레이아웃): (여기에 분석결과 명시)
■ 카테고리별 양식 차이: (카테고리별 제목/사이즈/소재/배송 차이 명시)
■ 업체코드/단가/ㄷㄱ 처리 규칙: (AI가 직접 생성하지 말고 프로그램 계산값을 하단에 붙이도록 명시)
■ 일괄 생성 기준: (모든 상품이 거의 같은 형식으로 나오기 위한 고정 골격)
■ 절대 금지 사항: (여기에 분석결과 명시)
"""

        try:
            response = client.models.generate_content(
                model='gemini-2.5-pro',
                contents=f"[과거 포스팅 데이터]\n{context_text}",
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2, # 일관된 분석을 위해 낮게 설정
                )
            )
            
            style_prompt = response.text
            
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(style_prompt)
                
            logger.info(f"  🎉 사장님의 뇌구조(스타일) 복사 완료! 프롬프트 템플릿 생성됨: [{out_path}]")
            return True, "성공"
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"  ❌ AI 프로파일링 중 오류 발생: {error_msg}")
            return False, error_msg

if __name__ == "__main__":
    profiler = StyleProfiler()
    profiler.generate_style_profile()
