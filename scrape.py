# FileName: MultipleFiles/scrape.py
from playwright.sync_api import sync_playwright, TimeoutError
import time
from datetime import datetime
import pandas as pd
import streamlit as st # Keep streamlit import for logging/feedback within the subprocess if needed, though app.py handles main UI
import os
import re # Import re for regex operations
import sys # Import sys to access command-line arguments
from playwright_stealth import stealth_sync

# --- Constants ---
MOENGAGE_BASE_URL = "https://dashboard-03.moengage.com/v4/#/sms/create?type=one-time&draftId="
MESSAGE_BODY_CHAR_LIMIT = 4096
# CDP_URL = "http://localhost:9222" # Not directly used for launching, but good to keep in mind for debug mode

# --- Global Playwright and Browser Context (managed by context manager in attach_and_login) ---
_playwright_instance = None
_browser_context_instance = None

def add_validations(all_data):
    """
    Adds validation columns and messages for each campaign.
    """
    for d in all_data:
        target = d.get("Target Users", {})
        content = d.get("Content", {})
        schedule = d.get("Schedule and Goals", {})

        # -------------------- Target Users --------------------
        # Campaign Name
        target["Campaign Name Validation"] = bool(target.get("Campaign Name") and target["Campaign Name"] != "N/A")
        target["Campaign Name Message"] = "" if target["Campaign Name Validation"] else "Campaign Name is missing"

        # User Attributes
        target["User Attribute Validation"] = bool(target.get("User Attribute") and target["User Attribute"] != "N/A")
        target["User Attribute Message"] = "" if target["User Attribute Validation"] else "User Attribute is missing"

        # Campaign Tags
        target["Campaign Tags Validation"] = bool(target.get("Campaign Tags") and target["Campaign Tags"] != "N/A")
        target["Campaign Tags Message"] = "" if target["Campaign Tags Validation"] else "Campaign Tags are missing"

        # Message Type
        target["Message Type Validation"] = True
        target["Message Type Message"] = ""

        # Audience Selection
        aud_sel = target.get("Audience Selection", "")
        if not aud_sel or aud_sel == "N/A":
            target["Audience Selection Validation"] = False
            target["Audience Selection Message"] = "Audience selection missing"
        elif "All Users" in aud_sel:
            target["Audience Selection Validation"] = False
            target["Audience Selection Message"] = "Audience set to All Users (usually not desired for targeted campaigns)"
        else:
            target["Audience Selection Validation"] = True
            target["Audience Selection Message"] = ""

        # Exclude User
        target["Exclude User Validation"] = True
        target["Exclude User Message"] = ""

        # User Opted Out Toggle
        target["User Opted Out Toggle Validation"] = True
        target["User Opted Out Toggle Message"] = ""

        # Audience Limit Toggle
        target["Audience Limit Toggle Validation"] = True
        target["Audience Limit Toggle Message"] = ""

        # Control Group Toggle
        target["Control Group Toggle Validation"] = True
        target["Control Group Toggle Message"] = ""

        # -------------------- Content --------------------
        # SMS Sender
        content["SMS Sender Validation"] = bool(content.get("SMS Sender") and content["SMS Sender"] != "N/A")
        content["SMS Sender Message"] = "" if content["SMS Sender Validation"] else "SMS Sender missing"

        # Template ID
        content["Template ID Validation"] = bool(content.get("Template ID") and content["Template ID"] != "N/A")
        content["Template ID Message"] = "" if content["Template ID Validation"] else "Template ID missing"

        # Message Body
        msg = content.get("Message Body", "")
        msg_valid = True
        msg_message = ""

        if not msg or msg == "N/A":
            msg_valid = False
            msg_message = "Message body is missing"
        else:
            # Check character limit
            if len(msg) > MESSAGE_BODY_CHAR_LIMIT:
                msg_valid = False
                msg_message = f"Message exceeds character limit of {MESSAGE_BODY_CHAR_LIMIT}"

            # Check for link presence (basic check)
            url_pattern = r"https?://\S+"
            if not re.search(url_pattern, msg):
                msg_valid = False
                msg_message = "Message link missing or invalid (requires http/https URL)"

        content["Message Validation"] = msg_valid
        content["Message Message"] = msg_message

        # -------------------- Schedule and Goals --------------------
        # Send Campaign Toggle
        send_toggle = schedule.get("Send Campaign Toggle", "")
        if send_toggle.lower() == "as soon as possible":
            schedule["Send Campaign Toggle Validation"] = False
            schedule["Send Campaign Toggle Message"] = "Send Campaign set to 'As soon as possible' (might not be desired for scheduled campaigns)"
        else:
            schedule["Send Campaign Toggle Validation"] = True
            schedule["Send Campaign Toggle Message"] = ""

        # Date & Time
        schedule["Date & Time Validation"] = bool(schedule.get("Scheduled Datetime") and schedule["Scheduled Datetime"] != "N/A")
        schedule["Date & Time Message"] = "" if schedule["Date & Time Validation"] else "Scheduled Date & Time is missing or invalid"

        # Conversion Goal
        schedule["Conversion Goal Validation"] = bool(schedule.get("Conversion Goals") and schedule["Conversion Goals"] != "N/A")
        schedule["Conversion Goal Message"] = "" if schedule["Conversion Goal Validation"] else "Conversion Goal is missing"

        # Frequency Cap Toggle
        schedule["Frequency Cap Toggle Validation"] = True
        schedule["Frequency Cap Toggle Message"] = ""

        # Request Limit
        schedule["Request Limit Validation"] = bool(schedule.get("Request Limit") is not None)
        schedule["Request Limit Message"] = "" if schedule["Request Limit Validation"] else "Request Limit is missing"

    return all_data


def flatten_campaign_data_with_single_message(all_data):
    flat = []
    for d in all_data:
        row = {"Draft ID": d["Draft ID"]}

        # -------------------- 1. Extract all data columns --------------------
        # Target Users
        target = d.get("Target Users", {})
        target_cols = ["Campaign Name", "User Attribute", "Campaign Tags", "Message Type",
                       "Audience Selection", "Exclude User", "User Opted Out Toggle",
                       "Audience Limit Toggle", "Control Group Toggle"]
        for col in target_cols:
            row[col] = target.get(col, "N/A")

        # Content
        content = d.get("Content", {})
        content_cols = ["SMS Sender", "Template ID", "Message Body"]
        for col in content_cols:
            row[col] = content.get(col, "N/A")

        # Schedule and Goals
        sched = d.get("Schedule and Goals", {})
        sched_cols = ["Send Campaign Toggle", "Start Date", "Send Time",
                      "Scheduled Datetime", "Conversion Goals", "Frequency Cap Toggle",
                      "Request Limit"]
        for col in sched_cols:
            row[col] = sched.get(col, "N/A")

        # -------------------- 2. Combine all validation messages into one column --------------------
        validation_messages = []

        # Target Users validations
        for key, msg in target.items():
            if key.endswith("Message") and msg:
                validation_messages.append(msg)

        # Content validations
        for key, msg in content.items():
            if key.endswith("Message") and msg:
                validation_messages.append(msg)

        # Schedule validations
        for key, msg in sched.items():
            if key.endswith("Message") and msg:
                validation_messages.append(msg)

        row["Validation Message"] = " | ".join(validation_messages) if validation_messages else ""

        # -------------------- 3. Add all dedicated validation columns --------------------
        # Target Users validations
        for key, val in target.items():
            if key.endswith("Validation"):
                row[key] = val

        # Content validations
        for key, val in content.items():
            if key.endswith("Validation"):
                row[key] = val

        # Schedule validations
        for key, val in sched.items():
            if key.endswith("Validation"):
                row[key] = val

        flat.append(row)
    return flat


def process_campaigns(context, draft_ids):
    all_data = []
    skipped_campaigns = []

    for draft_id in draft_ids:
        url = MOENGAGE_BASE_URL + draft_id
        print(f" Opening {url} in a new tab...") # Use print for subprocess output

        page = None
        try:
            page = context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_load_state("networkidle")
            except Exception:
                print(f" Campaign {draft_id} could not be opened (timeout/redirect). Skipping...")
                skipped_campaigns.append(draft_id)
                continue

            # Quick check: is this actually a valid campaign page?
            try:
                page.wait_for_selector(
                    "//div[contains(@class,'mds-segmentation__section')]",
                    timeout=5000
                )
                print(f" Campaign {draft_id} loaded successfully.")
            except Exception:
                print(f" Campaign {draft_id} not found or not in Drafts anymore. Skipping...")
                skipped_campaigns.append(draft_id)
                continue

            data = {"Draft ID": draft_id}
            target_users = {}

            # --- Target Users section ---
            try:
                target_users["Campaign Name"] = page.input_value("//input[@placeholder='Campaign Name']")
            except:
                target_users["Campaign Name"] = "N/A"

            # User Attribute
            try:
                target_users["User Attribute"] = page.inner_text("//span[@class='mds-dropdown__trigger__inner__single--value']")
            except:
                target_users["User Attribute"] = "N/A"

            # Campaign Tags
            try:
                page.wait_for_selector("//div[@class='mds-input__input--tags__list--item']/span[1]", timeout=5000)
                tag_elements = page.query_selector_all("//div[@class='mds-input__input--tags__list--item']/span[1]")
                tags = [el.inner_text().strip() for el in tag_elements]
                target_users["Campaign Tags"] = ", ".join(tags) if tags else "N/A"
            except Exception as e:
                target_users["Campaign Tags"] = "N/A"

            # Message Type
            try:
                selected = page.query_selector("//div[@class='dashboard-ui-103k3sf e441wj90']//input[@checked]")
                if selected:
                    # get the label text (the parent label’s text)
                    label = selected.evaluate("el => el.parentElement.innerText")
                    target_users["Message Type"] = label.strip()
                else:
                    target_users["Message Type"] = "N/A"
            except Exception as e:
                target_users["Message Type"] = "N/A"

            # Audience Selection
            try:
                page.wait_for_selector(
                    "//div[@class='mds-segmentation__section mds-segmentation__header']//input",
                    timeout=5000
                )
                # Get the label containing the checked input
                selected_label = page.query_selector(
                    "//div[@class='mds-segmentation__section mds-segmentation__header']//input[@checked]/.."
                )
                if selected_label:
                    label_text = selected_label.inner_text().strip()
                    target_users["Audience Selection"] = label_text
                else:
                    target_users["Audience Selection"] = "N/A"
            except Exception:
                target_users["Audience Selection"] = "N/A"


            # Exclude User checkbox
            try:
                selected = page.query_selector("//input[@id='exclude-user']")
                target_users["Exclude User"] = selected.is_checked() if selected else False
            except:
                target_users["Exclude User"] = False

            # User Opted Out Toggle
            try:
                toggle_attr = page.get_attribute("//div[@class='mds-preferenceManagement']//span[@role='switch']", "aria-checked")
                target_users["User Opted Out Toggle"] = toggle_attr == "true"
            except:
                target_users["User Opted Out Toggle"] = False

            # Audience Limit Toggle
            try:
                toggle_attr = page.get_attribute("//span[@aria-labelledby='Limit the number of users who will receive the campaign.']", "aria-checked")
                target_users["Audience Limit Toggle"] = toggle_attr == "true"
            except:
                target_users["Audience Limit Toggle"] = False

        
            # Control Group Toggle
            try:
                toggle_attr = page.get_attribute("//span[@aria-labelledby='Campaign control group']", "aria-checked")
                target_users["Control Group Toggle"] = toggle_attr == "true"
            except:
                target_users["Control Group Toggle"] = False

            # --- Content section ---
            try:
                content_step_button = page.wait_for_selector("//div[contains(@class,'mds-steps__item') and .//div[text()='Content']]//div[@role='button']", timeout=10000)
                content_step_button.click()
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(1000)
            except TimeoutError:
                print(f" Could not click Content step for Draft ID {draft_id}. Proceeding without content data.")
            except Exception as e:
                print(f" Error clicking Content step for Draft ID {draft_id}: {e}")

            content_data = {}
            sms_sender_span = page.query_selector("//div[@placeholder='Select a connector']//span[@class='mds-dropdown__trigger__inner__single--value']")
            content_data["SMS Sender"] = sms_sender_span.inner_text() if sms_sender_span else "N/A"

            template_id_input = page.query_selector("//input[@id='template_id']")
            content_data["Template ID"] = template_id_input.input_value() if template_id_input else "N/A"

            message_body_div = page.query_selector("//div[@id='personalization_container']")
            content_data["Message Body"] = message_body_div.inner_text() if message_body_div else "N/A"

            # --- Schedule and goals section ---
            try:
                schedule_step_button = page.wait_for_selector("//div[contains(@class,'mds-steps__item') and .//div[text()='Schedule and goals']]//div[@role='button']", timeout=10000)
                schedule_step_button.click()
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(1000)
            except TimeoutError:
                print(f" Could not click Schedule and Goals step for Draft ID {draft_id}. Proceeding without schedule data.")
            except Exception as e:
                print(f" Error clicking Schedule and Goals step for Draft ID {draft_id}: {e}")

            schedule_data = {}

            selected_schedule_input = page.query_selector("//input[@name='gCampaignType' and @checked]")
            if selected_schedule_input:
                sid = selected_schedule_input.get_attribute("id")
                if sid == "asap":
                    schedule_data["Send Campaign Toggle"] = "As soon as possible"
                elif sid == "specificDateTime":
                    schedule_data["Send Campaign Toggle"] = "At specific date and time"
                else:
                    schedule_data["Send Campaign Toggle"] = sid
            else:
                schedule_data["Send Campaign Toggle"] = "N/A"

            preferred_time_label = page.query_selector("//div[contains(@class,'mds-csc__sch__body__section')]//label[input[@name='startType'] and input[@checked]]")
            schedule_data["Preferred Time"] = preferred_time_label.inner_text().strip() if preferred_time_label else "N/A"

            start_date_input = page.query_selector("//input[@placeholder='Select date']")
            schedule_data["Start Date"] = start_date_input.input_value() if start_date_input else "N/A"

            hours_input = page.query_selector("(//div[contains(@class,'mds-timepicker__col')]//input[@type='number'])[1]")
            hours = hours_input.input_value() if hours_input else "N/A"

            minutes_input = page.query_selector("(//div[contains(@class,'mds-timepicker__col')]//input[@type='number'])[2]")
            minutes = minutes_input.input_value() if minutes_input else "N/A"

            am_pm_button = page.query_selector("//div[contains(@class,'mds-button-group')]//button[contains(@class,'mds-button--primary')]")
            am_pm = am_pm_button.inner_text() if am_pm_button else "N/A"

            if hours != "N/A" and minutes != "N/A" and am_pm != "N/A":
                schedule_data["Send Time"] = f"{hours}:{minutes} {am_pm}"
            else:
                schedule_data["Send Time"] = "N/A"

            date_str = schedule_data["Start Date"]
            time_str = schedule_data["Send Time"]

            if date_str != "N/A" and time_str != "N/A":
                dt_str = f"{date_str} {time_str}"
                try:
                    schedule_data["Scheduled Datetime"] = datetime.strptime(dt_str, "%d %b %Y %I:%M %p")
                except ValueError:
                    print(f" Datetime parsing failed for Draft ID {draft_id} with '{dt_str}'. Setting to N/A.")
                    schedule_data["Scheduled Datetime"] = "N/A"
            else:
                schedule_data["Scheduled Datetime"] = "N/A"

            conversion_goal_div = page.query_selector("//div[@class='mds-cg']//div[contains(@class,'mds-cg__section')]")
            schedule_data["Conversion Goals"] = conversion_goal_div.inner_text() if conversion_goal_div else "N/A"

            frequency_cap_toggle = page.query_selector("//span[@role='switch' and ../input[@name='Frequency capping']]")
            schedule_data["Frequency Cap Toggle"] = frequency_cap_toggle.get_attribute("aria-checked") == "true" if frequency_cap_toggle else False

            request_limit_input = page.query_selector("//input[@placeholder='Requests per/min...']")
            try:
                schedule_data["Request Limit"] = int(request_limit_input.input_value()) if request_limit_input else None
            except ValueError:
                schedule_data["Request Limit"] = None

            data = {
                "Draft ID": draft_id,
                "Target Users": target_users,
                "Content": content_data,
                "Schedule and Goals": schedule_data
            }
            data.update(target_users)
            all_data.append(data)
            print(f" Extracted data for Draft ID: {draft_id}")

        except Exception as e:
            print(f" Unexpected error for Draft ID {draft_id}: {e}")
            all_data.append({"Draft ID": draft_id, "Error": str(e)})

        finally:
            if page:
                page.close()

    return all_data


def run_scraper(email, password, draft_ids, output_csv_path, db_name,otp_code=None):
    with sync_playwright() as p:
        # Launch browser in non-headless mode so user can interact for OTP
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        stealth_sync(page)

        try:
            page.goto("https://dashboard-03.moengage.com/v4/#/auth", wait_until="domcontentloaded")

            # Check if already logged in
            try:
                page.wait_for_selector("div.mds-header__user-profile", timeout=5000)
                print("Already logged in, skipping login step.")
            except TimeoutError:
                print("Not logged in, attempting login...")
                try:
                    # wait for email field to exist and be visible
                    page.wait_for_selector("input#email", timeout=30000, state="visible")
                    page.fill("input#email", email)
                except Exception as e:
                    print(f" Could not find #email field: {e}")
                    page.screenshot(path="debug_email.png")
                    with open("debug_email.html", "w", encoding="utf-8") as f:
                        f.write(page.content())
                    raise
                page.fill("#password", password)
                page.click('button[type="submit"]')
                page.wait_for_load_state("networkidle", timeout=15000)

                # Detect 2FA page by presence of OTP inputs container
                try:
                    page.wait_for_selector("#passCodeInput", timeout=5000)
                    print("2FA verification required!")
                    if otp_code and len(otp_code) == 6 and otp_code.isdigit():
                        print("Filling OTP code automatically...")
                        # Fill each digit into the 6 separate inputs with ids 0 to 5
                        for i, digit in enumerate(otp_code):
                            page.fill(f"input[id='{i}']", digit)
                        # Click the Verify button
                        page.click("button.twofa-action-btn")
                        print("OTP submitted, waiting for login to complete...")
                    else:
                        print("No valid OTP code provided. Please enter the 6-digit code manually in the browser window.")
                    
                except TimeoutError:
                    print("No 2FA prompt detected. Waiting for login to complete...")

                # Wait indefinitely for the database dropdown to appear
                page.wait_for_selector("//div[contains(@class,'ignore-lang') and contains(@class,'tether-target')]", timeout=0)
                print("Login successful, database dropdown loaded.")

            # --- Select database/workspace ---
            try:
                # Open the workspace dropdown
                page.click(
                "//div[@class='ignore-lang tether-target tether-enabled tether-element-attached-top tether-element-attached-right tether-target-attached-bottom tether-target-attached-right tether-out-of-bounds tether-out-of-bounds-left tether-out-of-bounds-top']"
            )
                
                # Click the DB option by visible text
                page.click(f"text={db_name}")
                print(f" Database option clicked: {db_name}")

                # Handle "Change Workspace" confirmation popup if it appears
                try:
                    page.wait_for_selector("//button[normalize-space()='Change Workspace']", timeout=3000)
                    page.click("//button[normalize-space()='Change Workspace']")
                    print(f" Changed workspace to: {db_name}")
                except TimeoutError:
                    # No popup means already in correct DB
                    print(f"Already in database: {db_name}, no confirmation needed.")
            except Exception as e:
                print(f" Could not select database: {e}")
                sys.exit(1)

            # After successful login and DB selection, proceed to extract campaigns
            all_data = process_campaigns(context, draft_ids)
            all_data = add_validations(all_data)
            flat_data = flatten_campaign_data_with_single_message(all_data)
            df = pd.DataFrame(flat_data)
            df.to_csv(output_csv_path, index=False)
            print(f"Data successfully extracted and saved to {output_csv_path}")

        except Exception as e:
            print(f"An error occurred during the Playwright session: {e}")
            sys.exit(1)  # Exit with an error code to signal failure to the parent process
        finally:
            if browser:
                browser.close()

def enter_otp_code(page, otp_code):
    if len(otp_code) != 6 or not otp_code.isdigit():
        raise ValueError("OTP code must be a 6-digit string of digits.")

    for i, digit in enumerate(otp_code):
        selector = f"input[id='{i}']"
        page.fill(selector, digit)

    # Click the Verify button
    page.click("button.twofa-action-btn")

if __name__ == "__main__":
    # Order: email, password, db_name, draft_ids, csv_filename
    if len(sys.argv) < 7:
        print("Usage: python scrape.py <email> <password> <db_name> <comma_separated_draft_ids> <output_csv_path> <otp_code>")
        sys.exit(1)

    email = sys.argv[1]
    password = sys.argv[2]
    db_name = sys.argv[3]
    draft_ids_str = sys.argv[4]
    output_csv_path = sys.argv[5]
    otp_code = sys.argv[6]

    draft_ids = [d.strip() for d in draft_ids_str.split(',') if d.strip()]

    run_scraper(email, password, draft_ids, output_csv_path, db_name, otp_code)
