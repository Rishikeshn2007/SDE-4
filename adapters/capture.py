"""Opt-in synthetic frame capture adapter.

No real screen capture is performed.
"""

from dataclasses import dataclass


@dataclass
class SyntheticFrame:
    frame_id: str
    data: bytes


class CaptureAdapter:
    def __init__(
        self,
        opt_in=False,
        sample_every_n=2,
        max_frame_bytes=1024,
    ):
        if sample_every_n < 1 or max_frame_bytes < 1:
            raise ValueError("Sampling and size limits must be positive")

        self.opt_in = opt_in
        self.sample_every_n = sample_every_n
        self.max_frame_bytes = max_frame_bytes
        self.frame_count = 0

    def set_opt_in(self, enabled):
        if not isinstance(enabled, bool):
            raise ValueError("Opt-in must be boolean")

        self.opt_in = enabled

    def process_frame(self, frame):
        if not self.opt_in:
            raise PermissionError("Capture requires explicit opt-in")

        if not isinstance(frame, SyntheticFrame):
            raise ValueError("Only synthetic frames are allowed")

        if not isinstance(frame.data, bytes):
            raise ValueError("Frame data must be bytes")

        if len(frame.data) > self.max_frame_bytes:
            raise ValueError("Frame exceeds maximum size limit")

        self.frame_count += 1

        if (self.frame_count - 1) % self.sample_every_n != 0:
            return None

        return frame