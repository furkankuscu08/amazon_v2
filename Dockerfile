FROM python:3.12-slim
WORKDIR /app
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    FASTEMBED_CACHE_PATH=/opt/fastembed
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt
RUN useradd --create-home --uid 10001 workbot \
    && mkdir /data /opt/fastembed && chown workbot /data /opt/fastembed
USER workbot
# Download the embedding model at build time, so the first search does not wait for it.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/all-MiniLM-L6-v2')"
COPY workbot/ ./workbot/
CMD ["uvicorn", "workbot.main:app", "--host", "0.0.0.0", "--port", "8000"]
