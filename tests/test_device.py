import pytest

from academia_audio import (
    AudioChunk,
    AudioError,
    AudioErrorCode,
    AudioFormat,
    DeviceInfo,
    MockDeviceAdapter,
    PermissionState,
)

FMT = AudioFormat(16000, 1)


def test_device_listing():
    adapter = MockDeviceAdapter()
    devices = adapter.list_devices()
    assert len(devices) >= 2
    default_dev = adapter.get_selected_device()
    assert default_dev.is_default is True
    assert default_dev.is_supported is True


def test_select_valid_device():
    adapter = MockDeviceAdapter()
    dev = adapter.select_device("mock-studio")
    assert dev.id == "mock-studio"
    assert adapter.get_selected_device().id == "mock-studio"


def test_select_unknown_device_raises():
    adapter = MockDeviceAdapter()
    with pytest.raises(AudioError) as exc:
        adapter.select_device("non-existent-device-xyz")
    assert exc.value.code == AudioErrorCode.DEVICE_NOT_FOUND


def test_select_unsupported_device_raises():
    adapter = MockDeviceAdapter()
    with pytest.raises(AudioError) as exc:
        adapter.select_device("mock-unsupported")
    assert exc.value.code == AudioErrorCode.DEVICE_UNSUPPORTED
    assert "unsupported" in str(exc.value).lower()


def test_permission_granted_normal_capture():
    adapter = MockDeviceAdapter()
    assert adapter.get_permission_state() == PermissionState.GRANTED
    adapter.open(FMT)
    assert adapter.is_open is True

    chunk = adapter.read_chunk()
    assert isinstance(chunk, AudioChunk)
    assert chunk.sequence_id == 0
    assert chunk.format == FMT

    adapter.close()
    assert adapter.is_open is False


def test_permission_denied_raises_without_crash():
    adapter = MockDeviceAdapter(permission_state=PermissionState.DENIED)
    assert adapter.get_permission_state() == PermissionState.DENIED
    with pytest.raises(AudioError) as exc:
        adapter.open(FMT)
    assert exc.value.code == AudioErrorCode.PERMISSION_DENIED
    assert adapter.is_open is False


def test_permission_unsupported_raises_without_crash():
    adapter = MockDeviceAdapter(permission_state=PermissionState.UNSUPPORTED)
    with pytest.raises(AudioError) as exc:
        adapter.open(FMT)
    assert exc.value.code == AudioErrorCode.DEVICE_UNSUPPORTED
    assert adapter.is_open is False


def test_runtime_permission_revocation():
    adapter = MockDeviceAdapter(permission_state=PermissionState.GRANTED)
    adapter.open(FMT)
    chunk = adapter.read_chunk()
    assert chunk is not None

    # Simulate permission revocation while running
    adapter.set_permission_state(PermissionState.DENIED)
    with pytest.raises(AudioError) as exc:
        adapter.read_chunk()
    assert exc.value.code == AudioErrorCode.PERMISSION_DENIED


def test_custom_preloaded_chunks():
    chunks = [
        AudioChunk(0, 0.0, FMT, b"\x00\x00" * 160),
        AudioChunk(1, 0.01, FMT, b"\x01\x00" * 160),
    ]
    adapter = MockDeviceAdapter(chunks=chunks)
    adapter.open(FMT)
    c1 = adapter.read_chunk()
    c2 = adapter.read_chunk()
    c3 = adapter.read_chunk()

    assert c1 == chunks[0]
    assert c2 == chunks[1]
    assert c3 is None
    adapter.close()
