def test_post_chat_coach(client):
    payload = {
        "message": "Explique-moi comment sortir du pressing haut",
        "mode": "coach"
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["mode"] == "coach"
    assert "answer" in json_data
    assert "sources" in json_data
    assert len(json_data["sources"]) > 0

def test_post_chat_analyst(client):
    payload = {
        "message": "Quels sont les principes tactiques d'un inverted fullback ?",
        "mode": "analyst"
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["mode"] == "analyst"
    assert "Observations Structurelles" in json_data["answer"]

def test_post_chat_fan(client):
    payload = {
        "message": "C'est quoi un pivot ?",
        "mode": "fan"
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["mode"] == "fan"
    assert "L'Avis des Fans" in json_data["answer"]
