import os


class Settings:
    def __init__(self):
        self.environment = os.getenv("APP_ENV", "development")
        self.session_ttl_minutes = int(
            os.getenv("SESSION_TTL_MINUTES", "30")
        )
        self.max_event_payload_size = int(
            os.getenv("MAX_EVENT_PAYLOAD_SIZE", "4096")
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

        if self.environment not in (
            "development",
            "testing",
            "production",
        ):
            raise ValueError("Invalid APP_ENV value")


settings = Settings()