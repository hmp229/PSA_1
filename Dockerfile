FROM python:3.11-slim

WORKDIR /app

# Copy requirements from backend folder
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy ALL backend code
COPY backend/ .

# Use app.py instead of main.py
CMD uvicorn app:app --host 0.0.0.0 --port $PORT