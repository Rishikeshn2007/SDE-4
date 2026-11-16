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
        if not isinstance(opt_in, bool):
            raise ValueError("Opt-in must be boolean")

        if (
            not isinstance(sample_every_n, int)
            or isinstance(sample_every_n, bool)
            or sample_every_n < 1
        ):
            raise ValueError("Sampling interval must be a positive integer")

        if (
            not isinstance(max_frame_bytes, int)
            or isinstance(max_frame_bytes, bool)
            or max_frame_bytes < 1
        ):
            raise ValueError("Maximum frame size must be a positive integer")

        self.opt_in = opt_in
        self.sample_every_n = sample_every_n
        self.max_frame_bytes = max_frame_bytes
        self.frame_count = 0

    def set_opt_in(self, enabled):
        if not isinstance(enabled, bool):
            raise ValueError("Opt-in must be boolean")

        self.opt_in = enabled

        # Reset sampling state when consent is withdrawn.
        if not enabled:
            self.frame_count = 0

    def process_frame(self, frame):
        if not self.opt_in:
            raise PermissionError("Capture requires explicit opt-in")

        if not isinstance(frame, SyntheticFrame):
            raise ValueError("Only synthetic frames are allowed")

        if not isinstance(frame.frame_id, str) or not frame.frame_id.strip():
            raise ValueError("Frame ID must be a non-empty string")

        if not isinstance(frame.data, bytes):
            raise ValueError("Frame data must be bytes")

        if len(frame.data) > self.max_frame_bytes:
            raise ValueError("Frame exceeds maximum size limit")

        self.frame_count += 1

        if (self.frame_count - 1) % self.sample_every_n != 0:
            return None

        return frame