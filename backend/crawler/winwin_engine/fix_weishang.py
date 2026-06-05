import codecs

file_path = r"d:\안티그래비티\winwin크롤러2\backend\platforms\weishang\crawler.py"

with codecs.open(file_path, 'r', 'utf-8') as f:
    lines = f.readlines()

new_lines = []
in_target_block = False
skip_until = -1

for i, line in enumerate(lines):
    if i < skip_until:
        continue
        
    if "self.add_log(\"[4] 대형 이미지 뷰(大图) 전환 시도...\")" in line:
        # Start of the block to replace
        # We will replace from here until the final `except Exception as e:` of this block.
        # Let's find the end of the block.
        end_idx = i
        for j in range(i+1, min(i+100, len(lines))):
            if 'self.add_log(f"🎉 ({url_idx}/{len(vendor_urls)}) 업체 수집을 본격적으로 시작합니다...", "INFO")' in lines[j]:
                end_idx = j
                break
        
        # Now we insert our new block
        new_block = """                    # ====== 템플릿 전환 ======
                    self.add_log("[4] 대형 이미지 뷰(大图) 전환 시도...")
                    list_clicked = False
                    try:
                        page.wait_for_timeout(2000)
                        list_clicked = page.evaluate(\"\"\"() => {
                            let els = document.querySelectorAll("div, span, li, a");
                            for (let el of els) {
                                if (el.offsetWidth > 0 && el.offsetHeight > 0 && el.innerText) {
                                    let t = el.innerText.trim();
                                    if (t === "大图" || t.includes("大图模式")) {
                                        el.click();
                                        return true;
                                    }
                                }
                            }
                            return false;
                        }\"\"\")
                        if list_clicked:
                            self.add_log("  ✅ 대형 이미지 뷰(大图) 활성화 완료")
                            page.wait_for_timeout(1500)
                        else:
                            self.add_log("  ⚠️ 대형 이미지 뷰(大图) 버튼 못 찾음 (이미 대형 뷰이거나 기본 뷰 유지)", "WARNING")
                    except Exception as e:
                        self.add_log(f"⚠️ 대형 뷰 전환 오류 (무시): {e}", "WARNING")

                    if not list_clicked:
                        try:
                            # 1안 실패 시 다이어그램(多图/图文) 버튼 클릭 시도
                            list_clicked = page.evaluate(\"\"\"() => {
                                // 0. 최우선: 사용자가 지정한 아이콘 이미지 기반 매칭 (정확도 가장 높음)
                                let imgTarget = document.querySelector("img[src*='duotu.png'], img[src*='icon_list_template_duotu']");
                                if (imgTarget) {
                                    // 이미지를 클릭하거나, 클릭 가능한 부모 요소를 상단으로 올라가며 클릭합니다.
                                    let clickable = imgTarget.closest('div, li, a, button') || imgTarget;
                                    clickable.click();
                                    return true;
                                }

                                // 1. 텍스트 직접 매칭 (가장 높은 우선순위)
                                let els = document.querySelectorAll("div, span, li, a");
                                for (let el of els) {
                                    if (el.offsetWidth > 0 && el.offsetHeight > 0 && el.innerText) {
                                        let t = el.innerText.trim();
                                        if (t === "多图" || t === "图文" || t.includes("多图模式") || t.includes("图文") || t === "大图") {
                                            el.click();
                                            return true;
                                        }
                                    }
                                }
                                // 2. 텍스트 매칭 실패 시 클래스 기반 폴백 매칭
                                let fallbacks = document.querySelectorAll("div.index-module_highightFrame_tiqeg, div[class*='tiqeg'], div[class*='highightFrame'], i.icon-liebiao, i.icon-sanlie");
                                for (let fb of fallbacks) {
                                    if (fb.offsetWidth > 0 && fb.offsetHeight > 0) {
                                        fb.click();
                                        return true;
                                    }
                                }
                                return false;
                            }\"\"\")

                            if list_clicked:
                                self.add_log("  ✅ 목록(多图) 뷰 모드 활성화 완료")
                                page.wait_for_timeout(1500)
                            else:
                                self.add_log("  ⚠️ 목록 뷰 아이콘 못 찾음 (기본 뷰로 진행)", "WARNING")
                        except Exception as e:
                            self.add_log(f"⚠️ 추가 뷰 전환 오류 (무시): {e}", "WARNING")

"""
        new_lines.append(new_block)
        skip_until = end_idx
    else:
        new_lines.append(line)

with codecs.open(file_path, 'w', 'utf-8') as f:
    f.writelines(new_lines)

print("Patch applied successfully.")
