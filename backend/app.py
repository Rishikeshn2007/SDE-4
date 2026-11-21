"""Flask API for the SDE-4 voicebot Week 3 integration.

Mock reasoning and workflow mode.
Local audio transcription through the speech blueprint.
No screen capture.
"""

from flask import Flask, jsonify, request

from schemas.context import (
    ContextItem,
    SourceReference,
    ScreenContext,
    ReasoningRequest,
)
from reasoning.grounded_answer import GroundedAnswerGenerator
from workflow.planner import WorkflowPlanner
from workflow.handoff import WorkflowHandoff
from observations.consent_manager import ConsentManager

from speech.routes import speech_blueprint


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024


answer_generator = GroundedAnswerGenerator()
workflow_planner = WorkflowPlanner()
workflow_handoff = WorkflowHandoff()
consent_manager = ConsentManager()

app.register_blueprint(speech_blueprint)


def build_reasoning_request(data):
    """Build and validate a reasoning request from JSON data."""

    if not isinstance(data, dict):
        raise ValueError("Request body must be a JSON object")

    question = data.get("question")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("A valid question is required")

    context_data = data.get("context", {})
    if not isinstance(context_data, dict):
        raise ValueError("Context must be an object")

    items_data = context_data.get("items", [])
    if not isinstance(items_data, list):
        raise ValueError("Context items must be a list")

    items = []

    for entry in items_data:
        if not isinstance(entry, dict):
            raise ValueError("Each context item must be an object")

        source_data = entry.get("source")
        if not isinstance(source_data, dict):
            raise ValueError("Each item must contain a source object")

        source = SourceReference(
            source_id=source_data.get("source_id"),
            source_type=source_data.get("source_type"),
            description=source_data.get("description", ""),
        )

        item = ContextItem(
            item_id=entry.get("item_id"),
            content=entry.get("content"),
            source=source,
        )

        item.validate()
        items.append(item)

    context = ScreenContext(
        context_id=context_data.get("context_id", "api_context"),
        items=items,
        capture_enabled=False,
    )

    context.validate()

    reasoning_request = ReasoningRequest(
        request_id=data.get("request_id", "api_request"),
        question=question.strip(),
        context=context,
    )

    reasoning_request.validate()
    return reasoning_request


@app.after_request
def add_cors_headers(response):
    """Allow approved local Vite frontend addresses to call Flask."""

    origin = request.headers.get("Origin")

    allowed_origins = {
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
    }

    # Remove any previously assigned CORS origin.
    response.headers.pop("Access-Control-Allow-Origin", None)

    if origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"

    response.headers["Access-Control-Allow-Headers"] = (
        "Content-Type, X-Audio-Consent"
    )

    response.headers["Access-Control-Allow-Methods"] = (
        "GET, POST, OPTIONS"
    )

    response.headers["Access-Control-Max-Age"] = "600"

    return response


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "success",
        "message": "SDE-4 backend is running",
        "mode": "mock",
    })


@app.route("/api/consent", methods=["GET"])
def get_consent():
    return jsonify({
        "consent_enabled": consent_manager.consent_enabled,
        "capture_mode": "synthetic_only",
    })


@app.route("/api/consent/enable", methods=["POST"])
def enable_consent():
    consent_manager.enable_consent()

    return jsonify({
        "status": "success",
        "consent_enabled": True,
        "message": "Synthetic capture consent enabled",
    })


@app.route("/api/consent/withdraw", methods=["POST"])
def withdraw_consent():
    consent_manager.withdraw_consent()

    return jsonify({
        "status": "success",
        "consent_enabled": False,
        "message": "Consent withdrawn and pending context cleared",
    })


@app.route("/api/context/answer", methods=["POST"])
def generate_answer():
    try:
        reasoning_request = build_reasoning_request(request.get_json())
        result = answer_generator.generate(reasoning_request)

        return jsonify({
            "status": result.status,
            "request_id": result.request_id,
            "answer": result.answer,
            "source_ids": result.source_ids,
        })

    except (ValueError, TypeError) as exc:
        return jsonify({
            "status": "error",
            "error": str(exc),
        }), 400


@app.route("/api/workflow/proposals", methods=["GET"])
def get_proposals():
    proposals = workflow_handoff.get_pending()

    return jsonify({
        "status": "success",
        "proposals": [
            {
                "proposal_id": proposal.proposal_id,
                "action_type": proposal.action_type,
                "description": proposal.description,
                "source_ids": proposal.source_ids,
                "requires_confirmation": proposal.requires_confirmation,
                "status": proposal.status,
            }
            for proposal in proposals
        ],
    })


@app.route("/api/workflow/proposals", methods=["POST"])
def create_proposal():
    try:
        data = request.get_json()
        reasoning_request = build_reasoning_request(data)

        if not isinstance(data, dict):
            raise ValueError("Request body must be an object")

        proposal = workflow_planner.create_proposal(
            reasoning_request,
            data.get("action_type"),
            data.get("description"),
            data.get("source_ids"),
        )

        result = workflow_handoff.submit(proposal)

        return jsonify({
            "status": "success",
            "proposal": {
                "proposal_id": proposal.proposal_id,
                "action_type": proposal.action_type,
                "description": proposal.description,
                "source_ids": proposal.source_ids,
                "requires_confirmation": proposal.requires_confirmation,
                "status": proposal.status,
            },
            "handoff": result,
        }), 201

    except (ValueError, TypeError) as exc:
        return jsonify({
            "status": "error",
            "error": str(exc),
        }), 400


@app.route(
    "/api/workflow/proposals/<proposal_id>/approve",
    methods=["POST"],
)
def approve_proposal(proposal_id):
    try:
        result = workflow_handoff.approve(proposal_id)
        return jsonify(result)

    except ValueError as exc:
        return jsonify({
            "status": "error",
            "error": str(exc),
        }), 404


@app.route(
    "/api/workflow/proposals/<proposal_id>/reject",
    methods=["POST"],
)
def reject_proposal(proposal_id):
    try:
        result = workflow_handoff.reject(proposal_id)
        return jsonify(result)

    except ValueError as exc:
        return jsonify({
            "status": "error",
            "error": str(exc),
        }), 404


@app.errorhandler(413)
def request_too_large(error):
    return jsonify({
        "status": "error",
        "error": "Request is too large",
    }), 413


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
    )