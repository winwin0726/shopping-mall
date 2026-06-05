import os


def detect_category_with_vision(api_key: str, image_url_or_path: str, text_hint: str = "") -> str:
    """Gemini Vision API를 활용하여 이미지 기반 카테고리를 교차 검증한다."""
    try:
        from google import genai
        from google.genai import types
        import requests

        client = genai.Client(api_key=api_key.strip())

        img_bytes = None
        if image_url_or_path.startswith("http"):
            res = requests.get(image_url_or_path, timeout=5)
            if res.status_code == 200:
                img_bytes = res.content
        elif os.path.exists(image_url_or_path):
            with open(image_url_or_path, "rb") as f:
                img_bytes = f.read()

        if not img_bytes:
            return ""

        prompt = f'''아래 패션/잡화 상품 이미지를 보고 가장 적절한 카테고리를 단 하나만 골라 대답해.
선택지: [신발, 바지, 가방, 지갑, 시계, 악세사리, 의류, 기타]
참고 텍스트: "{text_hint[:50]}"
오직 선택지에 있는 단어 하나만 대답할 것.'''

        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=[
                types.Part.from_bytes(data=img_bytes, mime_type='image/jpeg'),
                prompt
            ]
        )
        ans = response.text.strip()

        valid_cats = ["신발", "바지", "가방", "지갑", "시계", "악세사리", "의류", "기타"]
        for cat in valid_cats:
            if cat in ans:
                return cat
        return ""
    except Exception as e:
        print(f"[Vision Category Error] {e}")
        return ""
