import sys
with open('backend/crawler_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''                        except Exception as te:
                            self.add_log(f"❌ 자동 번역 파이프라인 시작 실패: {te}", "ERROR")
        plat_name = "weishang" if "웨이상" in platform else "kakao" if "카카오" in platform else "band" if "밴드" in platform else platform'''

replace = '''                        except Exception as te:
                            self.add_log(f"❌ 자동 번역 파이프라인 시작 실패: {te}", "ERROR")

                if len(self.crawled_products) > 0:
                    try:
                        from backend.analysis_history import save_analysis_history
                        summary_msg = f"{platform} 수집 자동 백업 ({len(self.crawled_products)}건)"
                        save_analysis_history(len(self.crawled_products), "", summary_msg, {"bundled_products": self.crawled_products})
                        self.add_log(f"💾 크롤링 실행건 백업 완료 (분석자료 관리 화면에서 확인 가능)", "SUCCESS")
                    except Exception as backup_err:
                        self.add_log(f"⚠️ 자동 백업 실패: {backup_err}", "WARNING")

        plat_name = "weishang" if "웨이상" in platform else "kakao" if "카카오" in platform else "band" if "밴드" in platform else platform'''

if target in content:
    with open('backend/crawler_engine.py', 'w', encoding='utf-8') as f:
        f.write(content.replace(target, replace))
    print('OK')
else:
    print('NO_MATCH')
