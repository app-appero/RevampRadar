def test_create_audit_rejects_invalid_url(client, monkeypatch) -> None:
    monkeypatch.setattr("app.api.audits.execute_audit", lambda audit_id: None)
    response = client.post("/audits", json={"url": "ftp://example.com"})
    assert response.status_code == 422


def test_create_and_get_audit(client, monkeypatch) -> None:
    monkeypatch.setattr("app.api.audits.execute_audit", lambda audit_id: None)
    created = client.post("/audits", json={"url": "https://Example.com/hotel/"})
    assert created.status_code == 202
    payload = created.json()
    assert payload["status"] == "queued"
    assert payload["normalized_url"] == "https://example.com/hotel"
    assert payload["domain"] == "example.com"

    fetched = client.get(f"/audits/{payload['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == payload["id"]


def test_missing_audit_returns_404(client) -> None:
    response = client.get("/audits/11111111-1111-1111-1111-111111111111")
    assert response.status_code == 404
