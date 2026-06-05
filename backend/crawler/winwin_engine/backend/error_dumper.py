import os
import time
import traceback

def save_error_dump(driver, context_name="error"):
    """
    셀레니움 드라이버 에러 발생 시 스크린샷과 HTML을 캡처하여 저장한다.
    """
    try:
        if not driver:
            return None
            
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        dump_dir = os.path.join(base_dir, 'error_dumps')
        os.makedirs(dump_dir, exist_ok=True)
        
        ts = time.strftime("%Y%m%d_%H%M%S")
        prefix = os.path.join(dump_dir, f"{ts}_{context_name}")
        
        # 스크린샷 저장
        driver.save_screenshot(f"{prefix}.png")
        
        # HTML 덤프 저장
        with open(f"{prefix}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
            
        # 에러 URL 및 추가 정보 저장
        with open(f"{prefix}_info.txt", "w", encoding="utf-8") as f:
            f.write(f"URL: {driver.current_url}\n")
            f.write(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Traceback:\n{traceback.format_exc()}\n")
            
        return prefix
    except Exception as e:
        print(f"[ErrorDumper] 덤프 저장 실패: {e}")
        return None

def save_playwright_error_dump(page, context_name="pw_error"):
    """
    Playwright 페이지 객체에서 에러 발생 시 스크린샷과 HTML을 캡처한다.
    """
    try:
        if not page:
            return None
            
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        dump_dir = os.path.join(base_dir, 'error_dumps')
        os.makedirs(dump_dir, exist_ok=True)
        
        ts = time.strftime("%Y%m%d_%H%M%S")
        prefix = os.path.join(dump_dir, f"{ts}_{context_name}")
        
        # 스크린샷 저장
        page.screenshot(path=f"{prefix}.png", full_page=True)
        
        # HTML 덤프 저장
        with open(f"{prefix}.html", "w", encoding="utf-8") as f:
            f.write(page.content())
            
        # 에러 URL 및 추가 정보 저장
        with open(f"{prefix}_info.txt", "w", encoding="utf-8") as f:
            f.write(f"URL: {page.url}\n")
            f.write(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Traceback:\n{traceback.format_exc()}\n")
            
        return prefix
    except Exception as e:
        print(f"[ErrorDumper] Playwright 덤프 저장 실패: {e}")
        return None
