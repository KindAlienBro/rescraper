# scraper.py (Full Script - Final Version with Anti-Distortion Captcha Solver)

import time
import pytesseract
import re
from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import io
import cv2
import numpy as np
import random
import os

# --- ⚠️ IMPORTANT CONFIGURATION ---
# Update this path to where your Tesseract executable is located.
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe' # <--- UPDATE THIS

# Update this path to where your chromedriver.exe is located.
CHROME_DRIVER_PATH = './chromedriver.exe' # <--- UPDATE THIS

def get_chromedriver_with_proxy(proxy):
    """
    Configures a Chrome WebDriver instance to use a proxy.
    """
    service = Service(CHROME_DRIVER_PATH)
    options = webdriver.ChromeOptions()
    
    if proxy:
        print(f"Configuring driver with proxy: {proxy}")
        options.add_argument(f'--proxy-server={proxy}')
    
    # options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument("window-size=1400,800")
    options.add_argument("--disable-gpu")
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    try:
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception as e:
        print(f"Failed to start Chrome with proxy {proxy}: {e}")
        return None

# --- NEW CAPTCHA SOLVER v3: Tuned for Merged/Distorted Characters ---
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
    Parses VTU result HTML page for:
    USN, Name, Subject Code, Internal Marks, External Marks, Total, Result.
    Handles both <b> inside <td> and div/table layouts.
    """

    soup = BeautifulSoup(html_content, 'html.parser')

    # --- Handle invalid or unavailable results ---
    if re.search(r'Invalid USN|Results are not yet available', html_content, re.I):
        print(f"[{usn}] Invalid USN or results not available.")
        return None

    try:
        # --- Extract Student Details (handle <b> tags) ---
        usn_label = soup.find('b', string=re.compile(r'University Seat Number', re.I))
        if not usn_label:
            print(f"[{usn}] 'University Seat Number' not found.")
            return None

        usn_td = usn_label.find_parent('td')
        usn_value_td = usn_td.find_next_sibling('td')
        usn_value = re.sub(r'[:\s]+', '', usn_value_td.get_text(strip=True)).upper()

        name_label = soup.find('b', string=re.compile(r'Student Name', re.I))
        if not name_label:
            print(f"[{usn}] 'Student Name' not found.")
            return None

        name_td = name_label.find_parent('td')
        name_value_td = name_td.find_next_sibling('td')
        name_value = re.sub(r'^[:\s]+', '', name_value_td.get_text(strip=True)).title()

        # --- Locate result structure ---
        results_div_table = soup.find('div', class_='divTable')
        if not results_div_table:
            results_div_table = soup.find('table', class_=re.compile(r'table', re.I))
            if not results_div_table:
                print(f"[{usn}] Result table not found.")
                return None

        # --- Extract subjects ---
        subjects = []

        if results_div_table.name == 'div':
            rows = results_div_table.find_all('div', class_='divTableRow')
            for row in rows[1:]:
                cells = row.find_all('div', class_='divTableCell')
                if len(cells) >= 6:
                    subjects.append({
                        'subject_code': cells[0].get_text(strip=True),
                        'internal_marks': cells[2].get_text(strip=True),
                        'external_marks': cells[3].get_text(strip=True),
                        'total': cells[4].get_text(strip=True),
                        'result': cells[5].get_text(strip=True)
                    })
        else:
            # For <table> based layout
            rows = results_div_table.find_all('tr')[1:]
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 6:
                    subjects.append({
                        'subject_code': cells[0].get_text(strip=True),
                        'internal_marks': cells[2].get_text(strip=True),
                        'external_marks': cells[3].get_text(strip=True),
                        'total': cells[4].get_text(strip=True),
                        'result': cells[5].get_text(strip=True)
                    })

        if not subjects:
            print(f"[{usn}] No subjects found for {name_value}.")
            return None

        student_result = {
            'usn': usn_value,
            'student_name': name_value,
            'subjects': subjects
        }

        print(f"✅ Parsed: {name_value} ({usn_value}) — {len(subjects)} subjects.")
        return student_result

    except Exception as e:
        print(f"[{usn}] Error during parsing: {e}")
        return None

def fetch_vtu_results(usn_list, vtu_url):
    """
    Main function to orchestrate the scraping process with improved logic.
    """
    MAX_ATTEMPTS = 4
    all_results = []
    
    PROXY_LIST = [] 

    if not PROXY_LIST:
        print("\n[INFO] Scraping will proceed without proxies.\n")

    for i, usn in enumerate(usn_list):
        if i > 0:
            delay = random.uniform(5, 10)
            print(f"\n--- Pausing for {delay:.2f} seconds ---")
            time.sleep(delay)

        proxy = random.choice(PROXY_LIST) if PROXY_LIST else None
        driver = get_chromedriver_with_proxy(proxy)
        if not driver:
            print(f"Could not initialize driver for USN {usn}. Skipping.")
            continue

        was_successful = False
        for attempt in range(MAX_ATTEMPTS):
            try:
                print(f"\nFetching result for USN: {usn} (Attempt {attempt + 1}/{MAX_ATTEMPTS})...")
                driver.get(vtu_url)

                captcha_solution = solve_captcha(driver)
                if not captcha_solution:
                    print("Could not solve captcha. Retrying...")
                    time.sleep(2)
                    continue

                driver.find_element(By.NAME, 'lns').send_keys(usn)
                driver.find_element(By.NAME, 'captchacode').send_keys(captcha_solution)
                driver.find_element(By.ID, 'submit').click()
                time.sleep(3)
                
                try:
                    alert = driver.switch_to.alert
                    alert_text = alert.text
                    print(f"Alert received for {usn}: '{alert_text}'. Retrying...")
                    alert.accept()
                    continue
                except Exception:
                    pass

                page_source = driver.page_source
                if "Invalid captcha code" in page_source:
                    print(f"Page source indicates invalid CAPTCHA for {usn}. Retrying...")
                    continue
                
                result_data = parse_result_html(page_source, usn)
                if result_data:
                    all_results.append(result_data)
                    print(f"Successfully fetched and parsed result for {usn}")
                    was_successful = True
                    break
                else:
                    print(f"Parsing failed or no valid data found for {usn}. Moving on.")
                    was_successful = True
                    break
            
            except Exception as e:
                print(f"A critical error on attempt {attempt + 1} for {usn}: {e}. Retrying...")
                time.sleep(2)
        
        if not was_successful:
            print(f"--- FAILED to fetch result for {usn} after {MAX_ATTEMPTS} attempts. ---")
            
        driver.quit()

    return all_results