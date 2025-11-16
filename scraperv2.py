# scraper.py (Full Script - Final Version with Improved Captcha Solver)

import time
import pytesseract
import re
from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException
from bs4 import BeautifulSoup
import io
import cv2
import numpy as np
import random

# --- ⚠️ IMPORTANT CONFIGURATION ---
# Update this path to where your Tesseract executable is located.
#   - Windows example: r'C:\Program Files\Tesseract-OCR\tesseract.exe'
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe' # <--- UPDATE THIS

# Update this path to where your chromedriver.exe is located.
CHROME_DRIVER_PATH = './chromedriver.exe' # <--- UPDATE THIS

def get_chromedriver_with_proxy(proxy):
    """
    Configures a Chrome WebDriver instance to use a proxy.
    Handles http, https, socks4, and socks5 protocols.
    Proxy format should be: 'protocol://host:port'
    """
    service = Service(CHROME_DRIVER_PATH)
    options = webdriver.ChromeOptions()
    
    if proxy:
        print(f"Configuring driver with proxy: {proxy}")
        # Selenium's --proxy-server argument correctly handles various protocols
        options.add_argument(f'--proxy-server={proxy}')
    
    # options.add_argument('--headless') # Keep this commented out for initial testing
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument("window-size=1400,800")
    options.add_argument("--disable-gpu") # Can help with stability in some environments
    
    try:
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception as e:
        print(f"Failed to start Chrome with proxy {proxy}: {e}")
        return None

def solve_captcha(driver):
    """
    --- IMPROVED CAPTCHA SOLVER v2 ---
    Solves the captcha using more advanced OpenCV image processing and Tesseract OCR.
    """
    try:
        captcha_element = driver.find_element(By.XPATH, '//img[contains(@src, "vtu_captcha.php")]')
        png = captcha_element.screenshot_as_png
        nparr = np.frombuffer(png, np.uint8)
        img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # --- Advanced Image Processing ---
        # 1. Convert to grayscale
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # 2. Apply a threshold to get a binary image (black and white)
        # This helps remove most of the background noise and colors.
        _, binary = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY_INV)

        # 3. Use morphological operations to clean up noise.
        kernel = np.ones((2, 2), np.uint8)
        eroded = cv2.erode(binary, kernel, iterations=1)
        dilated = cv2.dilate(eroded, kernel, iterations=1)
        
        # Invert the final image back so Tesseract sees black text on a white background.
        final_image = cv2.bitwise_not(dilated)
        
        # Convert the processed OpenCV image to a PIL Image for Tesseract
        pil_img = Image.fromarray(final_image)

        # --- Tesseract OCR ---
        custom_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        captcha_text = pytesseract.image_to_string(pil_img, config=custom_config).strip()
        
        cleaned_text = re.sub(r'[^a-zA-Z0-9]', '', captcha_text)

        print(f"OCR Raw Text: '{captcha_text}', Cleaned Captcha: '{cleaned_text}'")
        
        # Enforce a 6-character length, as this is standard for VTU captchas.
        if cleaned_text and len(cleaned_text) == 6:
            return cleaned_text
        else:
            print(f"OCR failed to read a 6-character captcha. Length was {len(cleaned_text)}.")
            return None
            
    except Exception as e:
        print(f"Error in solve_captcha: {e}")
        return None

def parse_result_html(html_content, usn):
    """
    Parses the HTML of the result page to extract student data,
    including an ultra-robust calculation for total marks and result class.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    result_data = {'usn': usn, 'student_name': 'N/A', 'subjects': [], 'total_marks': 'N/A', 'result_class': 'N/A'}
    
    try:
        name_label = soup.find('td', text=re.compile(r'Student Name', re.I))
        if name_label:
            name_cell = name_label.find_next_sibling('td')
            if name_cell:
                result_data['student_name'] = name_cell.get_text(strip=True).replace(':', '').strip()

        first_semester_header = soup.find('b', text=re.compile(r'Semester\s*:\s*\d+'))
        if first_semester_header:
            semester_table = first_semester_header.find_parent('div').find_next_sibling('div', class_='divTable')
            if semester_table:
                subject_rows = semester_table.find_all('div', class_='divTableRow')
                for row in subject_rows:
                    cells = row.find_all('div', class_='divTableCell')
                    if len(cells) == 7:
                        subject_code = cells[0].text.strip()
                        if subject_code and "subject code" not in subject_code.lower():
                            result_data['subjects'].append({
                                'code':     subject_code, 'name':     cells[1].text.strip(),
                                'internal': cells[2].text.strip(), 'external': cells[3].text.strip(),
                                'total':    cells[4].text.strip(), 'result':   cells[5].text.strip()
                            })
        
        if result_data['subjects']:
            calculated_total = 0
            is_fail = False
            for subject in result_data['subjects']:
                try:
                    calculated_total += int(subject['total'])
                except (ValueError, TypeError):
                    pass # Ignore if 'total' is not a number
                if subject['result'].upper() in ['F', 'A', 'NE', 'X']:
                    is_fail = True
            
            result_data['total_marks'] = str(calculated_total)
            result_data['result_class'] = "FAIL" if is_fail else "PASS"

        return result_data
        
    except Exception as e:
        print(f"An unexpected error occurred during parsing for USN {usn}: {e}")
        return result_data

def fetch_vtu_results(usn_list, vtu_url):
    """
    --- Scraper Logic v8 ---
    Main function to orchestrate the scraping process.
    Uses an improved captcha solver and IP rotation via a proxy list.
    """
    MAX_ATTEMPTS = 3 # Attempts per USN. Free proxies are unreliable.
    all_results = []
    
    # ----------------------------------------------------------------------------------
    # --- ⚠️ ACTION REQUIRED: POPULATE THIS LIST ---
    # 1. Run the `proxy_checker.py` script.
    # 2. It will create a file named `working_proxies.txt`.
    # 3. Open that file, copy all the proxy URLs, and paste them into the list below.
    # ----------------------------------------------------------------------------------
    PROXY_LIST = [
        # PASTE YOUR WORKING PROXIES FROM 'working_proxies.txt' HERE
        # Example format:
        # "http://123.45.67.89:8080",
        # "socks5://98.76.54.32:1080",
    ]
    
    if not PROXY_LIST or (PROXY_LIST and "123.45.67.89" in PROXY_LIST[0]):
        print("\n[WARNING] PROXY_LIST is empty or contains only example data.")
        print("Please run 'proxy_checker.py' and populate the list for IP rotation to work.")
        print("Scraping will proceed without proxies.\n")
        time.sleep(5) # Give user time to see the warning

    for i, usn in enumerate(usn_list):
        if i > 0:
            delay = random.uniform(5, 10) # Randomized delays are crucial
            print(f"\n--- Pausing for {delay:.2f} seconds to avoid rate-limiting ---")
            time.sleep(delay)

        # Select a random proxy for this USN. If the list is empty, proxy will be None.
        proxy = random.choice(PROXY_LIST) if PROXY_LIST else None
        
        # Initialize a new driver instance for each USN to use the new proxy
        driver = get_chromedriver_with_proxy(proxy)
        if not driver:
            print(f"Could not initialize driver for USN {usn} with proxy {proxy}. Skipping.")
            continue

        was_successful = False
        for attempt in range(MAX_ATTEMPTS):
            try:
                print(f"\nFetching result for USN: {usn} (Attempt {attempt + 1}/{MAX_ATTEMPTS})...")
                driver.get(vtu_url)
                time.sleep(1.5)

                captcha_solution = solve_captcha(driver)
                if not captcha_solution:
                    print("Could not solve captcha. Retrying...")
                    time.sleep(1)
                    continue

                driver.find_element(By.NAME, 'lns').send_keys(usn)
                driver.find_element(By.NAME, 'captchacode').send_keys(captcha_solution)
                driver.find_element(By.ID, 'submit').click()
                time.sleep(3)
                
                # Check for JavaScript alerts (e.g., "Invalid captcha", "USN not found")
                try:
                    alert = driver.switch_to.alert
                    alert_text = alert.text
                    alert.accept()
                    if 'Invalid captcha' in alert_text:
                        print(f"Captcha failure for {usn}. Retrying...")
                        continue
                    else:
                        print(f"Alert received for {usn}: '{alert_text}'. Skipping this USN.")
                        was_successful = True # Mark as "successful" to avoid retries
                        break
                except Exception:
                    # No alert was present, which is the normal case
                    pass

                result_data = parse_result_html(driver.page_source, usn)

                if result_data and result_data['subjects']:
                    all_results.append(result_data)
                    print(f"Successfully fetched and parsed result for {usn}")
                    was_successful = True
                    break
                else:
                    print(f"Page loaded for {usn}, but no subjects found. Might be a 'results not available' page.")
                    was_successful = True # Mark as successful to avoid pointless retries
                    break
            
            except Exception as e:
                print(f"A critical error on attempt {attempt + 1} for {usn}: {e}. Retrying...")
                time.sleep(2)
        
        if not was_successful:
            print(f"--- FAILED to fetch result for {usn} after {MAX_ATTEMPTS} attempts. ---")
            
        # IMPORTANT: Quit the driver to close the session and release resources.
        driver.quit()

    return all_results