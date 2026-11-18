from app.mock_modules import MockReasoningModule


class ReasoningGateway:
    def __init__(self):
        self.module = MockReasoningModule()

    def health(self):
        return self.module.health()

    def process(self, session_id, correlation_id, transcription_data):
        return self.module.process(
            session_id, correlation_id, transcription_data
        )