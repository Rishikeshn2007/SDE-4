from app.mock_modules import MockAudioModule


class AudioGateway:

    def __init__(self):
        self.module = MockAudioModule()

    def health(self):
        return self.module.health()

    def process(self, session_id: str, correlation_id: str):
        return self.module.process(
            session_id,
            correlation_id,
        )