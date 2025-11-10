import streamlit as st
import pandas as pd
import subprocess
import os

st.title(" MoEngage Campaign Extractor (Selenium Version)")

# Session state setup
if "step" not in st.session_state:
    st.session_state.step = 1
for k in ["email", "password", "db_name", "draft_ids_text", "otp"]:
    st.session_state.setdefault(k, "")

# --- Step 1: Login Credentials ---
if st.session_state.step == 1:
    st.subheader("Step 1 — Login Credentials")
    st.write("Enter your MoEngage login details.")

    with st.form("login_form", clear_on_submit=False):
        email_input = st.text_input("Email", value=st.session_state.get("email", ""))
        password_input = st.text_input("Password", type="password", value=st.session_state.get("password", ""))
        submitted = st.form_submit_button("Next")

    if submitted:
        if email_input and password_input:
            st.session_state.email = email_input.strip()
            st.session_state.password = password_input.strip()
            st.session_state.step = 2
            st.rerun()
        else:
            st.warning("Please enter both email and password.")

# --- Step 2: Workspace & Draft IDs ---
elif st.session_state.step == 2:
    st.subheader("Step 2 — Workspace & Campaigns")
    st.write("Select your workspace and provide the Draft IDs to extract.")

    db_options = [
        "Collections_TC",
        "Tata Capital",
        "TataCapital_UAT",
        "Services_TC",
        "Wealth_TC",
        "Moneyfy"
    ]

    st.session_state.db_name = st.selectbox(
        "Select Database / Workspace Name",
        options=db_options,
        index=db_options.index(st.session_state.db_name) if st.session_state.db_name in db_options else 0
    )

    st.session_state.draft_ids_text = st.text_area(
        "Draft IDs (comma-separated)",
        value=st.session_state.draft_ids_text,
        help="Example: 68a87cca3bf0adc12258d2ad, 68ad7bc01315f645e808598a"
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Back"):
            st.session_state.step = 1
            st.rerun()
    with c2:
        if st.button("Next"):
            draft_ids_list = [x.strip() for x in st.session_state.draft_ids_text.split(",") if x.strip()]
            if not st.session_state.db_name:
                st.warning("Please select a workspace name.")
            elif not draft_ids_list:
                st.warning("Please enter at least one Draft ID.")
            else:
                st.session_state.draft_ids_list = draft_ids_list
                st.session_state.step = 3
                st.rerun()

# --- Step 3: OTP verification ---
elif st.session_state.step == 3:
    st.subheader("Step 3 — Two-Factor Authentication")
    st.write("Enter the 6-digit code from your Google Authenticator app.")

    with st.form("otp_form", clear_on_submit=False):
        otp_input = st.text_input("Authenticator Code", max_chars=6)
        c1, c2 = st.columns(2)
        with c1:
            back = st.form_submit_button("Back")
        with c2:
            submitted = st.form_submit_button("Verify & Continue")

    if back:
        st.session_state.step = 2
        st.rerun()

    if submitted:
        if otp_input.strip():
            st.session_state.otp = otp_input.strip()
            st.session_state.step = 4
            st.rerun()
        else:
            st.warning("Please enter the 6-digit code.")

# --- Step 4: Run Extraction ---
elif st.session_state.step == 4:
    st.subheader("Step 4 — Run Extraction")

    db_name = st.session_state.db_name.strip()
    csv_filename = f"{db_name}_campaigns.csv"
    draft_ids_list = st.session_state.draft_ids_list
    otp_code = st.session_state.otp

    with st.spinner("Running Selenium scraper... please wait."):
        try:
            process = subprocess.run(
                [
                    "python",
                    "selenium_headless.py",
                    st.session_state.email,
                    st.session_state.password,
                    db_name,
                    ",".join(draft_ids_list),
                    csv_filename,
                    otp_code
                ],
                capture_output=True,
                text=True,
                check=True
            )

            st.success(" Extraction completed!")
            st.text("Scraper Output:")
            st.code(process.stdout)
            if process.stderr:
                st.error("Scraper Errors:")
                st.code(process.stderr)

            if os.path.exists(csv_filename):
                df = pd.read_csv(csv_filename)
                st.success(" Data loaded successfully!")
                st.dataframe(df)
                st.caption(f"Saved to: {csv_filename}")
                st.download_button(
                    label="Download CSV",
                    data=df.to_csv(index=False).encode('utf-8'),
                    file_name=csv_filename,
                    mime="text/csv",
                )
            else:
                st.error(f"Extraction failed: CSV file '{csv_filename}' not found.")

        except subprocess.CalledProcessError as e:
            st.error(f" Scraper process failed (code {e.returncode}).")
            st.code(e.stdout)
            st.code(e.stderr)
        except FileNotFoundError:
            st.error(" 'selenium_headless.py' not found.")
        except Exception as e:
            st.error(f" Unexpected error: {e}")
