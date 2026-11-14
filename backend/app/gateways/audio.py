from datetime import datetime, timezone


class AudioGateway:
    def process(self, session_id: str, correlation_id: str):
        return {
            "module": "audio",
            "session_id": session_id,
            "correlation_id": correlation_id,
            "status": "success",
            "mode": "mock",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }