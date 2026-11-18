from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


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
    )

    response = external_client.get(
        "/sessions/test-session"
    )

    assert response.status_code == 403

    assert response.json()["error"]["code"] == "LOCAL_ACCESS_ONLY"


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