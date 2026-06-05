import re

with open('backend/platforms/weishang/crawler.py', 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if "self.add_log(\"[4] 대형 이미지 뷰(大图) 전환 시도...\")" in line:
        skip = True
        new_lines.append('                    # ====== 템플릿 전환 ======\n')
        new_lines.append('                    self.add_log("[4] 대형 이미지/목록 뷰 전환 시도...")\n')
        new_lines.append('                    try:\n')
        new_lines.append('                        page.wait_for_timeout(2000)\n')
        new_lines.append('                        list_clicked = page.evaluate("""() => {\n')
        new_lines.append('                            // 0. 최우선: 사용자가 지정한 아이콘 이미지 기반 매칭 (정확도 가장 높음)\n')
        new_lines.append('                            let imgTarget = document.querySelector("img[src*=\'duotu.png\'], img[src*=\'icon_list_template_duotu\']");\n')
        new_lines.append('                            if (imgTarget) {\n')
        new_lines.append('                                let clickable = imgTarget.closest(\'div, li, a, button\') || imgTarget;\n')
        new_lines.append('                                clickable.click();\n')
        new_lines.append('                                return true;\n')
        new_lines.append('                            }\n')
        new_lines.append('\n')
        new_lines.append('                            // 1. 텍스트 직접 매칭\n')
        new_lines.append('                            let els = document.querySelectorAll("div, span, li, a");\n')
        new_lines.append('                            for (let el of els) {\n')
        new_lines.append('                                if (el.offsetWidth > 0 && el.offsetHeight > 0 && el.innerText) {\n')
        new_lines.append('                                    let t = el.innerText.trim();\n')
        new_lines.append('                                    if (t === "大图" || t.includes("大图模式") || t === "多图" || t === "图文" || t.includes("多图模式") || t.includes("图文")) {\n')
        new_lines.append('                                        el.click();\n')
        new_lines.append('                                        return true;\n')
        new_lines.append('                                    }\n')
        new_lines.append('                                }\n')
        new_lines.append('                            }\n')
        new_lines.append('                            \n')
        new_lines.append('                            // 2. 클래스 기반 폴백 매칭\n')
        new_lines.append('                            let fallbacks = document.querySelectorAll("div.index-module_highightFrame_tiqeg, div[class*=\'tiqeg\'], div[class*=\'highightFrame\'], i.icon-liebiao, i.icon-sanlie");\n')
        new_lines.append('                            for (let fb of fallbacks) {\n')
        new_lines.append('                                if (fb.offsetWidth > 0 && fb.offsetHeight > 0) {\n')
        new_lines.append('                                    fb.click();\n')
        new_lines.append('                                    return true;\n')
        new_lines.append('                                }\n')
        new_lines.append('                            }\n')
        new_lines.append('                            return false;\n')
        new_lines.append('                        }""")\n')
        new_lines.append('                        \n')
        new_lines.append('                        if list_clicked:\n')
        new_lines.append('                            self.add_log("  ✅ 대형 이미지/목록 뷰 모드 활성화 완료")\n')
        new_lines.append('                            page.wait_for_timeout(1500)\n')
        new_lines.append('                        else:\n')
        new_lines.append('                            self.add_log("  ⚠️ 목록 뷰 전환 아이콘 못 찾음 (이미 대형 뷰이거나 기본 뷰 유지)", "WARNING")\n')
        new_lines.append('                    except Exception as e:\n')
        new_lines.append('                        self.add_log(f"⚠️ 뷰 전환 오류 (무시): {e}", "WARNING")\n')
        continue

    if skip:
        # We need to skip until the end of the original except block.
        # The end of the original block is followed by "self.add_log(f\"🎉 ({url_idx}/{len(vendor_urls)})"
        if "업체 수집을 본격적으로 시작합니다" in line:
            skip = False
            new_lines.append(line)
        continue
    
    if "====== 템플릿 전환 ======" in line and "self.add_log(\"[4] 대형 이미지 뷰(大图) 전환 시도...\")" in lines[i+1]:
        # we skip this line too because we handle it above
        continue

    new_lines.append(line)

with open('backend/platforms/weishang/crawler.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Done!")
