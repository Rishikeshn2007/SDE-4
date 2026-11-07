"""Audio device adapter interface and mock implementation (Week 2 - Audio & VAD).

Provides device selection, permission state management, and stream capture
abstractions. Works deterministically in mock mode with zero physical hardware.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Iterator, List, Optional, Sequence

from .mock_source import MockMicrophone
from .schemas import (
    AudioChunk,
    AudioError,
    AudioErrorCode,
    AudioFormat,
)


class PermissionState(str, Enum):
    """Represents OS microphone permission status."""

    GRANTED = "granted"
    DENIED = "denied"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class DeviceInfo:
    """Metadata describing an audio input device.

    Fields:
        id:           Unique identifier for the device.
        name:         Human-readable device name.
        sample_rate:  Native or default sample rate (Hz).
        channels:     Number of input channels (1 = mono, 2 = stereo).
        is_default:   Whether this is the primary input device.
        is_supported: Whether this device format/driver is supported.
    """

    id: str
    name: str
    sample_rate: int = 16000
    channels: int = 1
    is_default: bool = False
    is_supported: bool = True


DEFAULT_MOCK_DEVICES: Sequence[DeviceInfo] = (
    DeviceInfo(
        id="mock-default",
        name="Mock Built-in Microphone",
        sample_rate=16000,
        channels=1,
        is_default=True,
        is_supported=True,
    ),
    DeviceInfo(
        id="mock-studio",
        name="Mock Studio USB Microphone",
        sample_rate=48000,
        channels=2,
        is_default=False,
        is_supported=True,
    ),
    DeviceInfo(
        id="mock-unsupported",
        name="Mock Legacy Unsupported Hardware",
        sample_rate=96000,
        channels=8,
        is_default=False,
        is_supported=False,
    ),
)


class DeviceAdapter(ABC):
    """Abstract interface for audio input device adapters."""

    @abstractmethod
    def list_devices(self) -> List[DeviceInfo]:
        """Return list of available audio input devices."""

    @abstractmethod
    def select_device(self, device_id: str) -> DeviceInfo:
        """Select active device by ID.

        Raises:
            AudioError: DEVICE_NOT_FOUND if id does not exist.
            AudioError: DEVICE_UNSUPPORTED if device is not supported.
        """

    @abstractmethod
    def get_selected_device(self) -> DeviceInfo:
        """Return currently selected device."""

    @abstractmethod
    def get_permission_state(self) -> PermissionState:
        """Get current microphone permission state."""

    @abstractmethod
    def request_permission(self) -> PermissionState:
        """Request microphone permission from the system or user."""

    @abstractmethod
    def open(self, fmt: Optional[AudioFormat] = None) -> None:
        """Open audio stream for capturing.

        Raises:
            AudioError: PERMISSION_DENIED if permission is denied.
            AudioError: DEVICE_UNSUPPORTED if permission or device is unsupported.
        """

    @abstractmethod
    def read_chunk(self) -> Optional[AudioChunk]:
        """Read the next available chunk, or None if stream is finished/empty."""

    @abstractmethod
    def close(self) -> None:
        """Close audio stream and release resources."""

    @property
    @abstractmethod
    def is_open(self) -> bool:
        """True if the audio stream is currently open."""


class MockDeviceAdapter(DeviceAdapter):
    """Deterministic mock audio device adapter for tests and offline development.

    Supports configurable permission states, custom device inventories, and
    synthetic audio chunk generation using :class:`MockMicrophone`.
    """

    def __init__(
        self,
        devices: Optional[Sequence[DeviceInfo]] = None,
        permission_state: PermissionState = PermissionState.GRANTED,
        mock_source: Optional[MockMicrophone] = None,
        chunks: Optional[Sequence[AudioChunk]] = None,
    ) -> None:
        self._devices: dict[str, DeviceInfo] = {
            d.id: d for d in (devices if devices is not None else DEFAULT_MOCK_DEVICES)
        }
        default_dev = next(
            (d for d in self._devices.values() if d.is_default),
            next(iter(self._devices.values())) if self._devices else None,
        )
        if default_dev is None:
            raise AudioError(AudioErrorCode.INVALID_PARAMETER, "Mock device list cannot be empty")
        self._selected_device: DeviceInfo = default_dev
        self._permission_state: PermissionState = permission_state
        self._mock_source: Optional[MockMicrophone] = mock_source
        self._preloaded_chunks: Optional[list[AudioChunk]] = (
            list(chunks) if chunks is not None else None
        )
        self._chunk_iterator: Optional[Iterator[AudioChunk]] = None
        self._is_open: bool = False
        self._active_format: Optional[AudioFormat] = None

    def list_devices(self) -> List[DeviceInfo]:
        return list(self._devices.values())

    def select_device(self, device_id: str) -> DeviceInfo:
        if device_id not in self._devices:
            raise AudioError(
                AudioErrorCode.DEVICE_NOT_FOUND,
                f"Audio device with id '{device_id}' was not found",
            )
        device = self._devices[device_id]
        if not device.is_supported:
            raise AudioError(
                AudioErrorCode.DEVICE_UNSUPPORTED,
                f"Audio device '{device.name}' ({device.id}) is unsupported",
            )
        self._selected_device = device
        return device

    def get_selected_device(self) -> DeviceInfo:
        return self._selected_device

    def get_permission_state(self) -> PermissionState:
        return self._permission_state

    def set_permission_state(self, state: PermissionState) -> None:
        """Convenience method for tests to simulate OS permission changes."""
        self._permission_state = state

    def request_permission(self) -> PermissionState:
        """Simulate permission request (returns current configured permission state)."""
        return self._permission_state

    def open(self, fmt: Optional[AudioFormat] = None) -> None:
        if self._permission_state == PermissionState.DENIED:
            raise AudioError(
                AudioErrorCode.PERMISSION_DENIED,
                "Microphone access denied: permission has been revoked or refused",
            )
        if self._permission_state == PermissionState.UNSUPPORTED:
            raise AudioError(
                AudioErrorCode.DEVICE_UNSUPPORTED,
                "Microphone audio capture is unsupported on this system",
            )
        if not self._selected_device.is_supported:
            raise AudioError(
                AudioErrorCode.DEVICE_UNSUPPORTED,
                f"Cannot open stream: device '{self._selected_device.id}' is unsupported",
            )

        if fmt is not None:
            self._active_format = fmt
        else:
            self._active_format = AudioFormat(
                sample_rate=self._selected_device.sample_rate,
                channels=self._selected_device.channels,
            )

        # Set up chunk stream
        if self._preloaded_chunks is not None:
            self._chunk_iterator = iter(self._preloaded_chunks)
        else:
            source = self._mock_source or MockMicrophone(fmt=self._active_format)
            self._chunk_iterator = iter(source.stream(realtime=False))

        self._is_open = True

    def read_chunk(self) -> Optional[AudioChunk]:
        if not self._is_open:
            return None
        if self._permission_state == PermissionState.DENIED:
            raise AudioError(
                AudioErrorCode.PERMISSION_DENIED,
                "Cannot read chunk: microphone permission was revoked",
            )
        if self._chunk_iterator is None:
            return None
        try:
            return next(self._chunk_iterator)
        except StopIteration:
            return None

    def close(self) -> None:
        self._is_open = False
        self._chunk_iterator = None

    @property
    def is_open(self) -> bool:
        return self._is_open
