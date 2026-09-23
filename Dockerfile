FROM python:3.10-slim

# Install system dependencies needed for Playwright browsers
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser binaries and system dependencies
RUN playwright install chromium --with-deps

# Copy application files
COPY . .

# Expose port and run app
EXPOSE 7860
CMD ["python", "app.py"]
