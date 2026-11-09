FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      tesseract-ocr \
      tesseract-ocr-eng \
      curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir \
      fastapi==0.115.6 \
      uvicorn==0.32.1 \
      httpx==0.27.2 \
      python-multipart==0.0.17 \
      pypdf==5.1.0 \
      pdfplumber==0.11.4 \
      pypdfium2==4.30.0 \
      pytesseract==0.3.13 \
      pillow==11.0.0 \
      temporalio==1.7.1

COPY apps/worker-docs/app /app/app
COPY fixtures/d4-ocr /app/fixtures/d4-ocr

ENV OCR_LANGUAGES=eng
ENV PYTHONPATH=/app
EXPOSE 8091
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8091"]
