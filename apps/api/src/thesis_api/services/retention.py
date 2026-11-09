# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""Retention deletion planning + DeletionCertificate (D2).

Industry default: dry-run only. Destructive delete requires explicit
RETENTION_DESTRUCTIVE_DELETE=true — never the default for local/dev.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class DeletionCertificate:
    certificate_id: str
    firm_id: str | None
    mode: str  # dry_run | executed
    created_at: str
    data_room_ids: list[str] = field(default_factory=list)
    retention_record_ids: list[str] = field(default_factory=list)
    object_keys_planned: list[str] = field(default_factory=list)
    objects_deleted: list[str] = field(default_factory=list)
    blocked_reasons: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def certificates_dir() -> Path:
    raw = os.environ.get("RETENTION_CERT_DIR", "").strip()
    if raw:
        path = Path(raw)
    else:
        path = Path(__file__).resolve().parents[5] / "var" / "retention-certificates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def destructive_enabled() -> bool:
    return os.environ.get("RETENTION_DESTRUCTIVE_DELETE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def plan_deletion(
    *,
    firm_id: str | None,
    data_room_ids: list[str],
    retention_record_ids: list[str],
    object_keys: list[str] | None = None,
    notes: str = "",
) -> DeletionCertificate:
    """Always produces a dry-run certificate first (industry default)."""
    cert = DeletionCertificate(
        certificate_id=str(uuid4()),
        firm_id=firm_id,
        mode="dry_run",
        created_at=datetime.now(timezone.utc).isoformat(),
        data_room_ids=list(data_room_ids),
        retention_record_ids=list(retention_record_ids),
        object_keys_planned=list(object_keys or []),
        notes=notes or "list→delete dry-run (D2 default)",
    )
    path = certificates_dir() / f"{cert.certificate_id}.json"
    path.write_text(json.dumps(cert.to_dict(), indent=2) + "\n")
    return cert


def execute_deletion(cert: DeletionCertificate) -> DeletionCertificate:
    """Promote dry-run to executed only when destructive flag is set.

    When enabled, deletes planned object keys/prefixes via the S3-compatible store.
    Callers must not claim objects erased without a successful delete loop.
    """
    if not destructive_enabled():
        cert.blocked_reasons.append(
            "RETENTION_DESTRUCTIVE_DELETE not enabled; certificate remains dry_run"
        )
        path = certificates_dir() / f"{cert.certificate_id}.json"
        path.write_text(json.dumps(cert.to_dict(), indent=2) + "\n")
        return cert

    from thesis_api.services.object_store import delete_object, delete_prefix, parse_s3_ref
    from thesis_api.settings import settings

    deleted: list[str] = []
    errors: list[str] = []
    default_bucket = settings.s3_bucket_dataroom
    for ref in cert.object_keys_planned:
        try:
            is_prefix = ref.rstrip().endswith("*")
            bucket, key = parse_s3_ref(ref, default_bucket=default_bucket)
            if not bucket or key is None:
                errors.append(f"bad_ref:{ref}")
                continue
            if is_prefix or key.endswith("/"):
                deleted.extend(delete_prefix(bucket=bucket, prefix=key))
            elif key:
                deleted.append(delete_object(bucket=bucket, key=key))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{ref}:{exc}"[:240])

    cert.mode = "executed" if not errors else "executed_with_errors"
    cert.objects_deleted = deleted
    if errors:
        cert.blocked_reasons.extend(errors)
    cert.notes = (
        (cert.notes + "; ").lstrip("; ")
        + f"destructive delete ran; deleted={len(deleted)} errors={len(errors)}"
    )
    path = certificates_dir() / f"{cert.certificate_id}.json"
    path.write_text(json.dumps(cert.to_dict(), indent=2) + "\n")
    return cert
