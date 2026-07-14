from api.main import app, frontend, health


def test_api_health_smoke():
    payload = health()

    assert payload["status"] == "ok"
    assert payload["app"] == "CMMTrader"
    assert payload["paperOnly"] is True


def test_frontend_fallback_before_or_after_build():
    response = frontend("")

    assert response is not None
    assert any(route.path == "/api/health" for route in app.routes)
