from datetime import datetime

from fastapi.testclient import TestClient

from hello_fastapi.api.app import SERVICE, app

client = TestClient(app)


def test_hello_names_the_service_and_the_time() -> None:
    response = client.get("/hello")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == SERVICE
    assert body["message"] == "hello"
    assert datetime.fromisoformat(body["time"]).tzinfo is not None


def test_healthz() -> None:
    assert client.get("/healthz").json() == {"status": "ok"}
