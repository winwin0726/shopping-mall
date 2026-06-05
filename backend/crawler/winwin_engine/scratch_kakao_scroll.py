from selenium import webdriver
from selenium.webdriver.common.by import By
import time
import undetected_chromedriver as uc

options = uc.ChromeOptions()
options.add_argument(r"--user-data-dir=c:\programing\윈윈크롤러2\kakao_profile_4-1_신발카드_(신규)")
driver = uc.Chrome(options=options, use_subprocess=True)
driver.get("https://story.kakao.com/ch/winwin58") # Or whatever channel

time.sleep(5)
posts = driver.find_elements(By.CSS_SELECTOR, "div.section._activity")
print("Initial posts:", len(posts))

driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
time.sleep(3)
posts = driver.find_elements(By.CSS_SELECTOR, "div.section._activity")
print("After scrollTo body.scrollHeight:", len(posts))

# Let's try scrolling the window by a large amount
driver.execute_script("window.scrollBy(0, 10000);")
time.sleep(3)
posts = driver.find_elements(By.CSS_SELECTOR, "div.section._activity")
print("After scrollBy 10000:", len(posts))

# Let's find the last post and scroll to it
if posts:
    driver.execute_script("arguments[0].scrollIntoView();", posts[-1])
    time.sleep(3)
    posts2 = driver.find_elements(By.CSS_SELECTOR, "div.section._activity")
    print("After scrollIntoView last post:", len(posts2))

driver.quit()
