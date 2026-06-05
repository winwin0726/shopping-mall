"""Inject AI 업체분석 (vendor rules) into api_server.py translate_manual"""
import os
import re

path = r'd:\안티그래비티\winwin크롤러2\backend\api_server.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# The missing block
vendor_logic = """
        profile_rule_text = ""
        if req.vendor_name:
            import json
            import os
            from backend.utils import _PROJECT_ROOT, _normalize_vendor_key
            vendor_file = os.path.join(_PROJECT_ROOT, "weishang_vendors.json")
            if os.path.exists(vendor_file):
                try:
                    with open(vendor_file, "r", encoding="utf-8") as f:
                        vlist = json.load(f)
                        matched_vendor = None
                        for v in vlist:
                            if v.get("name") == req.vendor_name:
                                matched_vendor = v
                                break
                        if matched_vendor:
                            profile_parts = []
                            for label, key in [
                                ("업체 번역/문체 규칙", "profile_rules"),
                                ("상품 글 구성", "post_structure"),
                                ("묶음/분할 규칙", "grouping_rules"),
                                ("동일상품 매칭 규칙", "matching_rules"),
                                ("가격 표기/계산 패턴", "pricing_pattern"),
                                ("추천 판매 문체", "recommended_style"),
                            ]:
                                value = matched_vendor.get(key)
                                if value:
                                    profile_parts.append(f"- {label}: {value}")
                            if profile_parts:
                                profile_rule_text = "\\n\\n🚨 [해당 업체 특화 AI 번역/상품화 규칙 - 최우선 참고]\\n" + "\\n".join(profile_parts) + "\\n"
                except Exception as e:
                    print(f"Vendor profile load error: {e}")
"""

# Find where to inject
# Right before `custom_section = ""`
target = '        custom_section = ""\n        if req.custom_prompt and req.custom_prompt.strip():'

if "profile_rule_text =" not in content and target in content:
    content = content.replace(target, vendor_logic + "\n" + target)

# Update the prompt string
old_prompt_line = '이번에는 카카오스토리용(kakao_text), 네이버 밴드용(band_text), 인스타그램용(insta_text) 3가지 버전으로 각각 작성해야 해.{style_section}{custom_section}'
new_prompt_line = '이번에는 카카오스토리용(kakao_text), 네이버 밴드용(band_text), 인스타그램용(insta_text) 3가지 버전으로 각각 작성해야 해.{profile_rule_text}{style_section}{custom_section}'

content = content.replace(old_prompt_line, new_prompt_line)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("api_server.py vendor injection patched!")
