from datetime import datetime, timezone


def get_timestamp():
    return datetime.now(timezone.utc).isoformat()


class MockAudioModule:

    def health(self):
        return {"module": "audio", "status": "healthy", "mode": "mock"}

    def process(self, session_id, correlation_id):
        return {
            "module": "audio",
            "session_id": session_id,
            "correlation_id": correlation_id,
            "audio_reference": f"mock-audio-{session_id}",
            "status": "success",
            "message": "Mock audio received",
            "timestamp": get_timestamp(),
        }


class MockTranscriptionModule:

    def health(self):
        return {"module": "transcription", "status": "healthy", "mode": "mock"}

    def process(self, session_id, correlation_id, audio_data):
        return {
            "module": "transcription",
            "session_id": session_id,
            "correlation_id": correlation_id,
            "transcript": "Hello, this is a mock voice input.",
            "source": audio_data["audio_reference"],
            "status": "success",
            "timestamp": get_timestamp(),
        }


class MockReasoningModule:

    def health(self):
        return {"module": "reasoning", "status": "healthy", "mode": "mock"}

    def process(self, session_id, correlation_id, transcription_data):
        return {
            "module": "reasoning",
            "session_id": session_id,
            "correlation_id": correlation_id,
            "input_text": transcription_data["transcript"],
            "intent": "general_query",
            "response": "Mock reasoning completed successfully.",
            "status": "success",
            "timestamp": get_timestamp(),
        }


class MockWorkflowModule:

    def health(self):
        return {"module": "workflow", "status": "healthy", "mode": "mock"}

    def process(self, session_id, correlation_id, reasoning_data):
        return {
            "module": "workflow",
            "session_id": session_id,
            "correlation_id": correlation_id,
            "input_intent": reasoning_data["intent"],
            "result": "Mock workflow completed.",
            "status": "success",
            "timestamp": get_timestamp(),
        }