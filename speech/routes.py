"""Local speech transcription API."""

from flask import Blueprint, jsonify, request
from speech.transcriber import LocalTranscriber

speech_blueprint = Blueprint("speech", __name__)

_transcriber = None


@speech_blueprint.route("/api/transcribe", methods=["POST"])
def transcribe_audio():
    global _transcriber

    # Require explicit consent for each audio upload.
    if request.headers.get("X-Audio-Consent") != "true":
        return jsonify({
            "status": "error",
            "error": "Explicit audio consent is required",
        }), 403

    audio_file = request.files.get("audio")

    if audio_file is None:
        return jsonify({
            "status": "error",
            "error": "WAV audio file is required",
        }), 400

    try:
        audio_bytes = audio_file.read()

        if not audio_bytes:
            return jsonify({
                "status": "error",
                "error": "Audio file is empty",
            }), 400

        if _transcriber is None:
            _transcriber = LocalTranscriber()

        transcript = _transcriber.transcribe_wav(audio_bytes)

        return jsonify({
            "status": "success",
            "transcript": transcript,
            "mode": "local_vosk",
        })

    except (ValueError, OSError) as exc:
        return jsonify({
            "status": "error",
            "error": str(exc),
        }), 400
    except Exception:
        return jsonify({
            "status": "error",
            "error": "Local transcription failed",
        }), 500