import streamlit as st
import pandas as pd
import subprocess
import os
import sys

st.set_page_config(page_title="MoEngage Campaign Extractor", layout="centered")
st.title("MoEngage Campaign Extractor (Headless Selenium)")

# ==========================================
# SESSION STATE
# ==========================================
if "step" not in st.session_state:
    st.session_state.step = 1
for k in ["email", "password", "db_name", "draft_ids_text", "otp"]:
    st.session_state.setdefault(k, "")

# ==========================================
# STEP 1 — LOGIN CREDENTIALS
# ==========================================
if st.session_state.step == 1:
    st.subheader("Step 1 — Login Credentials")
    with st.form("login_form"):
        email = st.text_input("Email", value=st.session_state.email)
        password = st.text_input("Password", type="password", value=st.session_state.password)
        submitted = st.form_submit_button("Next")
    if submitted:
        if email and password:
            st.session_state.email = email
            st.session_state.password = password
            st.session_state.step = 2
            st.rerun()
        else:
            st.warning("Enter both email and password.")

# ==========================================
# STEP 2 — WORKSPACE & DRAFT IDS
# ==========================================
elif st.session_state.step == 2:
    st.subheader("Step 2 — Workspace & Draft IDs")

    db_options = ["Collections_TC", "Tata Capital", "TataCapital_UAT", "Services_TC", "Wealth_TC", "Moneyfy"]
    db_name = st.selectbox(
        "Select Workspace",
        db_options,
        index=db_options.index(st.session_state.db_name) if st.session_state.db_name in db_options else 0
    )
    draft_ids = st.text_area("Draft IDs (comma-separated)", value=st.session_state.draft_ids_text)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Back"):
            st.session_state.step = 1
            st.rerun()
    with col2:
        if st.button("Next"):
            if not draft_ids.strip():
                st.warning("Enter at least one Draft ID.")
            else:
                st.session_state.db_name = db_name
                st.session_state.draft_ids_text = draft_ids
                st.session_state.step = 3
                st.rerun()

# ==========================================
# STEP 3 — OTP VERIFICATION
# ==========================================
elif st.session_state.step == 3:
    st.subheader("Step 3 — OTP Verification")
    st.write("Enter the OTP sent by MoEngage for login verification:")

    with st.form("otp_form"):
        otp_code = st.text_input("OTP (6 digits)", max_chars=6, value=st.session_state.otp)
        col1, col2 = st.columns(2)
        with col1:
            back = st.form_submit_button("Back")
        with col2:
            next_btn = st.form_submit_button("Verify & Continue")

    if back:
        st.session_state.step = 2
        st.rerun()
    if next_btn:
        if otp_code.strip() and otp_code.isdigit() and len(otp_code.strip()) == 6:
            st.session_state.otp = otp_code.strip()
            st.session_state.step = 4
            st.rerun()
        else:
            st.warning("Enter a valid 6-digit OTP.")

# ==========================================
# STEP 4 — RUN EXTRACTION
# ==========================================
elif st.session_state.step == 4:
    st.subheader("Step 4 — Run Extraction")
    csv_filename = f"{st.session_state.db_name}_campaigns_headless.csv"

    env = os.environ.copy()
    env["MOENGAGE_EMAIL"] = st.session_state.email
    env["MOENGAGE_PASSWORD"] = st.session_state.password
    env["WORKSPACE"] = st.session_state.db_name
    env["DRAFT_IDS"] = st.session_state.draft_ids_text
    env["OTP_CODE"] = st.session_state.otp

    with st.spinner("Running headless Chrome... this may take 2–3 mins"):
        try:
            process = subprocess.run(
                [sys.executable, "selenium_headless.py"],
                capture_output=True,
                text=True,
                env=env,
                timeout=600
            )

            if process.stdout:
                st.text_area("Logs (stdout):", process.stdout, height=250)
            if process.stderr:
                st.warning("Errors / stderr:")
                st.text_area("stderr", process.stderr, height=200)

            if os.path.exists(csv_filename):
                df = pd.read_csv(csv_filename)
                st.success("Extraction finished!")
                st.dataframe(df)
                st.download_button(
                    "Download CSV",
                    df.to_csv(index=False).encode("utf-8"),
                    file_name=csv_filename
                )
            else:
                st.error("CSV not found — check logs above.")

        except subprocess.TimeoutExpired:
            st.error("Process timed out.")
        except Exception as e:
            st.error(f"Unexpected error: {e}")

    st.button("Run Again", on_click=lambda: st.session_state.update({"step": 1}))
