from app.mock_modules import MockWorkflowModule


class WorkflowGateway:
    def __init__(self):
        self.module = MockWorkflowModule()

    def health(self):
        return self.module.health()

    def process(self, session_id, correlation_id, reasoning_data):
        return self.module.process(
            session_id, correlation_id, reasoning_data
        )