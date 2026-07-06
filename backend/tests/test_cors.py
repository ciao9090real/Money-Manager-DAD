from fastapi.testclient import TestClient

from app.main import app


def test_localhost_development_port_is_allowed():
    with TestClient(app) as client:
        response = client.options(
            "/auth/demo",
            headers={
                "Origin": "http://localhost:3001",
                "Access-Control-Request-Method": "POST",
            },
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3001"
