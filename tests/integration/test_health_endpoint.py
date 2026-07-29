"""Интеграционные тесты: приложение собирается, /health отвечает по контракту."""

from __future__ import annotations

from fastapi.testclient import TestClient

from dekoder.composition.bootstrap import create_app


def test_create_app_returns_configured_fastapi_instance() -> None:
    app = create_app()

    assert app.title == "dekoder"
    assert app.version == "0.1.0"


def test_health_endpoint_matches_contract() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "dekoder",
        "version": "0.1.0",
    }
