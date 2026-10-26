
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DATABASE_PATH=/data/tixly.sqlite3

WORKDIR /app

COPY bot/requirements.txt /app/bot/requirements.txt
COPY api/requirements.txt /app/api/requirements.txt

RUN pip install --no-cache-dir \
    -r /app/bot/requirements.txt \
    -r /app/api/requirements.txt

COPY . /app

RUN mkdir -p /data

CMD ["sh", "-c", "uvicorn api.app:app --host 0.0.0.0 --port ${PORT:-8000} & python -m bot.main"]
 
