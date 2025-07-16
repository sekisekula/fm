FROM python:3.11-slim

# Tworzymy katalog roboczy
WORKDIR /app

# Instalujemy zależności
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Kopiujemy cały folder app jako podfolder app/
COPY app /app/app

# Najważniejsze: ustawiamy PYTHONPATH tak, żeby /app było w ścieżce
ENV PYTHONPATH=/app

# Allow switching between API and CLI mode
ENV APP_MODE=api

CMD ["/bin/sh", "-c", "if [ \"$APP_MODE\" = 'cli' ]; then python app/menu/main.py; else uvicorn app.main:app --host 0.0.0.0 --port 8000; fi"]
