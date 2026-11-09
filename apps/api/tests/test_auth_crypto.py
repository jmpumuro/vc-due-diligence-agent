from thesis_api.services.auth_crypto import (
    hash_password,
    hash_setup_token,
    new_setup_token,
    verify_password,
)


def test_password_roundtrip() -> None:
    h = hash_password("correct-horse-battery")
    assert verify_password(h, "correct-horse-battery")
    assert not verify_password(h, "wrong")


def test_setup_token_hash() -> None:
    raw, digest = new_setup_token()
    assert hash_setup_token(raw) == digest
    assert len(digest) == 64
