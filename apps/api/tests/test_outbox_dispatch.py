from thesis_api.services.outbox import notification_copy, sanitize_outbox_payload


def test_sanitize_rejects_private_keys() -> None:
    safe = sanitize_outbox_payload({"decision": "approve", "document_text": "SECRET", "raw": "x"})
    assert safe == {"decision": "approve"}


def test_notification_copy_watchlist() -> None:
    title, _ = notification_copy("watchlist.reassess", {"company_name": "Acme"})
    assert "Watchlist" in title
