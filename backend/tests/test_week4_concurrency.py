from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import app
from app.config import settings


def create_session():
    with TestClient(app) as client:
        response = client.post(
            "/sessions",
            json={"mode": "mock"},
            headers={
                "X-Local-Auth": settings.local_auth_token
            },
        )

        return response


def test_concurrent_session_creation():

    total_sessions = 20

    with ThreadPoolExecutor(max_workers=10) as executor:
        responses = list(
            executor.map(
                lambda _: create_session(),
                range(total_sessions),
            )
        )

    # Check that all requests succeeded
    for response in responses:
        assert response.status_code == 201, response.text

    # Collect all session IDs
    session_ids = [
        response.json()["session_id"]
        for response in responses
    ]

    # Check that every session ID is unique
    assert len(session_ids) == total_sessions
    assert len(set(session_ids)) == total_sessions