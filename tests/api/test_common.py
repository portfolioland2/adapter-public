def test_ping(client):
    url = "/api/ping"
    response = client.get(url)

    assert response.json() == "pong"
