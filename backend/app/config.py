import os


class Settings:
    def __init__(self):
        self.environment = os.getenv(
            "APP_ENV", "development"
        )

        self.session_ttl_minutes = int(
            os.getenv("SESSION_TTL_MINUTES", "30")
        )

        self.max_event_payload_size = int(
            os.getenv("MAX_EVENT_PAYLOAD_SIZE", "4096")
        )

        self.mock_mode = os.getenv(
            "MOCK_MODE", "true"
        ).lower() in ("true", "1", "yes")

        self.rate_limit_requests = int(
            os.getenv("RATE_LIMIT_REQUESTS", "10")
        )

        self.rate_limit_window = int(
            os.getenv("RATE_LIMIT_WINDOW", "60")
        )

        self.local_auth_token = os.getenv(
            "LOCAL_AUTH_TOKEN", "dev-local-token"
        )

        self.validate()

    def validate(self):
        if self.session_ttl_minutes <= 0:
            raise ValueError(
                "SESSION_TTL_MINUTES must be positive"
            )

        if self.max_event_payload_size <= 0:
            raise ValueError(
                "MAX_EVENT_PAYLOAD_SIZE must be positive"
            )

        if self.rate_limit_requests <= 0:
            raise ValueError(
                "RATE_LIMIT_REQUESTS must be positive"
            )

        if self.rate_limit_window <= 0:
            raise ValueError(
                "RATE_LIMIT_WINDOW must be positive"
            )

        if self.environment not in (
            "development",
            "testing",
            "production",
        ):
            raise ValueError("Invalid APP_ENV value")


settings = Settings()