from datetime import datetime, timezone


class WorkflowGateway:
    def process(self, session_id: str, correlation_id: str):
        return {
            "module": "workflow",
            "session_id": session_id,
            "correlation_id": correlation_id,
            "status": "success",
            "mode": "mock",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }