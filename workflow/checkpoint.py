
import json
import os
from pathlib import Path


CHECKPOINT_DIR = Path("checkpoints")


def save_checkpoint(
    plan_id,
    completed_steps,
    step_results,
    next_step_index,
    state,
    failed_step=None,
    idempotency_keys=None,
    audit_events=None,
    plan_signature=None,
):
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    checkpoint = {
        "plan_id": plan_id,
        "completed_steps": list(completed_steps),
        "step_results": step_results,
        "next_step_index": next_step_index,
        "state": state,
        "failed_step": failed_step,
        "idempotency_keys": idempotency_keys or {},
        "audit_events": audit_events or [],
        "plan_signature": plan_signature,
    }

    file_path = CHECKPOINT_DIR / f"{plan_id}.json"
    temporary_path = file_path.with_suffix(".tmp")

    with open(temporary_path, "w", encoding="utf-8") as file:
        json.dump(checkpoint, file, indent=4)

    os.replace(temporary_path, file_path)

    return file_path


def load_checkpoint(plan_id):
    file_path = CHECKPOINT_DIR / f"{plan_id}.json"

    if not file_path.exists():
        raise FileNotFoundError(
            f"Checkpoint not found for plan: {plan_id}"
        )

    with open(file_path, "r", encoding="utf-8") as file:
        checkpoint = json.load(file)

    if checkpoint.get("plan_id") != plan_id:
        raise ValueError("Checkpoint plan ID mismatch")

    return checkpoint
