FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg unzip ca-certificates fonts-liberation libnss3 libxss1 \
    libasound2 libatk1.0-0 libatk-bridge2.0-0 libcups2 libgbm1 \
    libgtk-3-0 libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Add Google Chrome repo and install Chrome stable (modern way)
RUN mkdir -p /etc/apt/keyrings \
 && wget -q -O /etc/apt/keyrings/google-linux-signing-key.gpg https://dl.google.com/linux/linux_signing_key.pub \
 && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-linux-signing-key.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
    | tee /etc/apt/sources.list.d/google-chrome.list > /dev/null \
 && apt-get update \
 && apt-get install -y --no-install-recommends google-chrome-stable \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV PORT=10000
ENV BROWSER=none

CMD ["streamlit", "run", "app.py", "--server.port", "10000", "--server.address", "0.0.0.0"]
