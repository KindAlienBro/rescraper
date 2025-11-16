# proxy_checker.py (Final Recommended Version)

import requests
import concurrent.futures
from tqdm import tqdm # Import tqdm for the progress bar

# --- CONFIGURATION ---
PROXY_SOURCES = [
    'https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt',
    'https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text',
    'https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt',
    'https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks4.txt',
    'https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-https.txt',
    'https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt',
]

OUTPUT_FILE = 'working_proxies.txt'
TEST_URL = 'https://httpbin.org/ip' # Using HTTPS is a slightly better test

# --- TUNING PARAMETERS ---
TIMEOUT = 5 # Don't wait more than 5 seconds for a proxy.
MAX_WORKERS = 100 # Increased for faster checking, adjust based on your network.

# --- IMPROVEMENT: Add a common browser User-Agent ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def fetch_proxies():
    """Fetches proxies from all sources and returns a unique list."""
    all_proxies = set()
    for url in PROXY_SOURCES:
        try:
            print(f"Fetching proxies from: {url}")
            response = requests.get(url, timeout=15, headers=HEADERS)
            response.raise_for_status()
            
            proxies = response.text.strip().split('\n')
            
            # Determine protocol based on URL content if not explicitly provided
            protocol = 'http' # Default
            if 'socks5' in url: protocol = 'socks5'
            elif 'socks4' in url: protocol = 'socks4'
            elif 'https' in url: protocol = 'https'

            for p in proxies:
                p = p.strip()
                if not p: continue
                # Handle proxies that already include the protocol
                if '://' in p:
                    all_proxies.add(p)
                else:
                    all_proxies.add(f"{protocol}://{p}")
        except Exception as e:
            print(f"Failed to fetch or parse from {url}: {e}")
    return list(all_proxies)

def check_proxy(proxy):
    """
    Checks a single proxy. Returns the proxy string if working, else None.
    CRITICAL: Requires 'pip install requests[socks]' to test SOCKS proxies.
    """
    proxy = proxy.strip()
    proxies = {'http': proxy, 'https': proxy}
    try:
        # Make the request using the proxy and the custom user-agent
        response = requests.get(TEST_URL, proxies=proxies, timeout=TIMEOUT, headers=HEADERS)
        if response.status_code == 200:
            return proxy # Success
    except Exception:
        pass # Any exception means the proxy has failed
    return None

def main():
    """Main function to orchestrate fetching, checking, and saving."""
    print("--- Starting Proxy Fetch and Check ---")
    
    # CRITICAL: Remind user to install SOCKS support
    try:
        import socks
    except ImportError:
        print("\n[WARNING] PySocks is not installed. SOCKS proxies cannot be checked.")
        print("Please run: pip install 'requests[socks]'\n")

    proxies_to_check = fetch_proxies()
    if not proxies_to_check:
        print("Could not fetch any proxies. Exiting.")
        return

    print(f"\nFetched {len(proxies_to_check)} unique proxies. Now testing with a {TIMEOUT}s timeout...")
    working_proxies = []
    
    # Using ThreadPoolExecutor for concurrent checking
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Create a future for each proxy check
        future_to_proxy = {executor.submit(check_proxy, p): p for p in proxies_to_check}
        
        # Use tqdm to create a progress bar
        for future in tqdm(concurrent.futures.as_completed(future_to_proxy), total=len(proxies_to_check), desc="Checking Proxies"):
            result = future.result()
            if result:
                working_proxies.append(result)

    print(f"\n--- Check Complete ---")
    print(f"Found {len(working_proxies)} working proxies.")

    if working_proxies:
        with open(OUTPUT_FILE, 'w') as f:
            for proxy in working_proxies:
                f.write(f"{proxy}\n")
        print(f"Successfully saved working proxies to '{OUTPUT_FILE}'.")
        print("You can now copy the contents of this file into the PROXY_LIST in scraper.py")
    else:
        print("\nWARNING: No working proxies were found. The parallel scraper will be ineffective.")

if __name__ == "__main__":
    main()