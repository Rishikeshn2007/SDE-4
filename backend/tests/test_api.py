from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_health():
    response = client.get("/health")
    assert response.status_code == 200


def test_readiness():
    response = client.get("/ready")
    assert response.status_code == 200


def test_request_and_correlation_ids():
    response = client.get("/health")
    assert "X-Request-ID" in response.headers
    assert "X-Correlation-ID" in response.headers


def test_create_mock_session():
    response = client.post(
        "/sessions",
        json={"mode": "mock"},
    )

    assert response.status_code == 201
    assert response.json()["state"] == "created"


def test_get_existing_session():
    created = client.post(
        "/sessions",
        json={"mode": "mock"},
    )

    session_id = created.json()["session_id"]

    response = client.get(f"/sessions/{session_id}")

    assert response.status_code == 200


def test_update_session_state():
    created = client.post(
        "/sessions",
        json={"mode": "mock"},
    )

    session_id = created.json()["session_id"]

    response = client.patch(
        f"/sessions/{session_id}/state",
        json={"state": "active"},
    )

    assert response.status_code == 200
    assert response.json()["state"] == "active"


def test_missing_session():
    response = client.get("/sessions/nonexistent")

    assert response.status_code == 404


def test_idempotency():
    headers = {"Idempotency-Key": "week2-test-001"}

    first = client.post(
        "/sessions",
        json={"mode": "mock"},
        headers=headers,
    )

    second = client.post(
        "/sessions",
        json={"mode": "mock"},
        headers=headers,
    )

    assert first.status_code == 201
    assert second.status_code == 201

    assert (
        first.json()["session_id"]
        == second.json()["session_id"]
    )


def test_event_streaming():
    created = client.post(
        "/sessions",
        json={"mode": "mock"},
    )

    session_id = created.json()["session_id"]

    response = client.get(
        f"/sessions/{session_id}/events"
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert "session_created" in response.text


def test_stop_session():
    created = client.post(
        "/sessions",
        json={"mode": "mock"},
    )

    session_id = created.json()["session_id"]

    response = client.post(
        f"/sessions/{session_id}/stop"
    )

    assert response.status_code == 200
    assert response.json()["state"] == "completed"


def test_invalid_session_state():
    response = client.post(
        "/sessions",
        json={"mode": "invalid"},
    )

    assert response.status_code == 400