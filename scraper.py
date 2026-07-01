# scraper.py (v2 — Lightweight requests + ddddocr captcha solver)

import time
import re
import io
import random
import warnings
import threading
import concurrent.futures
import requests
import urllib3
from PIL import Image, ImageFilter
import numpy as np
from bs4 import BeautifulSoup
import ddddocr

from db import get_cached_result, save_cached_result, init_db

import sys
import builtins

def force_print(*args, **kwargs):
    kwargs['file'] = sys.stderr
    kwargs['flush'] = True
    builtins.print(*args, **kwargs)

print = force_print
# Initialize database
init_db()

# VTU's SSL cert is misconfigured — suppress the warning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Initialize the captcha solver (once, globally) ---
ocr = ddddocr.DdddOcr(beta=True, show_ad=False)

# --- Browser-like headers to avoid being flagged ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

class SessionPool:
    """Manages a pool of independent requests.Session objects to prevent VTU PHPSESSID collisions."""
    def __init__(self, size=5):
        self.sessions = [requests.Session() for _ in range(size)]
        self.lock = threading.Lock()
        self.index = 0

    def get_session(self):
        with self.lock:
            session = self.sessions[self.index]
            self.index = (self.index + 1) % len(self.sessions)
            return session


class CaptchaEvolver:
    """
    Manages and scores different image preprocessing strategies.
    Promotes successful strategies to the top to adapt to VTU's changing captchas.
    """
    def __init__(self):
        # Define strategies: (filter_size, threshold)
        self.strategies = [
            {'name': 'raw', 'filter': None, 'thresh': None}, # Strategy 0: Raw image
            {'name': 'med3_thresh140', 'filter': 3, 'thresh': 140},
            {'name': 'med3_thresh160', 'filter': 3, 'thresh': 160},
            {'name': 'med5_thresh130', 'filter': 5, 'thresh': 130},
            {'name': 'thresh_only150', 'filter': None, 'thresh': 150}
        ]
        # Track success rates: {strategy_name: success_count}
        self.success_counts = {s['name']: 0 for s in self.strategies}
        self.current_order = list(self.strategies) # Initially in defined order
        
    def report_success(self, strategy_name):
        self.success_counts[strategy_name] += 1
        # Re-sort current_order based on success count (highest first)
        self.current_order.sort(key=lambda s: self.success_counts[s['name']], reverse=True)
        # print(f"[EVOLVER] Promoted strategy '{strategy_name}'. Current order: {[s['name'] for s in self.current_order]}")

    def apply_strategy(self, image_bytes, strategy):
        if strategy['name'] == 'raw':
            return image_bytes
            
        try:
            img = Image.open(io.BytesIO(image_bytes)).convert('L')
            
            if strategy['filter']:
                img = img.filter(ImageFilter.MedianFilter(size=strategy['filter']))
                
            img_array = np.array(img)
            
            if strategy['thresh']:
                img_array = np.where(img_array < strategy['thresh'], 0, 255).astype(np.uint8)
                
            clean_img = Image.fromarray(img_array)
            output = io.BytesIO()
            clean_img.save(output, format='PNG')
            return output.getvalue()
        except Exception as e:
            # print(f"[WARN] Strategy {strategy['name']} failed: {e}")
            return image_bytes

# Global evolver instance
evolver = CaptchaEvolver()

def solve_captcha(image_bytes):
    """
    Solve a captcha image using ddddocr with adaptive preprocessing.
    Returns (solution, strategy_used) or (None, None).
    """
    for strategy in evolver.current_order:
        try:
            processed_bytes = evolver.apply_strategy(image_bytes, strategy)
            result = ocr.classification(processed_bytes)
            cleaned = re.sub(r'[^a-zA-Z0-9]', '', result)
            
            if cleaned and len(cleaned) == 6:
                print(f"[ddddocr] [{strategy['name']}]: '{result}' -> Cleaned: '{cleaned}'")
                return cleaned, strategy['name']
                
        except Exception as e:
            print(f"❌ Error applying strategy {strategy['name']}: {e}")
            continue
            
    print(f"[WARN] Captcha solver exhausted all {len(evolver.strategies)} strategies. Failed.")
    return None, None


def parse_result_html(html_content, usn):
    """
    Parses VTU result HTML page using a robust Header-Anchored approach.
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    # --- Handle invalid or unavailable results ---
    if re.search(r'Invalid USN|Results are not yet available', html_content, re.I):
        print(f"[{usn}] Invalid USN or results not available.")
        return None

    try:
        # --- Flexible extraction for USN and Name ---
        usn_value = None
        name_value = None
        
        # We look for text nodes containing "University Seat Number" or "USN"
        for tag in soup.find_all(string=re.compile(r'University Seat Number|USN', re.I)):
            container = tag.find_parent(['td', 'div'])
            if container:
                next_node = container.find_next_sibling(['td', 'div'])
                if next_node:
                    usn_value = re.sub(r'[:\s]+', '', next_node.get_text(strip=True)).upper()
                    break
                
        for tag in soup.find_all(string=re.compile(r'Student Name', re.I)):
            container = tag.find_parent(['td', 'div'])
            if container:
                next_node = container.find_next_sibling(['td', 'div'])
                if next_node:
                    name_value = re.sub(r'^[:\s]+', '', next_node.get_text(strip=True)).title()
                    break

        if not usn_value or not name_value:
            if not usn_value: usn_value = usn # Fallback
            if not name_value: name_value = "Unknown Name"

        # --- Header-Anchored Parsing for Subjects ---
        subjects = []
        
        # 1. Find the container (table or div) that has the headers
        results_container = None
        header_row = None
        
        for container in soup.find_all(['div', 'table']):
            if 'Subject Code' in container.get_text():
                if container.name == 'table':
                    header_row = container.find(lambda tag: tag.name == 'tr' and 'Subject Code' in tag.get_text())
                    if header_row:
                        results_container = container
                        break
                elif container.name == 'div' and 'divTable' in container.get('class', []):
                    header_row = container.find(lambda tag: tag.name == 'div' and 'Subject Code' in tag.get_text() and ('TableRow' in ''.join(tag.get('class', [])) or 'TableRow' in str(tag.get('class', []))))
                    if header_row:
                        results_container = container
                        break

        if not results_container or not header_row:
            with open(f"failed_subjects_{usn}.html", "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"[{usn}] Result table or header row not found. Saved HTML to failed_subjects_{usn}.html")
            return None

        # 2. Extract Data Rows by looking at siblings of the header row
        current_row = header_row.find_next_sibling()
        
        while current_row:
            if current_row.name == 'tr':
                cells = current_row.find_all('td')
            else:
                # For div layout, grab direct div children or fallback to divTableCell
                cells = [c for c in current_row.find_all('div', recursive=False)]
                if not cells:
                    cells = current_row.find_all('div', class_='divTableCell')

            if len(cells) >= 6:
                subjects.append({
                    'subject_code': cells[0].get_text(strip=True),
                    'internal_marks': cells[2].get_text(strip=True),
                    'external_marks': cells[3].get_text(strip=True),
                    'total': cells[4].get_text(strip=True),
                    'result': cells[5].get_text(strip=True)
                })
            
            current_row = current_row.find_next_sibling()

        if not subjects:
            with open(f"failed_subjects_{usn}.html", "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"[{usn}] No subjects found for {name_value}. Saved HTML to failed_subjects_{usn}.html")
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


def fetch_single_result(session, vtu_url, usn, max_attempts=25, job_state=None):
    """
    Fetch a single USN result using HTTP requests + ddddocr captcha solving.
    Returns parsed result dict or None.
    """
    # Determine the base URL for the captcha image
    # VTU captcha is usually at the same directory level as the results page
    base_url = vtu_url.rsplit('/', 1)[0]
    captcha_url = f"{base_url}/captcha/vtu_captcha.php"
    
    for attempt in range(max_attempts):
        try:
            # Add micro-jitter delay to offset concurrent requests
            if attempt > 0:
                time.sleep(random.uniform(0.5, 1.5))
            else:
                time.sleep(random.uniform(0.1, 0.5))
                
            print(f"\n[FETCH] {usn} (Attempt {attempt + 1}/{max_attempts})...")
            if job_state:
                job_state['progress'] = f"Solving captcha for {usn} (Attempt {attempt + 1}/{max_attempts})..."
            
            # Step 1: GET the results page to establish session
            page_response = session.get(vtu_url, headers=HEADERS, timeout=15, verify=False)
            page_response.raise_for_status()
            
            # Step 2: Find the captcha image URL and hidden Token from the page
            soup = BeautifulSoup(page_response.text, 'html.parser')
            
            token_input = soup.find('input', {'name': 'Token'})
            token = token_input.get('value', '') if token_input else ''
            
            captcha_img = soup.find('img', src=re.compile(r'captcha', re.I))
            
            if captcha_img:
                captcha_src = captcha_img.get('src', '')
                # Handle relative URLs
                if captcha_src.startswith('http'):
                    actual_captcha_url = captcha_src
                elif captcha_src.startswith('/'):
                    # Absolute path from domain root
                    from urllib.parse import urlparse
                    parsed = urlparse(vtu_url)
                    actual_captcha_url = f"{parsed.scheme}://{parsed.netloc}{captcha_src}"
                else:
                    actual_captcha_url = f"{base_url}/{captcha_src}"
            else:
                actual_captcha_url = captcha_url
            
            # Step 3: Download the captcha image
            captcha_response = session.get(actual_captcha_url, headers={
                **HEADERS,
                'Referer': vtu_url,
            }, timeout=10, verify=False)
            captcha_response.raise_for_status()
            
            captcha_bytes = captcha_response.content
            
            # Step 4: Solve the captcha
            captcha_solution, strategy_used = solve_captcha(captcha_bytes)
            if not captcha_solution:
                print(f"[WARN] Could not solve captcha for {usn}. Retrying...")
                time.sleep(0.5)
                continue
            
            # Step 5: Find the form action URL
            form = soup.find('form')
            if form:
                action = form.get('action', '')
                if action and not action.startswith('http'):
                    post_url = f"{base_url}/{action.lstrip('/')}"
                elif action:
                    post_url = action
                else:
                    post_url = vtu_url
            else:
                post_url = vtu_url
            
            # Step 6: Submit the form via POST
            form_data = {
                'Token': token,
                'lns': usn,
                'captchacode': captcha_solution,
                'submit': 'Submit',
            }
            
            if job_state:
                job_state['progress'] = f"Submitting form for {usn}..."
            
            result_response = session.post(post_url, data=form_data, headers={
                **HEADERS,
                'Referer': vtu_url,
                'Content-Type': 'application/x-www-form-urlencoded',
            }, timeout=15, verify=False)
            result_response.raise_for_status()
            
            result_html = result_response.text
            
            # Step 7: Check for captcha errors
            if 'Invalid captcha code' in result_html or 'invalid captcha' in result_html.lower():
                print(f"[ERROR] Invalid captcha for {usn}. Retrying...")
                time.sleep(random.uniform(2.0, 3.5))  # Brief pause before next attempt to avoid rate-limiting
                continue
            
            # --- CAPTCHA SUCCESS! ---
            evolver.report_success(strategy_used)
            
            # Step 8: Parse the result
            if job_state:
                job_state['progress'] = f"Parsing results for {usn}..."
            
            result_data = parse_result_html(result_html, usn)
            if result_data:
                return result_data
            else:
                # If parse failed but no captcha error, the USN might be invalid — stop retrying
                print(f"[{usn}] Parsing failed — USN may be invalid or results not available.")
                return None
                
        except requests.exceptions.Timeout:
            print(f"[TIMEOUT] for {usn} on attempt {attempt + 1}. Retrying...")
            time.sleep(1)
        except requests.exceptions.RequestException as e:
            print(f"[NETWORK ERROR] Request error for {usn}: {e}. Retrying...")
            time.sleep(1)
        except Exception as e:
            print(f"[ERROR] Unexpected error for {usn}: {e}. Retrying...")
            time.sleep(1)
    
    print(f"--- FAILED to fetch result for {usn} after {max_attempts} attempts. ---")
    return None


def fetch_vtu_results(usn_list, vtu_url, job_state=None):
    """
    Main function to orchestrate the scraping process.
    Uses multi-threading + session multiplexing + micro-jitters for smart concurrency without proxies.
    """
    MAX_ATTEMPTS = 10
    all_results = []
    total_usns = len(usn_list)
    failed_usns = []
    
    print(f"\n[INFO] Starting concurrent scrape for {total_usns} USNs using requests + ddddocr.\n")
    
    # Thread-safe components
    session_pool = SessionPool(size=3)
    results_lock = threading.Lock()
    failed_lock = threading.Lock()
        
    def process_usn(usn, i):
        if job_state:
            job_state['progress'] = f"Processing USN {usn}..."
            job_state['current_usn'] = usn
        
        # Check Cache First
        cached_data = get_cached_result(usn, vtu_url)
        if cached_data:
            with results_lock:
                all_results.append(cached_data)
                if job_state: 
                    job_state['completed'] += 1
            print(f"[CACHE HIT] Instantly loaded {usn}")
            return
            
        session = session_pool.get_session()
        result = fetch_single_result(session, vtu_url, usn, MAX_ATTEMPTS, job_state)
        
        if result:
            with results_lock:
                all_results.append(result)
                if job_state: 
                    job_state['completed'] += 1
            save_cached_result(usn, vtu_url, result) # Save to database
            print(f"[SUCCESS] Fetched {usn}")
        else:
            print(f"[FAILED] Failed to fetch {usn} on first pass.")
            with failed_lock:
                failed_usns.append(usn)

    # Launch threads (Max 3 to avoid instant IP ban without proxies)
    MAX_WORKERS = 3
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for i, usn in enumerate(usn_list):
            futures.append(executor.submit(process_usn, usn, i))
        
        # Wait for first pass to complete
        concurrent.futures.wait(futures)

    # --- SECOND PASS (For the stubborn captchas) ---
    if failed_usns:
        print(f"\n[INFO] Doing a second pass for {len(failed_usns)} failed USNs sequentially with higher retry limit...\n")
        time.sleep(3) # Let the server breathe before hitting it again
        
        for j, usn in enumerate(failed_usns):
            if job_state:
                job_state['progress'] = f"Retry pass for failed USN {usn} ({j + 1}/{len(failed_usns)})"
                job_state['current_usn'] = usn
            
            time.sleep(random.uniform(2, 4))
                
            session = session_pool.get_session()
            result = fetch_single_result(session, vtu_url, usn, max_attempts=30, job_state=job_state)
            if result:
                all_results.append(result)
                save_cached_result(usn, vtu_url, result)
                print(f"[SUCCESS] Fetched {usn} on second pass!")
            else:
                print(f"[SKIP] Permanently skipped {usn}. May be invalid USN.")
            if job_state: 
                job_state['completed'] += 1
    
    # Sort results by USN to keep them in order
    all_results.sort(key=lambda x: x['usn'])
    
    print(f"\n[DONE] Fetched {len(all_results)}/{total_usns} results.\n")
    return all_results