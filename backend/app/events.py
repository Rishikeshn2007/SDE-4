
import json
import asyncio

from datetime import datetime, timezone
from threading import Lock

from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import StreamingResponse

from app.config import settings


router = APIRouter()

events_store = {}
events_lock = Lock()

MAX_PAYLOAD_SIZE = settings.max_event_payload_size


def add_event(session_id: str, event_type: str, data: dict):

    if not isinstance(data, dict):
        raise ValueError("Event data must be a dictionary")

    payload = json.dumps(data)

    if len(payload.encode("utf-8")) > MAX_PAYLOAD_SIZE:
        raise ValueError("Event payload is too large")

    with events_lock:
        session_events = events_store.setdefault(session_id, [])

        event = {
            "id": len(session_events) + 1,
            "session_id": session_id,
            "event_type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        session_events.append(event)

    return event


@router.get(
    "/sessions/{session_id}/events",
    summary="Stream Events",
    description="Stream session events using Server-Sent Events. Use Last-Event-ID to receive only events that have not yet been received.",
    responses={
        200: {
            "description": "Session events streamed successfully.",
            "content": {
                "text/event-stream": {
                    "example": (
                        "id: 1\n"
                        "event: session_created\n"
                        'data: {"id": 1, "session_id": "123e4567-e89b-12d3-a456-426614174000", '
                        '"event_type": "session_created", "data": {"state": "created"}}\n\n'
                    )
                }
            }
        },
        400: {
            "description": "Invalid event ID."
        },
        404: {
            "description": "No events found for this session."
        }
    }
)
async def stream_events(
    session_id: str,
    last_event_id: int = Header(
        default=0,
        alias="Last-Event-ID",
        description="Return only events with an ID greater than this value.",
        examples=[0, 1, 5],
    ),
):
    if last_event_id < 0:
        raise HTTPException(
            status_code=400,
            detail="Invalid event ID",
        )

    with events_lock:
        if session_id not in events_store:
            raise HTTPException(
                status_code=404,
                detail="No events found for this session",
            )

        events = [
            event
            for event in events_store[session_id]
            if event["id"] > last_event_id
        ]

    async def event_generator():

        for event in events:
            yield f"id: {event['id']}\n"
            yield f"event: {event['event_type']}\n"
            yield f"data: {json.dumps(event)}\n\n"

            await asyncio.sleep(0.1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )