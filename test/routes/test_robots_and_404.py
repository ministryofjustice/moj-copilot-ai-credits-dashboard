"""robots.txt and the page shown for an address that does not exist."""

from app.app import create_app


def _client():
    app = create_app(False)
    app.config["SECRET_KEY"] = "test_flask"
    return app.test_client()


def test_robots_txt_asks_crawlers_to_stay_out():
    resp = _client().get("/robots.txt")
    assert resp.status_code == 200
    assert "Disallow: /" in resp.get_data(as_text=True)


def test_an_unknown_address_shows_the_404_page():
    resp = _client().get("/no-such-page")
    assert resp.status_code == 404
    assert "Page not found (404 error)" in resp.get_data(as_text=True)
