FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data/raw data/processed data/chroma_db logs models

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=3s \
    CMD python -c "import json; json.load(open('logs/health.json'))" || exit 1

CMD ["python", "app.py"]
