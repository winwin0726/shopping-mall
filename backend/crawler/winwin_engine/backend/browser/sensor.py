import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, WebDriverException

class BrowserStateGuard:
    """
    브라우저의 상태(DOM, 요소 렌더링, 네트워크 업로드 등)를 
    명시적으로 대기(Explicit Wait)하는 공통 센서 모듈.
    """

    @staticmethod
    def wait_page_ready(driver, timeout=30):
        """
        DOM의 readyState가 'complete'가 될 때까지 대기합니다.
        """
        try:
            WebDriverWait(driver, timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            return True
        except TimeoutException:
            return False

    @staticmethod
    def wait_element_visible(driver, by, selector, timeout=10):
        """
        특정 요소가 화면에 나타날 때까지 대기합니다.
        """
        try:
            return WebDriverWait(driver, timeout).until(
                EC.visibility_of_element_located((by, selector))
            )
        except TimeoutException:
            return None

    @staticmethod
    def wait_element_clickable(driver, by, selector, timeout=10):
        """
        특정 요소가 클릭 가능해질 때까지 대기합니다.
        """
        try:
            return WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((by, selector))
            )
        except TimeoutException:
            return None

    @staticmethod
    def wait_upload_done(driver, target_count, current_count_func, timeout=60, check_interval=0.5):
        """
        사진 업로드 등 비동기 작업이 완료될 때까지 반복 확인합니다.
        current_count_func 는 현재 업로드된 개수를 반환하는 함수여야 합니다.
        """
        start_time = time.time()
        last_count = -1
        stable_since = None

        while time.time() - start_time < timeout:
            try:
                count = current_count_func()
                if count >= target_count:
                    return count
                
                # 개수 변화가 멈춘 채로 3초 이상 지나면 완료된 것으로 간주 (일부 업로드 실패 시)
                if count == last_count:
                    if stable_since is None:
                        stable_since = time.time()
                    elif time.time() - stable_since >= 3 and count > 0:
                        return count
                else:
                    stable_since = None
                    last_count = count
            except WebDriverException:
                pass
            
            time.sleep(check_interval)
            
        return current_count_func()
