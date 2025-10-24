FROM python:3.11-slim

WORKDIR /app

# Install system dependencies that might be needed
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy ALL backend code
COPY backend/ .

# Use app.py
CMD uvicorn app:app --host 0.0.0.0 --port $PORT