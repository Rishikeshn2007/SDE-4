"""Track prompt versions and their metadata."""

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class PromptVersion:
    """Represent an individual prompt version."""

    version: str
    description: str
    created_at: str


class PromptVersionRegistry:
    """Maintain a registry of prompt versions."""

    def __init__(self):
        self._versions = {}

    def register(self, version, description):
        if not isinstance(version, str) or not version.strip():
            raise ValueError("Prompt version must be non-empty")

        if not isinstance(description, str) or not description.strip():
            raise ValueError("Description must be non-empty")

        if version in self._versions:
            raise ValueError("Prompt version already exists")

        prompt_version = PromptVersion(
            version=version,
            description=description,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        self._versions[version] = prompt_version
        return prompt_version

    def get(self, version):
        return self._versions.get(version)

    def list_versions(self):
        return list(self._versions.values())

    def latest(self):
        if not self._versions:
            return None

        return list(self._versions.values())[-1]
