from app.app import create_app


def test_admin_pooled_renders():
    client = create_app(False).test_client()
    resp = client.get("/admin/pooled")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'data-chart="pooledTree"' in body
