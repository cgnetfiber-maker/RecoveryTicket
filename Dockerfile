FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install only Chromium binary without full bundle
RUN python -m playwright install chromium

# Copy app files
COPY . .

EXPOSE 7860
CMD ["python", "app.py"]
