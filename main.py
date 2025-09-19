import base64
import csv
from datetime import datetime
import os
import random
import re
import time
import traceback
import pandas as pd
import requests
from bs4 import BeautifulSoup
from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.options import Options
import urllib

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.5993.118 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
]


def rand_sleep(min_s=5, max_s=10):
    """Sleep for a random duration between min_s and max_s seconds."""
    time.sleep(random.uniform(min_s, max_s))


def scroll_slow(driver, step=500, wait_time=1, max_scroll=10):
    """Scroll page slowly to trigger lazy loading."""
    last_height = driver.execute_script("return document.body.scrollHeight")
    for i in range(max_scroll):
        driver.execute_script(f"window.scrollBy(0, {step});")
        rand_sleep(wait_time, wait_time + 1)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
    return driver.page_source


def close_MgsBox(driver):
    try:
        modal = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-automation="closeModal"], button[aria-label*="Đóng"], button[aria-label*="Đóng"], button[aria-label*="Close"]'))
        )
        try:
            modal.click()
        except Exception:
            try:
                driver.execute_script("arguments[0].click();", modal)
            except Exception:
                pass
    except Exception:
        pass



def normalize_date(text):
    now = datetime.now()
    current_year = now.year

    if not text:
        return now.strftime("%d/%m/%Y")

    text = text.lower().strip()

    # -----------------
    # Dạng "đã viết vào 25 tháng 7, 2025"
    m = re.search(r"(\d{1,2})\s+tháng\s+(\d{1,2}),?\s*(\d{4})?", text)
    if m:
        day, month, year = m.groups()
        year = year if year else str(current_year)
        return f"{int(day):02d}/{int(month):02d}/{year}"

    # -----------------
    # Review date ngắn (today, sec, phút, giờ, hôm qua...)
    if any(kw in text for kw in ["today", "sec", "phút", "giờ", "ngày", "hôm qua", "yesterday", "week", "tháng trước"]):
        return now.strftime("%d/%m/%Y")

    # -----------------
    # Stay date
    # "thg 8 2025"
    m = re.match(r"thg\s+(\d{1,2})\s+(\d{4})", text)
    if m:
        month, year = m.groups()
        return f"{int(month):02d}/{year}"

    # "thg 7 năm 2025"
    m = re.match(r"thg\s+(\d{1,2})\s+năm\s+(\d{4})", text)
    if m:
        month, year = m.groups()
        return f"{int(month):02d}/{year}"

    # "tháng 12 năm 2023"
    m = re.match(r"tháng\s+(\d{1,2})\s+năm\s+(\d{4})", text)
    if m:
        month, year = m.groups()
        return f"{int(month):02d}/{year}"

    # "2 thg 9"
    m = re.match(r"\d{1,2}\s+thg\s+(\d{1,2})", text)
    if m:
        month = m.group(1)
        return f"{int(month):02d}/{current_year}"

    # -----------------
    # Fallback
    return now.strftime("%d/%m/%Y")


def scrape(URL, USER, PASS, ports=None, max_retries=3, wait_for=10, keep_driver=False):
    """Setup driver and scrape TripAdvisor page with retry logic across proxy ports.

    - Tries ports in `ports` (defaults to 8001..8005).
    - Retries each port up to `max_retries` times with exponential backoff.
    - Returns page_source on success or raises the last exception on failure.
    """
    if ports is None:
        ports = [8001]

    last_exc = None

    for attempt in range(1, max_retries + 1):
        changeIP()
        chrome_options = Options()
        ua = random.choice(USER_AGENTS)
        chrome_options.add_argument(f"user-agent={ua}")
        chrome_options.add_argument('--lang=vi')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-infobars')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--start-maximized')
        # chrome_options.add_argument(r'--user-data-dir=C:\Users\<user>\AppData\Local\CocCoc\Browser\User Data')
        # chrome_options.add_argument(r'--profile-directory=Profile 2')
        proxy_host = "103.57.128.248"
        proxy_port = 8329
        proxy_user = "xLkgW8Deanhtu"
        proxy_pass = "t7as2eWT"
        seleniumwire_opts = {
            'proxy': {
                'http': f'http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}',
                'https': f'http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}',
            },
            'request_storage_base_dir': None,
        }

        driver = None
        try:
            driver = webdriver.Chrome(seleniumwire_options=seleniumwire_opts, options=chrome_options)
            driver.set_page_load_timeout(60)

            # Xóa dấu vết automation
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})")
            driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]})")

            # Truy cập trang chủ trước để nhận cookie/session
            driver.get("https://www.tripadvisor.com/")
            rand_sleep(3, 7)
            # Sau đó mới vào link địa điểm
            driver.get(URL)
            # rand_sleep(2, 5)
            # click_country_button(driver, country_name="Việt Nam")
            # rand_sleep(2, 4)
            max_reload = 5
            for reload_attempt in range(max_reload):
                try:
                    WebDriverWait(driver, wait_for).until(
                        EC.presence_of_element_located((
                            By.XPATH,
                            "//div[@id='tab-review-content']"
                        ))
                    )
                    break  # Nếu tìm thấy thì thoát vòng lặp
                except Exception:
                    print(f"Không tìm thấy reviews-tab, reload lần {reload_attempt+1}/{max_reload}")
                    driver.refresh()
                    rand_sleep(2, 4)
            else:
                # Nếu hết 5 lần vẫn không tìm thấy, raise ngoại lệ để nhảy ra ngoài
                raise Exception("Không tìm thấy reviews-tab sau khi reload 5 lần")
            
            rand_sleep(1, 2)

            page_source = scroll_slow(driver)

            if keep_driver:
                # return live driver for further actions (caller must quit it)
                return driver
            else:
                try:
                    driver.quit()
                except Exception:
                    pass
                return page_source

        except Exception as e:
            last_exc = e
            msg = getattr(e, 'msg', str(e))
            # print(f"[proxy-test] Error on port {port} attempt {attempt}: {msg}")
            # ensure driver closed
            try:
                if driver:
                    driver.quit()
            except Exception:
                pass

            # small backoff before retrying
            backoff = 2 ** (attempt - 1)
            time.sleep(backoff)
            continue

    # all ports/attempts exhausted
    print("[proxy-test] All ports/attempts exhausted. Raising last exception.")
    if last_exc:
        raise last_exc
    raise RuntimeError('Failed to connect via any proxy port')

def changeIP():
    # Gọi link đổi IP trước khi crawl
    change_ip_url = "https://api.zingproxy.com/getip/ee0ab4f3f39084d583b5dfa1bde05a9fedfbcf14"
    try:
        requests.get(change_ip_url, timeout=10)
        print("Đã đổi IP proxy!")
    except Exception as e:
        print("Lỗi đổi IP:", e)

def scrape_tripadvisor_reviews(driver, output_csv, url):
    reviews = []
    page = 1
    rand_sleep(2, 4)
    close_MgsBox(driver)
    while page <= 100:  # giới hạn max 100 trang
        soup = BeautifulSoup(driver.page_source, "html.parser")
        review_blocks = soup.find_all(attrs={"data-automation": "reviewCard"})
        print(f"Page {page}: found {len(review_blocks)} reviews")

        for block in review_blocks:
            a = block.select_one('.ncFvv a')
            if not a:
                continue
            href = a['href']
            href1 = href.split('-')
            for p in href1:
                if p.startswith('r'):
                    id = p  # "g298085"
            title = block.select_one('a .yCeTE')
            review_text = block.select_one('.biGQs span .yCeTE')
            createdDate_span = block.select_one('.TreSq div')
            createdDate = normalize_date(createdDate_span.get_text(strip=True) if createdDate_span else "")

            date_spans = block.select_one(".RpeCd").get_text(strip=True)
            parts = [p.strip() for p in date_spans.split("•")]
            stayDate = parts[0] if len(parts) > 0 else ""
            tripType = parts[1] if len(parts) > 1 else ""
                
            rating_span = block.select_one(".VVbkp title")

            rating = None
            if rating_span:
                raw = rating_span.get_text(strip=True)
                m = re.search(r"(\d+[.,]?\d*)", raw)
                if m:
                    rating = float(m.group(1).replace(",", "."))

            parts = url.split('-') 
            locationId = ""
            parentGeoId = ""
            for p in parts:
                if p.startswith('g'):
                    parentGeoId = p  # "g298085"
                elif p.startswith('d'):
                    locationId = p  # "d17324749"
                    
            user = block.select_one(".QIHsu span a")
            username = user.get_text(strip=True) if user else ""
            
            userHref = user.get("href") if user else ""
            val = userHref.split("value=")[-1]
            val = urllib.parse.unquote(val)
            decoded = base64.b64decode(val).decode("utf-8")
            user_id = decoded.split("/")[-1].split("_")[0]
            
            helpful_votes = block.select_one(".Vonfv .kLqdM span")
            hotel_name = soup.select_one("h1[data-test-target='mainH1']").get_text(strip=True) if soup.select_one("h1[data-test-target='mainH1']") else ""
            
            address = soup.select_one(".NpLUv .suezE .VImYz").get_text(strip=True) if soup.select_one(".NpLUv .suezE .VImYz") else ""

            reviews.append(
                {
                    "id": id,
                    "language": "vi",
                    "rating": rating,
                    "createdDate": createdDate,
                    "helpfulVotes": helpful_votes.get_text(strip=True) if helpful_votes else "",
                    "username": username,
                    "userId": user_id,
                    "title": title.get_text(strip=True) if title else "",
                    "text": review_text.get_text(strip=True) if review_text else "",
                    "locationId": locationId,     
                    "parentGeoId": parentGeoId,       
                    "hotelName": hotel_name,
                    "address": address,
                    "stayDate": normalize_date(stayDate),
                    "tripType": tripType
                }
            )

        # thử click nút next page
        try:
            next_btn = driver.find_element(By.CSS_SELECTOR, '[data-smoke-attr="pagination-next-arrow"]')
            driver.execute_script("arguments[0].scrollIntoView({block: \'center\'});", next_btn)
            rand_sleep(2, 4)
            driver.execute_script("arguments[0].click();", next_btn)
            rand_sleep(2, 4)
            page += 1
        except NoSuchElementException:
            print("No more pages.")
            break

    keys = ["id", "language", "rating", "createdDate", "helpfulVotes",
            "username", "userId", "title", "text", "locationId", "parentGeoId", "hotelName",
            "address", "stayDate", "tripType"]
    
    file_exists = os.path.isfile(output_csv)
    with open(output_csv, "a", newline="", encoding="utf-8") as f:
        dict_writer = csv.DictWriter(f, fieldnames=keys)
        if not file_exists:  # chỉ ghi header 1 lần
            dict_writer.writeheader()
        dict_writer.writerows(reviews)

    print(f"✅ Saved {len(reviews)} reviews to {output_csv}")

if __name__ == "__main__":
    
    USER = "tuaDA1_beKG9"
    PASS = "1452004Tuan="

    driver = None
    
    df = pd.read_csv('listRelaxLocation.csv')
    urls = df['link'].tolist()
    for url in urls:
        URL = url.replace("tripadvisor.com", "tripadvisor.com.vn")
        try:
            driver = scrape(URL, USER, PASS, keep_driver=True)
            output_file = "listRelaxLocation_reviews.csv"
            scrape_tripadvisor_reviews(driver, output_file, url=URL)
        except Exception as e:
            print("Scrape failed:", e)
            traceback.print_exc()
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass