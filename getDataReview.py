from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException, WebDriverException
from bs4 import BeautifulSoup
import pandas as pd
import random
import time
from selenium.webdriver.chrome.options import Options
import traceback


def scroll_slow(driver, step=500, wait_time=0.5, max_scrolls=50):
    """Cuộn từng bước nhỏ để ép TripAdvisor load thêm kết quả"""
    last_height = driver.execute_script("return document.body.scrollHeight")
    curr_scrolls = 0
    prev_count = 0

    while curr_scrolls < max_scrolls:
        # cuộn xuống thêm `step` px
        driver.execute_script(f"window.scrollBy(0, {step});")
        time.sleep(wait_time)

        # đếm số card hiện tại
        cards = driver.find_elements(By.CSS_SELECTOR, '[data-test-attribute="location-results-card"]')
        curr_count = len(cards)

        # nếu có nút "Show more" thì bấm
        try:
            btn = driver.find_element(By.XPATH, '//button//*[contains(text(), "Show more")]/ancestor::button')
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            btn.click()
            time.sleep(1)
        except:
            pass

        # nếu không thấy thêm card nào mới → thoát vòng lặp
        if curr_count == prev_count:
            curr_scrolls += 1
        else:
            curr_scrolls = 0  # reset nếu có thêm thẻ
            prev_count = curr_count

        # kiểm tra nếu đã cuộn hết trang
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    print(f"==> Tổng số card load được: {prev_count}")
    return driver.page_source

def scrape(URL, USER, PASS, ports=None, max_retries=3, wait_for=10, keep_driver=False):
    """Setup driver and scrape TripAdvisor page with retry logic across proxy ports.

    - Tries ports in `ports` (defaults to 8001..8005).
    - Retries each port up to `max_retries` times with exponential backoff.
    - Returns page_source on success or raises the last exception on failure.
    """
    if ports is None:
        ports = [8001]

    last_exc = None

    for port in ports:
        for attempt in range(1, max_retries + 1):
            print(f"[proxy-test] Trying port {port} (attempt {attempt}/{max_retries})")
            chrome_options = Options()
            chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--disable-infobars')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--start-maximized')

            seleniumwire_opts = {
                'proxy': {
                    'http': f'http://customer-{USER}:{PASS}@dc.oxylabs.io:{port}',
                    'https': f'https://customer-{USER}:{PASS}@dc.oxylabs.io:{port}',
                },
                # reduce capture if you don't need full request/response bodies
                'request_storage_base_dir': None,
            }

            driver = None
            try:
                driver = webdriver.Chrome(seleniumwire_options=seleniumwire_opts, options=chrome_options)
                driver.set_page_load_timeout(60)
                driver.get(URL)
                # polite random delay
                time.sleep(random.uniform(2, 4))

                WebDriverWait(driver, wait_for).until(
                    EC.presence_of_element_located((
                        By.XPATH,
                        '//*[@data-test-target="reviews-tab"]'
                    ))
                )
                
                time.sleep(random.uniform(1, 2))

                page_source = scroll_slow(driver)
                print(f"[proxy-test] Success with port {port} on attempt {attempt}")
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
                print(f"[proxy-test] Error on port {port} attempt {attempt}: {msg}")
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


def parse(html):
    
    """Parse HTML and extract restaurant data."""
    # Lưu HTML ra file để kiểm tra nếu cần
    with open('debug_page.html', 'w', encoding='utf-8') as f:
        f.write(html)
    soup = BeautifulSoup(html, 'html.parser')
    
    listings = []
    
    for listing in soup.select('[data-test-target="HR_CC_CARD"]'):
        review_title   = listing.select_one('[data-test-target="review-title"] span span')
        href    = listing.select_one('a').get('href') if listing.select_one('a') else None

        # Gán mặc định None hoặc trống nếu thiếu
        review_title_text   = review_title.text.strip() if review_title else None
        # --- Rating ---
        rating_el = listing.select_one('.eaSdf title')
        rating_val = None
        if rating_el:
            # đổi dấu , -> . để parse float
            rating_val = float(rating_el.get_text(strip=True)[0])
        # --- Reviews ---
        reviews_val = None
        reviews_el = listing.select_one('.JguWG span')
        if reviews_el:
            reviews_val = reviews_el.get_text(strip=True)   # "(3.101 đánh giá)"
            
        review_id = None
        review_date = listing.select_one('.MZTIt .biGQs:nth-of-type(2)')
        review_date_text   = review_date.text.strip() if review_date else None

        
        user_id = href.split('/')[-1] if href and '/' in href else None
        user_location = None 
        
        
        try:
            listings.append({
                'user_id': user_id,
                'user_location': user_location,
                'review_id': review_id,
                'review_title': review_title_text,
                'review_content': reviews_val if reviews_val else None,
                'review_date': review_date_text,
                'rating': rating_val if rating_val else None
            })
        except Exception:
            continue
    return listings
def crawl_all_pages(driver, max_pages=2):
    """Crawl nhiều trang bằng nút 'Trang tiếp theo'"""
    all_results = []
    for page in range(max_pages):
        # parse trang hiện tại
        html = driver.page_source
        listings = parse(html)
        all_results.extend(listings)

        # Thử tìm và click nút 'Trang tiếp theo' tối đa 3 lần
        clicked_next = False
        for attempt in range(1, 4):
            try:
                next_btn = WebDriverWait(driver, 6).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@data-smoke-attr="pagination-next-arrow"]'))
                )
                try:
                    next_btn.click()
                except Exception:
                    try:
                        driver.execute_script("arguments[0].click();", next_btn)
                    except Exception:
                        pass

                # đợi trang mới load
                time.sleep(4)

                # đóng modal nếu xuất hiện
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

                clicked_next = True
                break

            except Exception:
                # nếu không tìm thấy nút, reload trang và thử lại
                print(f"[crawl] Không tìm thấy nút 'Trang tiếp theo' (attempt {attempt}/3) — reload và thử lại")
                try:
                    driver.refresh()
                except Exception:
                    try:
                        driver.execute_script('location.reload()')
                    except Exception:
                        pass
                time.sleep(2 + attempt)
    return all_results



def save_to_csv(data, filename):
    """Save data to CSV file."""
    df = pd.DataFrame(data)
    df.to_csv(filename, index=False)


if __name__ == '__main__':
    USER = 'tuaDA1_beKG9'
    PASS = '1452004Tuan='
    # Đọc file CSV
    df = pd.read_csv('listLocation.csv')

    # Giả sử cột chứa URL tên là 'url'
    urls = df['link'].tolist()
    for url in urls[1:2]:
        URL = url
        driver = None
        try:
            # mở driver 1 lần, yêu cầu scrape trả về driver sống để crawl nhiều trang
            driver = scrape(URL, USER, PASS, keep_driver=True)
        except Exception as e:
            print('Scrape failed:', e)
            raise
        # nếu scrape trả về driver, tiếp tục crawl nhiều trang
        try:
            results = crawl_all_pages(driver, max_pages=2)
            save_to_csv(results, 'resultsLocation.csv')
        finally:
            try:
                if driver:
                    driver.quit()
            except Exception:
                pass