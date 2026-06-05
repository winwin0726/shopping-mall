import re
import sys

with open('backend/platforms/weishang/crawler.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Define the exact text to replace based on what we saw in the view_file tool earlier
target = """                                    if current_vendor_ai_rules.get("has_price") is False:

                                        _p_final_price_input = "0"

                                    else:

                                        # 1차: 명시적 기호가 있는 단가 추출

                                        _price_matches = list(re.finditer(r'(¥|元|块|价)[ \\t]*([\\d\\.,]+)|[pPwWqQ][ \\t]*(\\d+)', _flush_pending_text))



                                        # 2차: 기호가 없다면 단독 숫자(50~999 사이)를 단가로 추정 (년도, 사이즈 제외)

                                        if not _price_matches:

                                            _price_matches = list(re.finditer(r'(?:^|\\s|[^A-Za-z0-9])(\\d{2,4})(?:$|\\s|[^A-Za-z0-9])', _flush_pending_text))



                                        for _m in _price_matches:

                                            _pn = re.findall(r'\\d+', _m.group(0))
                                            if _pn:
                                                val = int(_pn[0])
                                                
                                                # [추가됨] 사이즈/치수 오탐지 방지
                                                ctx_start = max(0, _m.start() - 15)
                                                ctx_end = min(len(_flush_pending_text), _m.end() + 15)
                                                context_str = _flush_pending_text[ctx_start:ctx_end].lower()
                                                if re.search(r'(cm|mm|g|kg|size|사이즈|가슴|길이|기장|어깨|소매|둘레|반품|허리|신발|발볼)', context_str):
                                                    continue
                                                    
                                                # [추가됨] 카테고리 기반 최소 단가 하한선 조정
                                                _cat_hint = current_vendor_ai_category or _guess_category("", _flush_pending_text) or ""
                                                min_val = 30
                                                if "악세" not in _cat_hint and "잡화" not in _cat_hint and "반지" not in _cat_hint and "목걸이" not in _cat_hint and "귀걸이" not in _cat_hint:
                                                    min_val = 50
                                                
                                                # [수정됨] '돼지' 업체의 경우 50 미만의 숫자가 단가로 쓰이는 특수성이 있으므로 하한선을 낮춤
                                                if _p_vendor_name and "돼지" in _p_vendor_name:
                                                    min_val = 10
                                                
                                                if min_val <= val <= 3000: # 도매가 범위: 하한선~3000위안
                                                    _p_final_price_input = _pn[0]
                                                    break"""

new_content = """                                    _p_final_price_input = _extract_price(_flush_pending_text, _p_vendor_name, current_vendor_ai_category, current_vendor_ai_rules)"""

if target in content:
    content = content.replace(target, new_content)
    with open('backend/platforms/weishang/crawler.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully replaced block 1")
else:
    print("Target block 1 not found. Trying regex fallback...")
    # fallback to remove block 1 using regex
    pattern = r'if current_vendor_ai_rules\.get\("has_price"\) is False:\s*_p_final_price_input = "0"\s*else:\s*# 1차: 명시적 기호가 있는 단가 추출.*?if min_val <= val <= 3000: # 도매가 범위: 하한선~3000위안\s*_p_final_price_input = _pn\[0\]\s*break'
    if re.search(pattern, content, re.DOTALL):
        content = re.sub(pattern, new_content, content, count=1, flags=re.DOTALL)
        with open('backend/platforms/weishang/crawler.py', 'w', encoding='utf-8') as f:
            f.write(content)
        print("Successfully replaced block 1 using regex")
    else:
        print("Target block 1 not found even with regex.")
