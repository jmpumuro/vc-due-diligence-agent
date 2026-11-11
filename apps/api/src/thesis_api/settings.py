from __future__ import annotations

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    demo_workspace: bool = True
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    database_url: str = "postgresql+asyncpg://thesis:thesis@postgres:5432/thesis"
    temporal_host: str = "temporal:7233"
    searxng_url: str = "http://searxng:8080"
    browser_enabled: bool = False
    # Trusted operator configuration, never supplied by the research agent.
    browser_egress_proxy_url: str = ""
    research_execution_backend: Literal["local", "opensandbox"] = "local"
    sandbox_endpoint: str = "http://127.0.0.1:8095"
    sandbox_api_key: SecretStr = SecretStr("")
    sandbox_image: str = ""
    sandbox_owner: str = "thesis-research"
    sandbox_concurrency: int = Field(default=2, ge=1, le=8)
    sandbox_timeout_seconds: int = Field(default=120, ge=60, le=300)
    # Operator-owned JSON file; references secret env vars, never contains values.
    sandbox_credentials_file: str = ""
    s3_endpoint: str = "http://seaweedfs:8333"
    # SeaweedFS default S3 identity is any/any (see seaweed-init in compose).
    s3_access_key: str = "any"
    s3_secret_key: str = "any"
    s3_bucket_artifacts: str = "artifacts"
    s3_bucket_dataroom: str = "dataroom"
    s3_bucket_quarantine: str = "quarantine"
    public_web_url: str = "http://localhost:3000"
    public_api_url: str = "http://localhost:8000"
    setup_complete: bool = False
    # When true, API/worker sessions SET LOCAL ROLE thesis_app so RLS policies apply.
    enforce_rls_role: bool = True
    # Optional Stage 7 webhook delivery (POST JSON sanitized outbox payload).
    outbox_webhook_url: str = ""
    # Local OpenAI-compatible server (REM-P1-05). Empty → local_route_available false.
    local_llm_url: str = ""
    local_llm_api_key: str = "local"
    local_llm_model: str = "local-model"
    # D6 local fixture base (compose d6-fixture). Never invent a public Pages URL.
    d6_fixture_url: str = "http://localhost:8090"
    # ClamAV clamd TCP (compose service `clamav`).
    clamav_host: str = "clamav"
    clamav_port: int = 3310
    # worker-docs health (compose service).
    worker_docs_url: str = "http://worker-docs:8091"
    # Max upload size before reject (bytes).
    docs_max_upload_bytes: int = 25 * 1024 * 1024
    # Flip only after D4 product smoke / Temporal q.docs evidence (never health alone).
    ocr_product_verified: bool = False


settings = Settings()
