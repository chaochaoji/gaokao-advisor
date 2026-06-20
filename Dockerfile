FROM python:3.11-slim

WORKDIR /app

# Use Tsinghua Debian mirrors for faster downloads in China
RUN sed -i 's|http://deb.debian.org/debian|https://mirrors.tuna.tsinghua.edu.cn/debian|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple -r requirements.txt

COPY . .

RUN mkdir -p data/raw data/processed data/chroma_db logs models

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=3s \
    CMD python -c "import json; json.load(open('logs/health.json'))" || exit 1

CMD ["python", "app.py"]
