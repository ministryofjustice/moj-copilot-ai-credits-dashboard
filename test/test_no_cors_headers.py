"""CORS removal (OWASP A05).

This is a same-origin, server-rendered app with no cross-origin API
consumers, so no response should ever invite a foreign origin to read it.
"""

import pytest

from app.app import create_app


@pytest.fixture()
def client():
    return create_app(False).test_client()


def test_no_cors_headers_on_cross_origin_request(client):
    response = client.get("/", headers={"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in response.headers
