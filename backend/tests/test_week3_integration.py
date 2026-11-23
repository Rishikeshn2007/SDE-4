from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.events import add_event


AUTH_HEADERS = {
    "X-Local-Auth": settings.local_auth_token,
}

client = TestClient(
    app,
    headers=AUTH_HEADERS,
)


def test_complete_mock_pipeline():

    session_response = client.post(
        "/sessions",
        json={"mode": "mock"},
    )

    assert session_response.status_code == 201

    session_id = session_response.json()["session_id"]

    response = client.post(
        f"/sessions/{session_id}/process"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "success"
    assert data["mode"] == "mock"

    modules = data["modules"]

    assert [module["module"] for module in modules] == [
        "audio",
        "transcription",
        "reasoning",
        "workflow",
    ]

    correlation_id = data["correlation_id"]

    for module in modules:
        assert module["session_id"] == session_id
        assert module["correlation_id"] == correlation_id

    assert modules[1]["source"] == modules[0]["audio_reference"]
    assert modules[2]["input_text"] == modules[1]["transcript"]
    assert modules[3]["input_intent"] == modules[2]["intent"]


def test_health_aggregates_all_modules():

    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "healthy"

    assert set(data["modules"].keys()) == {
        "audio",
        "transcription",
        "reasoning",
        "workflow",
    }

    for module in data["modules"].values():
        assert module["status"] == "healthy"


def test_external_access_is_rejected():

    external_client = TestClient(
        app,
        client=("8.8.8.8", 12345),
        headers=AUTH_HEADERS,
    )

    response = external_client.get(
        "/sessions/test-session"
    )

    assert response.status_code == 403

    assert response.json()["error"]["code"] == "LOCAL_ACCESS_ONLY"


def test_missing_authentication_key_is_rejected():

    unauthenticated_client = TestClient(app)

    response = unauthenticated_client.get(
        "/sessions/test-session"
    )

    assert response.status_code == 401

    error = response.json()["error"]

    assert error["code"] == "LOCAL_AUTH_REQUIRED"
    assert error["retryable"] is False


def test_pipeline_events_are_recorded():

    session_response = client.post(
        "/sessions",
        json={"mode": "mock"},
    )

    session_id = session_response.json()["session_id"]

    response = client.post(
        f"/sessions/{session_id}/process"
    )

    assert response.status_code == 200

    from app.events import events_store

    session_events = events_store.get(session_id, [])

    gateway_events = [
        event
        for event in session_events
        if event["event_type"] == "gateway_processed"
    ]

    assert len(gateway_events) == 4

    assert [
        event["data"]["module"]
        for event in gateway_events
    ] == [
        "audio",
        "transcription",
        "reasoning",
        "workflow",
    ]


def test_event_replay_returns_only_missed_events():

    session_id = "replay-review-test"

    add_event(session_id, "first_event", {"number": 1})
    add_event(session_id, "second_event", {"number": 2})
    add_event(session_id, "third_event", {"number": 3})
    add_event(session_id, "fourth_event", {"number": 4})

    response = client.get(
        f"/sessions/{session_id}/events",
        headers={
            **AUTH_HEADERS,
            "Last-Event-ID": "2",
        },
    )

    assert response.status_code == 200

    content = response.text

    assert "id: 3\n" in content
    assert "id: 4\n" in content

    assert "id: 1\n" not in content
    assert "id: 2\n" not in content

    assert "third_event" in content
    assert "fourth_event" in content

    assert "first_event" not in content
    assert "second_event" not in content


def test_rate_limit_returns_typed_429_error(monkeypatch):

    # Make the test limit two requests per window
    monkeypatch.setattr(
        settings,
        "rate_limit_requests",
        1,
    )

    monkeypatch.setattr(
        settings,
        "rate_limit_window",
        60,
    )

    # Use a separate loopback address for an isolated counter
    limited_client = TestClient(
        app,
        client=("127.0.0.2", 12345),
        headers=AUTH_HEADERS,
    )

    session_response = limited_client.post(
        "/sessions",
        json={"mode": "mock"},
    )

    assert session_response.status_code == 201

    session_id = session_response.json()["session_id"]

    first_response = limited_client.post(
        f"/sessions/{session_id}/process"
    )

    assert first_response.status_code == 200

    second_response = limited_client.post(
        f"/sessions/{session_id}/process"
    )

    assert second_response.status_code == 429

    error = second_response.json()["error"]

    assert error["code"] == "RATE_LIMIT_EXCEEDED"
    assert error["retryable"] is False
    assert error["correlation_id"]