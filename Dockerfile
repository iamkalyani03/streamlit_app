# ==========================================
# Base image
# ==========================================
FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_ROOT_USER_ACTION=ignore
ENV PYTHONUNBUFFERED=1

# ==========================================
# Install Chrome + dependencies
# ==========================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg unzip fonts-liberation libnss3 libasound2 xdg-utils ca-certificates \
    libxss1 libgdk-pixbuf-2.0-0 libxcomposite1 libxrandr2 libxi6 libatk-bridge2.0-0 libgtk-3-0 \
    curl xvfb \
    && mkdir -p /etc/apt/keyrings \
    && wget -q -O /etc/apt/keyrings/google-linux-signing-key.gpg https://dl.google.com/linux/linux_signing_key.pub \
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-linux-signing-key.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
      > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y --no-install-recommends google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# ==========================================
# Set working directory
# ==========================================
WORKDIR /app

# ==========================================
# Copy dependencies and install Python packages
# ==========================================
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ==========================================
# Copy application code
# ==========================================
COPY . .

# ==========================================
# Expose port for Streamlit (optional)
# ==========================================
ENV PORT=10000
CMD ["streamlit", "run", "app.py", "--server.port=10000", "--server.address=0.0.0.0"]
