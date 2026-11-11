"""Host-only credential policy. Neither the policy nor secrets enter job inputs."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from thesis_contracts.base import Strict


class ResearchCredential(Strict):
    name: str = Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")
    host: str = Field(pattern=r"^[a-z0-9][a-z0-9.-]+[a-z0-9]$")
    paths: tuple[str, ...] = Field(min_length=1, max_length=20)
    secret_env: str = Field(pattern=r"^THESIS_RESEARCH_SECRET_[A-Z0-9_]+$")
    auth_type: str = Field(default="bearer", pattern=r"^(bearer|apiKey)$")
    header_name: str = Field(default="Authorization", pattern=r"^[A-Za-z][A-Za-z0-9-]{0,63}$")

    @field_validator("host")
    @classmethod
    def exact_host(cls, host: str) -> str:
        import ipaddress

        try:
            ipaddress.ip_address(host)
        except ValueError:
            if host.endswith(".") or ".." in host:
                raise ValueError("invalid hostname")
            return host
        raise ValueError("credentials require an exact DNS hostname")

    @field_validator("paths")
    @classmethod
    def exact_paths(cls, paths: tuple[str, ...]) -> tuple[str, ...]:
        for path in paths:
            # Exact paths only: no wildcard, query, encoded separators or traversal.
            if not re.fullmatch(r"/[A-Za-z0-9_/-]+", path) or ".." in path or "//" in path:
                raise ValueError("credential paths must be narrow exact paths")
        return paths

    @field_validator("header_name")
    @classmethod
    def authentication_header_only(cls, name: str) -> str:
        if name.lower() in {
            "host", "content-length", "transfer-encoding", "connection", "upgrade",
            "proxy-authorization", "forwarded", "origin", "referer", "content-type",
        } or name.lower().startswith("x-forwarded-"):
            raise ValueError("credential header cannot affect routing or request framing")
        return name

    def matches(self, url: str) -> bool:
        parsed = urlsplit(url)
        return (
            parsed.scheme == "https" and parsed.port in {None, 443}
            and parsed.hostname == self.host and parsed.path in self.paths
        )


def load_credentials(path: str, url: str) -> list[tuple[ResearchCredential, SecretStr]]:
    if not path:
        return []
    config = Path(path)
    if config.stat().st_size > 64_000:
        raise ValueError("credential policy exceeds limit")
    payload = json.loads(config.read_text())
    if not isinstance(payload, list) or len(payload) > 20:
        raise ValueError("expected at most 20 credential policies")
    policies = [ResearchCredential.model_validate(item) for item in payload]
    selected = [p for p in policies if p.matches(url)]
    if len(selected) > 1:
        raise ValueError("overlapping credential policies")
    output = []
    for policy in selected:
        value = os.environ.get(policy.secret_env, "")
        if not value or len(value) > 8192:
            raise ValueError("research credential unavailable")
        output.append((policy, SecretStr(value)))
    return output
