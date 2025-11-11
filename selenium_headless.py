import logging
import os
import sys
import time
import pandas as pd
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ==========================================
# LOGGING SETUP
# ==========================================
logging.basicConfig(
    filename='selenium_debug.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logging.info("=== Starting MoEngage Headless Scraper ===")

# ==========================================
# CONFIGURATION
# ==========================================
MOENGAGE_URL = "https://dashboard-03.moengage.com/"
SMS_CREATE_BASE_URL = "https://dashboard-03.moengage.com/v4/#/sms/create?type=one-time&draftId="

USERNAME = os.getenv("MOENGAGE_EMAIL", "").strip()
PASSWORD = os.getenv("MOENGAGE_PASSWORD", "").strip()
WORKSPACE = os.getenv("WORKSPACE", "Collections_TC").strip()
DRAFT_IDS = [d.strip() for d in os.getenv("DRAFT_IDS", "").split(",") if d.strip()]
OTP_CODE = os.getenv("OTP_CODE", "").strip()  # Step 3: OTP
OUTPUT_FILE = f"{WORKSPACE}_campaigns_headless.csv"

if not USERNAME or not PASSWORD or not DRAFT_IDS:
    logging.error("Missing credentials or draft IDs. Please check environment variables.")
    sys.exit(1)

logging.info(f"Workspace: {WORKSPACE}")
logging.info(f"Draft IDs: {DRAFT_IDS}")

# ==========================================
# CHROME OPTIONS — HEADLESS
# ==========================================
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("--disable-software-rasterizer")
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("--no-proxy-server")
chrome_options.add_argument("--ignore-certificate-errors")
chrome_options.add_argument("--log-level=3")

try:
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 20)
    logging.info("Chrome headless started successfully.")
except Exception as e:
    logging.error(f"Failed to start Chrome: {e}")
    sys.exit(1)

# ==========================================
# INTERNET CHECK
# ==========================================
try:
    r = requests.get("https://www.google.com", timeout=10)
    logging.info(f"Internet OK ({r.status_code})")
except Exception as e:
    logging.warning(f"Internet check failed: {e}")

# ==========================================
# SAFE ELEMENT FETCHER
# ==========================================
def safe_get(xpath, attr=None, retries=3, delay=2):
    for _ in range(retries):
        try:
            elem = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
            if attr:
                return elem.get_attribute(attr) or "N/A"
            text = elem.text.strip()
            return text if text else elem.get_attribute("value") or "N/A"
        except Exception:
            time.sleep(delay)
    return "N/A"

# ==========================================
# LOGIN PROCESS + OTP VERIFICATION
# ==========================================
login_status = "Failed"

def login():
    global login_status
    logging.info("Attempting login...")
    try:
        driver.get(MOENGAGE_URL)
        wait.until(EC.visibility_of_element_located((By.ID, "email"))).send_keys(USERNAME)
        driver.find_element(By.ID, "password").send_keys(PASSWORD)
        driver.find_element(By.ID, "password").send_keys(Keys.RETURN)
        time.sleep(5)

        # Step 3: OTP verification (if provided)
        if OTP_CODE:
            try:
                otp_input = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[@id='otp_code']")))  # Replace XPath if needed
                otp_input.send_keys(OTP_CODE)
                otp_input.send_keys(Keys.RETURN)
                time.sleep(5)
                logging.info("OTP verified successfully.")
            except Exception as e:
                logging.warning(f"OTP input failed or skipped: {e}")

        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        logging.info("Login successful.")
        login_status = "Success"
        print("Login successful!")
    except Exception as e:
        logging.error(f"Login failed: {e}")
        login_status = f"Failed: {e}"
        driver.quit()
        sys.exit(1)

login()

# ==========================================
# SCRAPE DRAFTS
# ==========================================
results = []

for draft_id in DRAFT_IDS:
    logging.info(f"Opening Draft: {draft_id}")
    url = f"{SMS_CREATE_BASE_URL}{draft_id}"
    try:
        driver.get(url)
        time.sleep(5)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
    except Exception as e:
        logging.error(f"Failed to open draft {draft_id}: {e}")
        results.append({
            "Draft ID": draft_id,
            "Login Status": login_status,
            "Status": f"Failed to open: {e}",
            "Campaign Name": "N/A",
            "User Attribute": "N/A",
            "Campaign Tags": "N/A",
            "SMS Sender": "N/A",
            "Template ID": "N/A",
            "Message Body": "N/A"
        })
        continue

    data = {
        "Draft ID": draft_id,
        "Login Status": login_status,
        "Status": "Opened successfully",
        "Campaign Name": safe_get("//input[@placeholder='Campaign Name']", "value"),
        "User Attribute": safe_get("//span[@class='mds-dropdown__trigger__inner__single--value']"),
        "Campaign Tags": ", ".join([t.text.strip() for t in driver.find_elements(By.XPATH, "//div[@class='mds-input__input--tags__list--item']/span[1]")]) or "N/A",
        "SMS Sender": safe_get("//div[@placeholder='Select a connector']//span[@class='mds-dropdown__trigger__inner__single--value']"),
        "Template ID": safe_get("//input[@id='template_id']", "value"),
        "Message Body": safe_get("//div[@id='personalization_container']")
    }

    results.append(data)
    logging.info(f"Extracted draft: {draft_id}")

# ==========================================
# SAVE RESULTS
# ==========================================
if results:
    df = pd.DataFrame(results)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8")
    logging.info(f"Saved results to {OUTPUT_FILE}")
    print(f"Saved results to {OUTPUT_FILE}")
else:
    logging.warning("No data extracted — check login or draft IDs.")
    print("No data extracted — check login or draft IDs.")

driver.quit()
logging.info("Script completed successfully.")
print("Script completed successfully.")
