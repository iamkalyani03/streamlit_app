import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time, os, sys, requests

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
# CONFIGURATION (read from environment)
# ==========================================
MOENGAGE_URL = "https://dashboard-03.moengage.com/"
SMS_CREATE_BASE_URL = "https://dashboard-03.moengage.com/v4/#/sms/create?type=one-time&draftId="

USERNAME = os.getenv("MOENGAGE_EMAIL", "").strip()
PASSWORD = os.getenv("MOENGAGE_PASSWORD", "").strip()
WORKSPACE = os.getenv("WORKSPACE", "Collections_TC").strip()
DRAFT_IDS = [d.strip() for d in os.getenv("DRAFT_IDS", "").split(",") if d.strip()]
OUTPUT_FILE = f"{WORKSPACE}_campaigns_headless.csv"

if not USERNAME or not PASSWORD or not DRAFT_IDS:
    logging.error("Missing credentials or draft IDs. Please check environment variables.")
    sys.exit(1)

logging.info(f"Workspace: {WORKSPACE}")
logging.info(f"Draft IDs: {DRAFT_IDS}")

# ==========================================
# CHROME OPTIONS — HEADLESS CONFIG
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
    """Utility to safely get element text or attribute with retries."""
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
# LOGIN PROCESS
# ==========================================
def login():
    logging.info("Attempting login...")
    print(" Opening MoEngage login page...")
    try:
        driver.get(MOENGAGE_URL)
        wait.until(EC.visibility_of_element_located((By.ID, "email"))).send_keys(USERNAME)
        driver.find_element(By.ID, "password").send_keys(PASSWORD)
        driver.find_element(By.ID, "password").send_keys(Keys.RETURN)
        time.sleep(5)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        logging.info(" Login successful.")
        print(" Login successful on MoEngage!")
    except Exception as e:
        logging.error(f" Login failed: {e}")
        print(f" Login failed: {e}")
        driver.quit()
        sys.exit(1)

# Perform login
login()

# ==========================================
# SCRAPE EACH DRAFT
# ==========================================
results = []
for draft_id in DRAFT_IDS:
    logging.info(f"Opening Draft: {draft_id}")
    print(f" Opening draft ID: {draft_id}")
    url = f"{SMS_CREATE_BASE_URL}{draft_id}"
    try:
        driver.get(url)
        time.sleep(5)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
    except Exception as e:
        logging.error(f"Failed to open draft {draft_id}: {e}")
        print(f" Failed to open draft {draft_id}: {e}")
        results.append({"Draft ID": draft_id, "Status": f"Failed to open: {e}"})
        continue

    data = {"Draft ID": draft_id, "Status": "Opened successfully"}
    data["Campaign Name"] = safe_get("//input[@placeholder='Campaign Name']", "value")
    data["User Attribute"] = safe_get("//span[@class='mds-dropdown__trigger__inner__single--value']")
    data["Campaign Tags"] = ", ".join(
        [t.text.strip() for t in driver.find_elements(By.XPATH,
            "//div[@class='mds-input__input--tags__list--item']/span[1]")]
    ) or "N/A"
    data["SMS Sender"] = safe_get("//div[@placeholder='Select a connector']//span[@class='mds-dropdown__trigger__inner__single--value']")
    data["Template ID"] = safe_get("//input[@id='template_id']", "value")
    data["Message Body"] = safe_get("//div[@id='personalization_container']")

    results.append(data)
    logging.info(f" Extracted draft: {draft_id}")
    print(f" Extracted draft ID: {draft_id}")

# ==========================================
# SAVE RESULTS
# ==========================================
if results:
    df = pd.DataFrame(results)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8")
    logging.info(f"Saved results to {OUTPUT_FILE}")
    print(f" Saved results to {OUTPUT_FILE}")
else:
    logging.warning("No data extracted — check login or draft IDs.")
    print(" No data extracted — check login or draft IDs.")

driver.quit()
logging.info("Script completed successfully.")
print(" Script completed successfully.")
