"""Fetch and verify the version-pinned upstream Chromium seccomp policy."""

import argparse
import hashlib
import json
import ssl
import urllib.request
from pathlib import Path

PROFILE_URL = "https://raw.githubusercontent.com/microsoft/playwright/v1.58.0/utils/docker/seccomp_profile.json"
PROFILE_SHA256 = "cc3e61cabda6bbc1e53e54d27ba4d55a9d3be829b6dd1a596f4a7b31b1cc7849"
PROFILE_PATH = Path("var/opensandbox/chromium-seccomp.json")


def verified_profile() -> str:
    data = PROFILE_PATH.read_bytes()
    if hashlib.sha256(data).hexdigest() != PROFILE_SHA256:
        raise RuntimeError("Chromium seccomp policy hash mismatch")
    return json.dumps(json.loads(data), separators=(",", ":"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile-source", help="Use an already downloaded upstream profile")
    args = parser.parse_args()
    if args.profile_source:
        content = Path(args.profile_source).read_bytes()
    else:
        import certifi

        with urllib.request.urlopen(
            PROFILE_URL, context=ssl.create_default_context(cafile=certifi.where()), timeout=20
        ) as response:
            content = response.read(128_000)
    if hashlib.sha256(content).hexdigest() != PROFILE_SHA256:
        raise RuntimeError("downloaded seccomp policy hash mismatch")
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_bytes(content)
    print("Verified Chromium seccomp policy installed")
