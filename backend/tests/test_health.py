def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == "healthy"
    assert json_data["project"] == "Football IQ Assistant"
    assert "version" in json_data
