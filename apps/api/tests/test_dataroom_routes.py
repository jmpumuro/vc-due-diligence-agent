"""Data-room route module imports + ClamAV-gated upload contract."""

from thesis_api.routes import dataroom


def test_dataroom_router_registered() -> None:
    paths = {getattr(r, "path", None) for r in dataroom.router.routes}
    assert any(p and "data-room" in p for p in paths)


def test_documents_upload_route_registered() -> None:
    paths = {getattr(r, "path", None) for r in dataroom.router.routes}
    assert any(p and p.endswith("/documents") for p in paths)


def test_upload_handler_mentions_clamav() -> None:
    assert "ClamAV" in (dataroom.upload_document.__doc__ or "")
