import os

file_path = 'c:/programing/윈윈크롤러2/backend/platforms/weishang/crawler.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 엉뚱하게 수정된 라인 2118 복구
bad_diff = """                            rules_text = f.read()
                    except Exception:
                        rules_text = "기본 번역 포맷을 사용합니다."
                            rules_text = f.read()
                    except Exception:
                        rules_text = "기본 번역 포맷을 사용합니다."
"""
good_diff = """                            rules_text = f.read()
                    except Exception:
                        rules_text = "기본 번역 포맷을 사용합니다."
"""
content = content.replace(bad_diff, good_diff)

# 두 번째로 엉뚱하게 수정된 라인 2125 복구
bad_diff2 = """                    seen_image_fingerprints = set()
                    seen_first_image_counts = {}
                    seen_image_fingerprint_counts = {}
                    
                    while not _stop_crawling_by_date and not self.stop_flag:"""
good_diff2 = """                    seen_image_fingerprints = set()
                    seen_first_image_counts = {}
                    seen_image_fingerprint_counts = {}

                    while not _stop_crawling_by_date and not self.stop_flag:"""
content = content.replace(bad_diff2, good_diff2)


# 정상적인 blacklist 수정
content = content.replace('"二维码", "扫码", "扫一扫", "分享", "转发朋友圈",', '"二维码", "扫一扫", "转发朋友圈",')
content = content.replace('"不要", "文字", "图文",', '')
content = content.replace('"关注", "点赞", "收藏", "评论",', '"点赞", "收藏",')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Fix applied.")
