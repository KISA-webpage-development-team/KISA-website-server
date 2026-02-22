from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse
import json, time

BASE = "https://www.superookie.com"
NEWBIE_URL = "https://www.superookie.com/jobs?job_level%5B%5D=579f18168b129f673b4efebf"

# @Jioh - we can add more types later if needed (e.g., '계약직', '파트타임', '주니어')

MAX_JOBS = 100  # total to collect
MAX_PAGES = 3   # only 3 pages available in srookie

# UTILS
def driver(headless=False):
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

# Appending &page= in the given URL.
def set_page(url: str, page: int) -> str:    
    u = urlparse(url)
    q = parse_qs(u.query, keep_blank_values=True)
    q["page"] = [str(page)]
    new_q = urlencode(q, doseq=True)
    return urlunparse((u.scheme, u.netloc, u.path, u.params, new_q, u.fragment))

def extract_company(detail_html: str) -> str:
    soup = BeautifulSoup(detail_html, "html.parser")
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            if not script.string:
                continue
            data = json.loads(script.string)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict):
                    org = item.get("hiringOrganization") or item.get("publisher")
                    if isinstance(org, dict) and org.get("name"):
                        return org["name"].strip()
        except Exception:
            pass
    return ""

def extract_value_by_label(detail_html: str, label: str) -> str:
    soup = BeautifulSoup(detail_html, "html.parser")
    for block in soup.select(".job-detail-item-body .bottommargin-xs, .job-detail-item .bottommargin-xs"):
        txt = block.get_text("\n", strip=True)
        if label in txt:
            lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
            for i, ln in enumerate(lines):
                if label in ln and i + 1 < len(lines):
                    return lines[i + 1]
    return ""

# MAIN
def srookie_newbie_crawl(headless=False):
    drv = driver(headless=headless)
    output = []
    try:
        page = 1
        while page <= MAX_PAGES and len(output) < MAX_JOBS:
            page_url = set_page(NEWBIE_URL, page)
            drv.get(page_url)

            # Wait for the list container and at least 1 card
            WebDriverWait(drv, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.row.jobs.posts"))
            )
            WebDriverWait(drv, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.item-job a.job-detail-link.color-black"))
            )

            # Collect ALL card elements (this page)
            cards = drv.find_elements(By.CSS_SELECTOR, "div.item-job a.job-detail-link.color-black")
            total_on_page = len(cards)

            # Process every card on this page (finish the page)
            for idx in range(total_on_page):
                if len(output) >= MAX_JOBS:
                    break

                cards = drv.find_elements(By.CSS_SELECTOR, "div.item-job a.job-detail-link.color-black")
                a = cards[idx]

                # position (from card)
                try:
                    position = a.find_element(By.CSS_SELECTOR, "p.job-title").get_attribute("innerText").strip()
                except Exception:
                    position = BeautifulSoup(a.get_attribute("outerHTML"), "html.parser").get_text(" ", strip=True)

                href = a.get_attribute("href") or ""
                if href.startswith("/"):
                    href = urljoin(BASE, href)

                # Open detail in new tab
                before = drv.window_handles
                drv.execute_script("arguments[0].click();", a)
                WebDriverWait(drv, 12).until(lambda d: len(d.window_handles) > len(before))
                new_tab = [t for t in drv.window_handles if t not in before][0]
                drv.switch_to.window(new_tab)

                WebDriverWait(drv, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))
                time.sleep(0.5)
                html = drv.page_source

                company = extract_company(html)
                date_txt = extract_value_by_label(html, "접수기간")

                output.append({
                    "title": company,      # company name
                    "date": date_txt,      # '접수기간' value
                    "position": position,  # job title
                    "link": href,          # detail link
                })

                drv.close()
                drv.switch_to.window(before[0])

            # After current page is all done processing
            page += 1

        # currently just printing the output. later, we can save to DB.
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return output

    finally:
        drv.quit()

if __name__ == "__main__":
    srookie_newbie_crawl(headless=False)
