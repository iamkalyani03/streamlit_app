# Use selenium + chromium base
FROM seleniarm/standalone-chromium:latest

USER root

# Install Python + venv
RUN apt-get update && apt-get install -y python3 python3-pip python3-venv && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

# Create virtual environment & install dependencies
RUN python3 -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip setuptools wheel \
 && /opt/venv/bin/pip install -r requirements.txt

ENV PATH="/opt/venv/bin:$PATH"

# Streamlit config
RUN mkdir -p ~/.streamlit && \
    echo "\
[browser]\n\
gatherUsageStats = false\n\
[server]\n\
headless = true\n\
enableCORS = false\n\
enableXsrfProtection = false\n\
port = 8501\n\
address = \"0.0.0.0\"\n\
" > ~/.streamlit/config.toml

EXPOSE 8501

CMD ["bash", "-c", "streamlit run app.py --server.port=${PORT:-8501} --server.address=0.0.0.0"]
