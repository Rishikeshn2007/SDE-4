
import json
import time
from pathlib import Path


AUDIT_DIR = Path("audit_logs")


def record_event(events, event_type, step_id, message):
    event = {
        "event": event_type,
        "step_id": step_id,
        "message": message,
        "timestamp": time.time(),
    }

    events.append(event)
    return event


def save_audit_log(plan_id, events):
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    file_path = AUDIT_DIR / f"{plan_id}.json"

    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(events, file, indent=4)

    return file_path


def load_audit_log(plan_id):
    file_path = AUDIT_DIR / f"{plan_id}.json"

    if not file_path.exists():
        raise FileNotFoundError(
            f"Audit log not found for plan: {plan_id}"
        )

    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)
