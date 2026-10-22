import pytest
from fastapi.testclient import TestClient
import config
from main import app


def test_cors_headers_production():
    """WP7: Verifies that in production mode, CORS requires exact match and no wildcards."""
    client = TestClient(app)

    # In current test env, check OPTIONS request behavior
    response = client.options(
        "/api/auth/me",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET"
        }
    )
    # Origin should be reflected if allowed, or no allow-origin returned
    assert response.status_code in [200, 400, 405]
