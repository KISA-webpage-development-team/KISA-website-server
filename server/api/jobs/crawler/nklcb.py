from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from bs4 import BeautifulSoup
import time
import json

def get_jobs():
    # (동은 컴터 테스트용 무시하셈)
    # CHROMEDRIVER_PATH = r"C:\Users\de7da\.wdm\drivers\chromedriver\win64\138.0.7204.94\chromedriver-win32\chromedriver.exe"

    chrome_options = Options()
    # 자동화 도입하면 headless로. 지금은 디버깅 위해서 꺼놓음.
    # chrome_options.add_argument("--headless=new")
    chrome_options.add_experimental_option("detach", True)
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    # 다 크롤링하면 시간 너무 오래 걸려서 우선 되는지 확인하기 위해서 기업마다 2개씩만 했음.
    company_list = ["NAVER", "KAKAO", "LINE", "COUPANG", "WOOWAHAN", "DAANGN", "TOSS", "NEXON", "KRAFTON", "MOLOCO", "DUNAMU", "SENDBIRD"]
    jobs = []

    try:
        for company in company_list:
            print(f"Loading page for: {company}")
            driver.get(f"https://www.nklcb.kr/web?company={company}")

            # Wait until job cards load
            WebDriverWait(driver, 15).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[class*='recruit-card_card__container']"))
            )
            time.sleep(1)

            cards = driver.find_elements(By.CSS_SELECTOR, "div[class*='recruit-card_card__container']")

            for i in range(min(2, len(cards))):
                try:
                    # Re-select cards each time because the DOM may refresh
                    cards = driver.find_elements(By.CSS_SELECTOR, "div[class*='recruit-card_card__container']")
                    card = cards[i]

                    # hovering action on card
                    ActionChains(driver).move_to_element(card).pause(0.3).perform()
                    time.sleep(0.5)

                    soup = BeautifulSoup(card.get_attribute("outerHTML"), "html.parser")
                    comp = soup.find("span", class_=lambda c: c and "recruit-card_card__company" in c).text.strip()
                    title = soup.find("span", class_=lambda c: c and "recruit-card_card__title__" in c).text.strip()
                    date = soup.find("span", class_=lambda c: c and "recruit-card_card__timestamp" in c).text.strip()
                    position = soup.find("span", class_=lambda c: c and "recruit-card_card__position" in c).text.strip()

                    clickable = card.find_element(By.CSS_SELECTOR, "div[class*='recruit-card_card__path__container']")
                    original_tabs = driver.window_handles
                    clickable.click()

                    # new tab to open
                    WebDriverWait(driver, 10).until(lambda d: len(d.window_handles) > len(original_tabs))
                    new_tab = [tab for tab in driver.window_handles if tab not in original_tabs][0]

                    driver.switch_to.window(new_tab)
                    time.sleep(1.5)

                    # final url
                    link = driver.current_url

                    jobs.append({
                        "title": f"{comp} | {title}",
                        "date": date,
                        "position": position,
                        "link": link
                    })

                    driver.close()
                    driver.switch_to.window(original_tabs[0])
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[class*='recruit-card_card__container']"))
                    )
                    time.sleep(0.5)
                
                except Exception as e:
                    print(f"Error parsing card #{i} for {company}: {e}")
                    driver.get(f"https://www.nklcb.kr/web?company={company}")
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[class*='recruit-card_card__container']"))
                    )
                    continue

        # for debugging - priting in console as JSON
        print(json.dumps(jobs, indent=2, ensure_ascii=False))
        return jobs

    finally:
        driver.quit()
