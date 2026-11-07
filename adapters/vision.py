"""Mock OCR and vision adapter."""

from abc import ABC, abstractmethod


class VisionAdapter(ABC):

    @abstractmethod
    def extract_text(self, frame):
        pass


class MockVisionAdapter(VisionAdapter):

    def extract_text(self, frame):
        if not isinstance(frame.data, bytes):
            raise ValueError("Invalid frame data")

        try:
            return frame.data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("Unable to extract text from frame") from exc