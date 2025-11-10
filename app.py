import streamlit as st
import pandas as pd
import subprocess
import os
import sys

st.set_page_config(page_title="MoEngage Campaign Extractor", layout="centered")
st.title(" MoEngage Campaign Extractor (Selenium Version)")

# ---------------------------------------------
# SESSION STATE SETUP
# ---------------------------------------------
if "step" not in st.session_state:
    st.session_state.step = 1
for k in ["email", "password", "db_name", "draft_ids_text", "otp"]:
    st.session_state.setdefault(k, "")

# ---------------------------------------------
# STEP 1: LOGIN CREDENTIALS
# ---------------------------------------------
if st.session_state.step == 1:
    st.subheader("Step 1 — Login Credentials")
    with st.form("login_form"):
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

# ---------------------------------------------
# STEP 2: WORKSPACE + DRAFT IDS
# ---------------------------------------------
elif st.session_state.step == 2:
    st.subheader("Step 2 — Workspace & Campaigns")
    db_options = [
        "Collections_TC", "Tata Capital", "TataCapital_UAT",
        "Services_TC", "Wealth_TC", "Moneyfy"
    ]

    st.session_state.db_name = st.selectbox(
        "Select Database / Workspace",
        db_options,
        index=db_options.index(st.session_state.db_name) if st.session_state.db_name in db_options else 0
    )

    st.session_state.draft_ids_text = st.text_area(
        "Draft IDs (comma-separated)",
        value=st.session_state.draft_ids_text,
        help="Example: 68885b612a3c4eb3c36713cd, 68a87cca3bf0adc12258d2ad"
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Back"):
            st.session_state.step = 1
            st.rerun()
    with c2:
        if st.button("Next"):
            draft_ids = [x.strip() for x in st.session_state.draft_ids_text.split(",") if x.strip()]
            if not draft_ids:
                st.warning("Please enter at least one Draft ID.")
            else:
                st.session_state.draft_ids_list = draft_ids
                st.session_state.step = 3
                st.rerun()

# ---------------------------------------------
# STEP 3: OTP VERIFICATION
# ---------------------------------------------
elif st.session_state.step == 3:
    st.subheader("Step 3 — Two-Factor Authentication")
    with st.form("otp_form"):
        otp_input = st.text_input("Authenticator Code (6 digits)", max_chars=6)
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
            st.warning("Please enter the 6-digit OTP code.")

# ---------------------------------------------
# STEP 4: RUN EXTRACTION
# ---------------------------------------------
elif st.session_state.step == 4:
    st.subheader("Step 4 — Run Extraction")
    db_name = st.session_state.db_name.strip()
    csv_filename = f"{db_name}_campaigns_headless.csv"

    with st.spinner("Running Selenium scraper... this may take a few minutes "):
        try:
            # Run the Selenium script safely
            process = subprocess.run(
                [sys.executable, "selenium_headless.py"],
                capture_output=True,
                text=True,
                timeout=600  # 10-minute safety timeout
            )

            st.success(" Extraction completed!")
            st.code(process.stdout)
            if process.stderr:
                st.warning(" Scraper Warnings / Errors:")
                st.code(process.stderr)

            # --- Display and Download Data ---
            if os.path.exists(csv_filename):
                df = pd.read_csv(csv_filename)
                st.dataframe(df)
                st.download_button(
                    label=" Download CSV",
                    data=df.to_csv(index=False).encode("utf-8"),
                    file_name=csv_filename,
                    mime="text/csv"
                )
            else:
                st.error(f"CSV file '{csv_filename}' not found after extraction.")

        except subprocess.TimeoutExpired:
            st.error(" Scraper timed out — it took too long to finish.")
        except Exception as e:
            st.error(f" Unexpected error: {e}")

    st.button(" Run Again", on_click=lambda: st.session_state.update({"step": 1}))
