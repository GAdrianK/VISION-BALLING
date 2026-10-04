def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    response_alias = client.get("/api/health")
    assert response_alias.status_code == 200
    assert response_alias.json() == {"status": "ok"}

