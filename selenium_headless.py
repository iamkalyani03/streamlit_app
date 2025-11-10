from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time

# ==========================================
# CONFIGURATION
# ==========================================
MOENGAGE_URL = "https://dashboard-03.moengage.com/"
SMS_CREATE_BASE_URL = "https://dashboard-03.moengage.com/v4/#/sms/create?type=one-time&draftId="
USERNAME = "sahil@0101.today"       # Replace with your MoEngage email
PASSWORD = "Patson@0101"            # Replace with your MoEngage password
WORKSPACE = "Collections_TC"        # Your MoEngage workspace name

DRAFT_IDS = [
    "68885b612a3c4eb3c36713cd"
]  # Add more draft IDs if needed

OUTPUT_FILE = f"{WORKSPACE}_campaigns_headless.csv"

# ==========================================
# CHROME SETUP — HEADLESS STABLE
# ==========================================
chrome_options = Options()
chrome_options.add_argument("--headless=new")                # modern headless
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("--disable-software-rasterizer")  # prevents renderer crash
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option("useAutomationExtension", False)
chrome_options.add_argument("--remote-debugging-port=9222")  # optional but stabilizes headless

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
wait = WebDriverWait(driver, 10)

# ==========================================
# HELPER FUNCTION
# ==========================================
def safe_get(xpath, attr=None, retries=3, delay=2):
    """Safe getter with retries"""
    for _ in range(retries):
        try:
            elem = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
            if attr:
                return elem.get_attribute(attr) or "N/A"
            text = elem.text.strip()
            return text if text else elem.get_attribute("value") or "N/A"
        except:
            time.sleep(delay)
    return "N/A"

# ==========================================
# LOGIN PROCESS
# ==========================================
print("Logging into MoEngage...")
driver.get(MOENGAGE_URL)

try:
    wait.until(EC.visibility_of_element_located((By.ID, "email"))).send_keys(USERNAME)
    driver.find_element(By.ID, "password").send_keys(PASSWORD)
    driver.find_element(By.ID, "password").send_keys(Keys.RETURN)
    print("Credentials submitted. Waiting for dashboard...")
    time.sleep(6)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    print(" Logged in successfully!\n")
except Exception as e:
    print(f" Login failed: {e}")
    driver.quit()
    exit()

# ==========================================
# OPEN DRAFT LINKS & EXTRACT DATA
# ==========================================
results = []

for draft_id in DRAFT_IDS:
    print(f" Opening Draft: {draft_id}")
    url = f"{SMS_CREATE_BASE_URL}{draft_id}"

    try:
        driver.get(url)
        time.sleep(5)  # allow JS to render
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")  # force lazy-load
        time.sleep(2)
    except Exception as e:
        print(f" Failed to load draft {draft_id}: {e}")
        results.append({"Draft ID": draft_id, "Status": f"Failed to load: {e}"})
        continue

    data = {"Draft ID": draft_id, "Status": "Opened successfully"}

    # ---------- TARGET USERS ----------
    data["Campaign Name"] = safe_get("//input[@placeholder='Campaign Name']", "value")
    data["User Attribute"] = safe_get("//span[@class='mds-dropdown__trigger__inner__single--value']")

    try:
        tags = driver.find_elements(By.XPATH, "//div[@class='mds-input__input--tags__list--item']/span[1]")
        data["Campaign Tags"] = ", ".join([t.text.strip() for t in tags]) if tags else "N/A"
    except:
        data["Campaign Tags"] = "N/A"

    # ---------- CONTENT ----------
    try:
        content_tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[contains(text(),'Content')]")))
        driver.execute_script("arguments[0].click();", content_tab)
        time.sleep(2)
    except:
        pass

    data["SMS Sender"] = safe_get("//div[@placeholder='Select a connector']//span[@class='mds-dropdown__trigger__inner--single--value']")
    data["Template ID"] = safe_get("//input[@id='template_id']", "value")
    data["Message Body"] = safe_get("//div[@id='personalization_container']")

    # ---------- SCHEDULE ----------
    try:
        schedule_tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[contains(text(),'Schedule and goals')]")))
        driver.execute_script("arguments[0].click();", schedule_tab)
        time.sleep(2)
    except:
        pass

    data["Send Campaign Toggle"] = safe_get("//input[@name='gCampaignType' and @checked]", "id")
    data["Start Date"] = safe_get("//input[@placeholder='Select date']", "value")
    data["Conversion Goals"] = safe_get("//div[@class='mds-cg']//div[contains(@class,'mds-cg__section')]")
    data["Request Limit"] = safe_get("//input[@placeholder='Requests per/min...']", "value")

    results.append(data)
    print(f" Extracted data for draft {draft_id}")

# ==========================================
# SAVE RESULTS TO CSV
# ==========================================
if results:
    df = pd.DataFrame(results)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8")
    print(f"\n All data saved to: {OUTPUT_FILE}")
else:
    print(" No data extracted — check your draft IDs or login.")

driver.quit()
print(" Script finished successfully.")
