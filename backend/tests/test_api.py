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
    assert response.json() == {"status": "healthy"}


def test_readiness():
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_request_and_correlation_ids():
    response = client.get("/health")

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert "X-Correlation-ID" in response.headers


def test_create_mock_session():
    response = client.post(
        "/sessions",
        json={"mode": "mock"},
    )

    assert response.status_code == 201

    data = response.json()
    assert data["state"] == "created"
    assert "session_id" in data
    assert data["session_id"]


def test_get_existing_session():
    create_response = client.post(
        "/sessions",
        json={"mode": "mock"},
    )

    session_id = create_response.json()["session_id"]

    response = client.get(f"/sessions/{session_id}")

    assert response.status_code == 200
    assert response.json()["session_id"] == session_id
    assert response.json()["state"] == "created"


def test_update_session_state():
    create_response = client.post(
        "/sessions",
        json={"mode": "mock"},
    )
    session_id = create_response.json()["session_id"]

    response = client.patch(
        f"/sessions/{session_id}/state",
        json={"state": "active"},
    )

    assert response.status_code == 200
    assert response.json()["state"] == "active"


def test_missing_session_returns_standard_error():
    response = client.get("/sessions/nonexistent-session")

    assert response.status_code == 404

    error = response.json()["error"]
    assert error["code"] == "SESSION_NOT_FOUND"
    assert error["retryable"] is False
    assert "correlation_id" in error
    assert "message_safe_for_user" in error
    assert "details_redacted" in error
    