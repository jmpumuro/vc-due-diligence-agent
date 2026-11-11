FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

ENV PYTHONDONTWRITEBYTECODE=1 PLAYWRIGHT_BROWSERS_PATH=/opt/browsers PYTHONPATH=/opt/contracts
COPY apps/sandbox-runtime/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt \
    && playwright install --with-deps chromium \
    && useradd --uid 10000 --create-home researcher \
    && rm -f /tmp/requirements.txt
COPY packages/contracts/src/thesis_contracts /opt/contracts/thesis_contracts
COPY apps/sandbox-runtime/runner.py /opt/research/runner.py
COPY apps/api/src/thesis_api/services/fetch/safe_fetcher.py /opt/research/safe_fetcher.py
RUN mkdir -p /opt/opensandbox && chmod -R a+rX /opt/research
# OpenSandbox starts execd; individual fixed commands run as uid/gid 10000.
CMD ["sleep", "infinity"]
