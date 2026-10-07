# Small, boring, disk-friendly image. No extra services.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Only persistent data is the SQLite DB + tiny backups (files stay on Telegram)
VOLUME ["/app/data"]

CMD ["python", "-m", "app.main"]
