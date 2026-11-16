"""Consent management for capture and pending observations."""


class ConsentManager:

    def __init__(self, capture_adapter=None):
        self._consent_enabled = False
        self._pending_observations = []
        self._capture_adapter = capture_adapter

        # Capture must remain disabled by default.
        if self._capture_adapter is not None:
            self._capture_adapter.set_opt_in(False)

    @property
    def consent_enabled(self):
        return self._consent_enabled

    def enable_consent(self):
        self._consent_enabled = True

        if self._capture_adapter is not None:
            self._capture_adapter.set_opt_in(True)

    def add_observation(self, observation):
        if not self._consent_enabled:
            raise PermissionError("Consent is not enabled")

        if observation is None:
            raise ValueError("Observation cannot be empty")

        self._pending_observations.append(observation)

    def get_pending_observations(self):
        if not self._consent_enabled:
            return []

        return list(self._pending_observations)

    def withdraw_consent(self):
        self._consent_enabled = False
        self._pending_observations.clear()

        if self._capture_adapter is not None:
            self._capture_adapter.set_opt_in(False)

    def clear(self):
        self._pending_observations.clear()