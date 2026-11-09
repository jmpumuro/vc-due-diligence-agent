#!/usr/bin/env python3
"""B1 SeaweedFS S3-compat smoke: put, get, delete via boto3.

Industry default (2026-11-08): compose publishes 8333; credentials any/any.
Does not alone mark B1 Verified — records smoke evidence for rem backlog.
"""

from __future__ import annotations

import os
import sys
import uuid

try:
    import boto3
    from botocore.client import Config
except ImportError:
    print("SKIP: boto3 not installed")
    raise SystemExit(0)

endpoint = os.environ.get("S3_ENDPOINT", "http://localhost:8333")
access = os.environ.get("S3_ACCESS_KEY", "any")
secret = os.environ.get("S3_SECRET_KEY", "any")
bucket = os.environ.get("S3_BUCKET_ARTIFACTS", "artifacts")

client = boto3.client(
    "s3",
    endpoint_url=endpoint,
    aws_access_key_id=access,
    aws_secret_access_key=secret,
    config=Config(signature_version="s3v4"),
    region_name="us-east-1",
)

key = f"b1-smoke/{uuid.uuid4()}.txt"
body = b"thesis-b1-smoke"
try:
    client.put_object(Bucket=bucket, Key=key, Body=body, ContentType="text/plain")
    got = client.get_object(Bucket=bucket, Key=key)["Body"].read()
    assert got == body
    url = client.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=60
    )
    assert url.startswith("http")
    client.delete_object(Bucket=bucket, Key=key)
    print("status=ok put/get/presign/delete")
    print(f"endpoint={endpoint} bucket={bucket}")
except Exception as exc:  # noqa: BLE001
    print(f"status=failed {exc}")
    raise SystemExit(1)
