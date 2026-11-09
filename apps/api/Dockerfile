FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/* \
  && pip install --no-cache-dir uv

COPY packages/contracts /app/packages/contracts
COPY apps/api /app/apps/api
COPY fixtures/ofac /app/fixtures/ofac
COPY fixtures/d6-site /app/fixtures/d6-site

# Drop workspace-only source so the image can install from a path.
RUN sed -i '/\[tool\.uv\.sources\]/,/^$/d' /app/apps/api/pyproject.toml

WORKDIR /app/apps/api
RUN uv pip install --system --no-cache /app/packages/contracts \
  && uv pip install --system --no-cache -e . \
  && uv pip install --system --no-cache argon2-cffi email-validator temporalio

ENV PYTHONPATH=/app/apps/api/src
EXPOSE 8000
CMD ["uvicorn", "thesis_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
