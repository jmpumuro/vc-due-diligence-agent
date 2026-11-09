# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""ClamAV clamd TCP client (INSTREAM) — DD-12 malware gate."""

from __future__ import annotations

import asyncio
import socket
from dataclasses import dataclass

from thesis_api.settings import settings


@dataclass(frozen=True)
class ScanResult:
    ok: bool
    status: str
    detail: str = ""


def _sync_ping(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.sendall(b"zPING\0")
            sock.settimeout(timeout)
            data = sock.recv(32)
            return b"PONG" in data
    except OSError:
        return False


def _sync_scan(data: bytes, host: str, port: int, timeout: float = 30.0) -> ScanResult:
    """Scan bytes via clamd INSTREAM. Empty payload → ok."""
    if not data:
        return ScanResult(ok=True, status="empty")
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.sendall(b"zINSTREAM\0")
            # chunked: 4-byte big-endian length + data; end with length 0
            view = memoryview(data)
            chunk = 1024 * 64
            for i in range(0, len(view), chunk):
                part = view[i : i + chunk]
                sock.sendall(len(part).to_bytes(4, "big") + part.tobytes())
            sock.sendall((0).to_bytes(4, "big"))
            sock.settimeout(timeout)
            resp = sock.recv(4096).decode("utf-8", errors="replace").replace("\x00", "").strip()
    except OSError as exc:
        return ScanResult(ok=False, status="unavailable", detail=str(exc)[:200])

    # Examples: "stream: OK" / "stream: Eicar-Test-Signature FOUND"
    upper = resp.upper()
    if "FOUND" in upper:
        return ScanResult(ok=False, status="malware", detail=resp)
    if "OK" in upper:
        return ScanResult(ok=True, status="clean", detail=resp)
    if "ERROR" in upper:
        return ScanResult(ok=False, status="error", detail=resp)
    return ScanResult(ok=False, status="unknown", detail=resp)


async def ping_clamav() -> dict:
    host = settings.clamav_host
    port = settings.clamav_port
    ok = await asyncio.to_thread(_sync_ping, host, port)
    return {"ok": ok, "host": host, "port": port, "status": "ok" if ok else "unavailable"}


async def scan_bytes(data: bytes) -> ScanResult:
    return await asyncio.to_thread(
        _sync_scan, data, settings.clamav_host, settings.clamav_port
    )
