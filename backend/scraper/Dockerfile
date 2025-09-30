FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    tesseract-ocr \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scraper /app/scraper
COPY database /app/database
COPY task_queue /app/task_queue
COPY __init__.py /app/__init__.py

CMD ["python", "-m", "scraper.main"]
