"""Untrusted public-fetch boundary; tenant identity and credentials never cross it."""

from __future__ import annotations

import hashlib
from typing import Literal
from urllib.parse import urlsplit

from pydantic import ConfigDict, Field, field_validator, model_validator

from thesis_contracts.base import Strict

MAX_PUBLIC_FETCH_BYTES = 900_000


def public_url_shape(value: str) -> str:
    """Syntax only. The trusted executor must also enforce DNS/network policy."""
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or any(ord(c) < 33 for c in value)
    ):
        raise ValueError("expected an HTTP(S) URL without userinfo or whitespace")
    # Reject malformed ports here, rather than in an HTTP client later.
    _ = parsed.port
    return value


class PublicFetchRequest(Strict):
    scope: Literal["public"] = "public"
    url: str = Field(max_length=8192)
    max_bytes: int = Field(default=MAX_PUBLIC_FETCH_BYTES, ge=1, le=MAX_PUBLIC_FETCH_BYTES)

    _url = field_validator("url")(public_url_shape)


class PublicFetchResult(Strict):
    model_config = ConfigDict(
        extra="forbid", frozen=True, ser_json_bytes="base64", val_json_bytes="base64"
    )

    requested_url: str = Field(max_length=8192)
    final_url: str = Field(max_length=8192)
    status_code: int = Field(ge=100, le=599)
    content_type: str = Field(min_length=1, max_length=256)
    body: bytes = Field(max_length=MAX_PUBLIC_FETCH_BYTES)
    body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    hops: tuple[str, ...] = Field(min_length=1, max_length=6)

    _urls = field_validator("requested_url", "final_url")(public_url_shape)

    @model_validator(mode="after")
    def check_integrity(self) -> PublicFetchResult:
        for hop in self.hops:
            if len(hop) > 8192:
                raise ValueError("redirect URL too long")
            public_url_shape(hop)
        if self.hops[0] != self.requested_url or self.hops[-1] != self.final_url:
            raise ValueError("redirect chain does not match result URLs")
        if hashlib.sha256(self.body).hexdigest() != self.body_sha256:
            raise ValueError("body hash mismatch")
        return self
