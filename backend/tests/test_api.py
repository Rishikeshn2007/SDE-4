import pytest

from datetime import timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.sessions import (
    SessionRepository,
    SessionState,
    InvalidSessionTransition,
)
from app.events import add_event, events_store
from app.config import Settings

import app.sessions as sessions_module


client = TestClient(app)


# EXISTING API TESTS

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

    assert first.json()["session_id"] == second.json()["session_id"]


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


# NEW REVIEWER-REQUESTED TESTS


def test_illegal_session_transition():
    repository = SessionRepository()
    session = repository.create()

    with pytest.raises(InvalidSessionTransition):
        repository.update_state(
            session.session_id,
            SessionState.COMPLETED,
        )


def test_pause_and_resume_session():
    repository = SessionRepository()
    session = repository.create()

    repository.update_state(
        session.session_id,
        SessionState.ACTIVE,
    )

    paused = repository.update_state(
        session.session_id,
        SessionState.PAUSED,
    )

    assert paused.state == SessionState.PAUSED

    resumed = repository.update_state(
        session.session_id,
        SessionState.ACTIVE,
    )

    assert resumed.state == SessionState.ACTIVE


def test_illegal_resume_transition():
    repository = SessionRepository()
    session = repository.create()

    repository.update_state(session.session_id, SessionState.ACTIVE)
    repository.update_state(session.session_id, SessionState.PAUSED)
    repository.update_state(session.session_id, SessionState.STOPPING)
    repository.update_state(session.session_id, SessionState.COMPLETED)

    with pytest.raises(InvalidSessionTransition):
        repository.update_state(session.session_id, SessionState.ACTIVE)


def test_session_expiry(monkeypatch):
    repository = SessionRepository()
    session = repository.create()

    monkeypatch.setattr(
        sessions_module,
        "SESSION_TTL",
        timedelta(seconds=0),
    )

    expired = repository.get(session.session_id)

    assert expired.state == SessionState.EXPIRED


def test_oversized_event_payload():
    large_data = {
        "message": "A" * (
            sessions_module.settings.max_event_payload_size + 100
        )
    }

    with pytest.raises(ValueError):
        add_event(
            "test-session",
            "test_event",
            large_data,
        )


def test_invalid_configuration(monkeypatch):
    monkeypatch.setenv("APP_ENV", "invalid")

    with pytest.raises(ValueError):
        Settings()


def test_invalid_session_ttl_configuration(monkeypatch):
    monkeypatch.setenv("SESSION_TTL_MINUTES", "0")

    with pytest.raises(ValueError):
        Settings()


def test_event_streaming_order():
    session_id = "order-test-session"

    add_event(session_id, "first_event", {"number": 1})
    add_event(session_id, "second_event", {"number": 2})
    add_event(session_id, "third_event", {"number": 3})

    response = client.get(
        f"/sessions/{session_id}/events"
    )

    assert response.status_code == 200

    content = response.text

    first = content.index("first_event")
    second = content.index("second_event")
    third = content.index("third_event")

    assert first < second < third