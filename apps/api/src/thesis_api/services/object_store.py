# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""S3-compatible helpers (SeaweedFS)."""

from __future__ import annotations

from typing import Any

from thesis_api.settings import settings


def _client():
    import boto3
    from botocore.client import Config

    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def put_bytes(*, bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    client = _client()
    client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
    return f"s3://{bucket}/{key}"


def get_bytes(*, bucket: str, key: str) -> bytes:
    client = _client()
    obj = client.get_object(Bucket=bucket, Key=key)
    return obj["Body"].read()


def delete_object(*, bucket: str, key: str) -> str:
    client = _client()
    client.delete_object(Bucket=bucket, Key=key)
    return f"s3://{bucket}/{key}"


def list_keys(*, bucket: str, prefix: str, max_keys: int = 1000) -> list[str]:
    client = _client()
    keys: list[str] = []
    token: str | None = None
    while True:
        kwargs: dict[str, Any] = {
            "Bucket": bucket,
            "Prefix": prefix,
            "MaxKeys": min(1000, max_keys - len(keys)),
        }
        if token:
            kwargs["ContinuationToken"] = token
        res = client.list_objects_v2(**kwargs)
        for item in res.get("Contents") or []:
            k = item.get("Key")
            if k:
                keys.append(str(k))
                if len(keys) >= max_keys:
                    return keys
        if not res.get("IsTruncated"):
            break
        token = res.get("NextContinuationToken")
        if not token:
            break
    return keys


def delete_prefix(*, bucket: str, prefix: str) -> list[str]:
    """Delete all objects under prefix. Returns deleted s3:// URIs."""
    deleted: list[str] = []
    keys = list_keys(bucket=bucket, prefix=prefix)
    client = _client()
    # Seaweed/S3 delete in chunks of 1000
    for i in range(0, len(keys), 1000):
        chunk = keys[i : i + 1000]
        if not chunk:
            continue
        client.delete_objects(
            Bucket=bucket,
            Delete={"Objects": [{"Key": k} for k in chunk], "Quiet": True},
        )
        deleted.extend(f"s3://{bucket}/{k}" for k in chunk)
    return deleted


def parse_s3_ref(ref: str, *, default_bucket: str | None = None) -> tuple[str, str]:
    """Parse s3://bucket/key, bucket/key, or bare prefix (uses default_bucket)."""
    raw = ref.strip().rstrip("*")
    if raw.startswith("s3://"):
        rest = raw[len("s3://") :]
        bucket, _, key = rest.partition("/")
        return bucket, key
    if default_bucket and "/" in raw and not raw.startswith(default_bucket + "/"):
        # treat as key/prefix under default bucket
        return default_bucket, raw
    if default_bucket:
        return default_bucket, raw
    bucket, _, key = raw.partition("/")
    return bucket, key
