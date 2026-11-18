from app.mock_modules import MockTranscriptionModule


class TranscriptionGateway:
    def __init__(self):
        self.module = MockTranscriptionModule()

    def health(self):
        return self.module.health()

    def process(self, session_id, correlation_id, audio_data):
        return self.module.process(
            session_id, correlation_id, audio_data
        )