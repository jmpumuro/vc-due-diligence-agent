# SPDX-License-Identifier: Apache-2.0
"""Object-store delete helpers + retention destructive path (mocked S3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from thesis_api.services import object_store, retention


class _FakeS3:
    def __init__(self) -> None:
        self.store: dict[tuple[str, str], bytes] = {}
        self.deleted: list[tuple[str, str]] = []

    def put_object(self, **kwargs: Any) -> None:
        self.store[(kwargs["Bucket"], kwargs["Key"])] = kwargs["Body"]

    def get_object(self, **kwargs: Any) -> dict:
        return {"Body": _Bytes(self.store[(kwargs["Bucket"], kwargs["Key"])])}

    def delete_object(self, **kwargs: Any) -> None:
        self.deleted.append((kwargs["Bucket"], kwargs["Key"]))
        self.store.pop((kwargs["Bucket"], kwargs["Key"]), None)

    def list_objects_v2(self, **kwargs: Any) -> dict:
        bucket = kwargs["Bucket"]
        prefix = kwargs.get("Prefix") or ""
        contents = [
            {"Key": k} for (b, k) in self.store if b == bucket and k.startswith(prefix)
        ]
        return {"Contents": contents, "IsTruncated": False}

    def delete_objects(self, **kwargs: Any) -> dict:
        for obj in kwargs["Delete"]["Objects"]:
            self.delete_object(Bucket=kwargs["Bucket"], Key=obj["Key"])
        return {}


class _Bytes:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data


@pytest.fixture()
def fake_s3(monkeypatch: pytest.MonkeyPatch) -> _FakeS3:
    fake = _FakeS3()
    monkeypatch.setattr(object_store, "_client", lambda: fake)
    return fake


def test_put_get_delete_prefix(fake_s3: _FakeS3) -> None:
    object_store.put_bytes(bucket="dataroom", key="a/b/1.pdf", data=b"one")
    object_store.put_bytes(bucket="dataroom", key="a/b/2.pdf", data=b"two")
    assert object_store.get_bytes(bucket="dataroom", key="a/b/1.pdf") == b"one"
    deleted = object_store.delete_prefix(bucket="dataroom", prefix="a/b/")
    assert len(deleted) == 2
    assert object_store.list_keys(bucket="dataroom", prefix="a/") == []


def test_execute_deletion_deletes_planned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_s3: _FakeS3
) -> None:
    monkeypatch.setenv("RETENTION_CERT_DIR", str(tmp_path))
    monkeypatch.setenv("RETENTION_DESTRUCTIVE_DELETE", "true")
    object_store.put_bytes(bucket="dataroom", key="frm/x/doc.pdf", data=b"x")
    cert = retention.plan_deletion(
        firm_id="frm",
        data_room_ids=["dr1"],
        retention_record_ids=[],
        object_keys=["s3://dataroom/frm/x/*"],
    )
    done = retention.execute_deletion(cert)
    assert done.mode.startswith("executed")
    assert done.objects_deleted
    assert fake_s3.store == {}
