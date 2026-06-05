import sys

path = 'backend/platforms/weishang/crawler.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("max_workers=6, thread_name_prefix=\"img_dl\"", "max_workers=3, thread_name_prefix=\"img_dl\"")

# Retry delay increase for download
old_retry = """                if attempt < 2:
                    time.sleep(0.45 * (attempt + 1))"""
new_retry = """                if attempt < 2:
                    delay = 1.0 * (attempt + 1)
                    if r is not None and r.status_code in [403, 429, 503]:
                        delay += 3.0
                    time.sleep(delay)"""
content = content.replace(old_retry, new_retry)

# Supplement signal merge protection
old_merge = """                                        elif has_supplement_signal or (rule_prefers_merge_detail and text_is_short):
                                            is_main_product = False
                                            self.add_log("  🔍 [경계판별-휴리스틱] 보충/상세 신호 → 직전 상품에 병합", "INFO")"""
new_merge = """                                        elif has_supplement_signal or (rule_prefers_merge_detail and text_is_short):
                                            pending_cnt = len(_pending_product.get('img_urls', [])) if _pending_product else 0
                                            curr_cnt = len(img_urls)
                                            if pending_cnt >= 9 or (pending_cnt + curr_cnt) > 12:
                                                is_main_product = True
                                                self.add_log("  ✂️ [경계판별-휴리스틱] 보충컷이나, 누적 사진 한도 방지로 새 상품 분리", "INFO")
                                            else:
                                                is_main_product = False
                                                self.add_log("  🔍 [경계판별-휴리스틱] 보충/상세 신호 → 직전 상품에 병합", "INFO")"""
content = content.replace(old_merge, new_merge)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Patch applied to crawler.py")
