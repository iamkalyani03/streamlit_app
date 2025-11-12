# ==========================================
# Base: Selenium + Chromium
# ==========================================
FROM seleniarm/standalone-chromium:latest

USER root

# ==========================================
# Install Python and dependencies
# ==========================================
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

# ==========================================
# Setup Python virtual environment
# ==========================================
RUN python3 -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip setuptools wheel \
 && /opt/venv/bin/pip install -r requirements.txt

ENV PATH="/opt/venv/bin:$PATH"

# ==========================================
# Streamlit configuration
# ==========================================
RUN mkdir -p ~/.streamlit && \
    echo "\
[browser]\n\
gatherUsageStats = false\n\
[server]\n\
headless = true\n\
enableCORS = false\n\
enableXsrfProtection = false\n\
port = 10000\n\
address = \"0.0.0.0\"\n\
" > ~/.streamlit/config.toml

# ==========================================
# Expose the Render web port
# ==========================================
EXPOSE 10000

# ==========================================
# Start the Streamlit app
# ==========================================
CMD ["bash", "-c", "streamlit run app.py --server.port=${PORT:-10000} --server.address=0.0.0.0"]
