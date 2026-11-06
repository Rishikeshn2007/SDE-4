"""Tests for Voice Activity Detection (VAD) module."""

import math
import struct
import pytest

from academia_audio.schemas import AudioChunk, AudioFormat
from sde4_stt.vad import VADConfig, VADResult, VADState, VoiceActivityDetector


def make_pcm_sine(freq: float, duration_s: float, sample_rate: int = 16000, amplitude: float = 0.5) -> bytes:
    """Generate 16-bit mono PCM sine wave."""
    num_samples = int(sample_rate * duration_s)
    samples = []
    for i in range(num_samples):
        val = int(amplitude * 32767.0 * math.sin(2 * math.pi * freq * i / sample_rate))
        samples.append(max(-32768, min(32767, val)))
    return struct.pack(f"<{len(samples)}h", *samples)


def make_silence(duration_s: float, sample_rate: int = 16000) -> bytes:
    """Generate pure silence PCM bytes."""
    num_samples = int(sample_rate * duration_s)
    return b"\x00\x00" * num_samples


def test_vad_config_validation():
    """Verify VADConfig rejects invalid configuration parameters."""
    with pytest.raises(ValueError, match="energy_threshold"):
        VADConfig(energy_threshold=-0.1)
    with pytest.raises(ValueError, match="energy_threshold"):
        VADConfig(energy_threshold=1.5)
    with pytest.raises(ValueError, match="min_speech_duration_s"):
        VADConfig(min_speech_duration_s=-0.01)
    with pytest.raises(ValueError, match="min_silence_duration_s"):
        VADConfig(min_silence_duration_s=-0.01)
    with pytest.raises(ValueError, match="noise_floor_alpha"):
        VADConfig(noise_floor_alpha=1.5)


def test_vad_pure_silence():
    """Verify that pure silence is detected as SILENCE with zero energy."""
    vad = VoiceActivityDetector(VADConfig(energy_threshold=0.02, min_speech_duration_s=0.05))
    silence_pcm = make_silence(0.1, 16000)
    result = vad.process_chunk(silence_pcm, sample_rate=16000)

    assert result.state == VADState.SILENCE
    assert not result.is_speech
    assert result.energy == 0.0
    assert result.transition is None


def test_vad_speech_like_audio():
    """Verify that high-energy speech-like audio transitions to SPEECH state."""
    vad = VoiceActivityDetector(VADConfig(energy_threshold=0.02, min_speech_duration_s=0.05))
    speech_pcm = make_pcm_sine(300.0, 0.1, sample_rate=16000, amplitude=0.4)
    result = vad.process_chunk(speech_pcm, sample_rate=16000)

    assert result.state == VADState.SPEECH
    assert result.is_speech
    assert result.energy > 0.02
    assert result.transition == "SPEECH_START"


def test_vad_background_noise_below_threshold():
    """Verify low-amplitude background noise does not trigger speech state."""
    vad = VoiceActivityDetector(VADConfig(energy_threshold=0.05, min_speech_duration_s=0.05, adaptive_noise=True))
    noise_pcm = make_pcm_sine(120.0, 0.1, sample_rate=16000, amplitude=0.01)  # energy ~ 0.007
    result = vad.process_chunk(noise_pcm, sample_rate=16000)

    assert result.state == VADState.SILENCE
    assert not result.is_speech
    assert result.transition is None


def test_vad_empty_input():
    """Verify empty input returns silence with 0.0 energy safely."""
    vad = VoiceActivityDetector()
    result = vad.process_chunk(b"", sample_rate=16000)

    assert result.state == VADState.SILENCE
    assert not result.is_speech
    assert result.energy == 0.0


def test_vad_invalid_audio_input():
    """Verify invalid audio buffers raise appropriate exceptions."""
    vad = VoiceActivityDetector()
    # Odd byte count is invalid for 16-bit PCM
    with pytest.raises(ValueError, match="multiple of 2"):
        vad.process_chunk(b"\x01\x02\x03", sample_rate=16000)

    # Invalid type
    with pytest.raises(TypeError, match="Expected AudioChunk or bytes"):
        vad.process_chunk(12345)  # type: ignore


def test_vad_threshold_boundaries():
    """Verify behaviour directly above and below energy threshold."""
    config = VADConfig(energy_threshold=0.10, min_speech_duration_s=0.0, adaptive_noise=False)
    vad = VoiceActivityDetector(config)

    # Just below threshold (RMS of sine is amp / sqrt(2) -> amp 0.10 gives RMS ~0.0707)
    sub_pcm = make_pcm_sine(400.0, 0.05, sample_rate=16000, amplitude=0.10)
    sub_res = vad.process_chunk(sub_pcm, sample_rate=16000)
    assert not sub_res.is_speech

    # Just above threshold (amp 0.20 gives RMS ~0.1414 > 0.10)
    super_pcm = make_pcm_sine(400.0, 0.05, sample_rate=16000, amplitude=0.20)
    super_res = vad.process_chunk(super_pcm, sample_rate=16000)
    assert super_res.is_speech


def test_vad_speech_followed_by_silence_hangover():
    """Verify that speech followed by silence respects the hangover duration before ending speech."""
    config = VADConfig(
        energy_threshold=0.02,
        min_speech_duration_s=0.05,
        min_silence_duration_s=0.15,
        adaptive_noise=False,
    )
    vad = VoiceActivityDetector(config)

    # Chunk 1: 100ms speech -> triggers SPEECH_START
    speech_pcm = make_pcm_sine(300.0, 0.10, sample_rate=16000, amplitude=0.3)
    r1 = vad.process_chunk(speech_pcm, sample_rate=16000)
    assert r1.state == VADState.SPEECH
    assert r1.transition == "SPEECH_START"

    # Chunk 2: 50ms silence -> hangover holds SPEECH state active
    silence_50ms = make_silence(0.05, 16000)
    r2 = vad.process_chunk(silence_50ms, sample_rate=16000)
    assert r2.state == VADState.SPEECH
    assert r2.is_speech
    assert r2.transition is None

    # Chunk 3: another 100ms silence (cumulative 150ms >= min_silence 150ms) -> transitions to SILENCE
    silence_100ms = make_silence(0.10, 16000)
    r3 = vad.process_chunk(silence_100ms, sample_rate=16000)
    assert r3.state == VADState.SILENCE
    assert not r3.is_speech
    assert r3.transition == "SPEECH_END"


def test_vad_continuous_speech():
    """Verify that continuous speech maintains SPEECH state across consecutive chunks."""
    config = VADConfig(energy_threshold=0.02, min_speech_duration_s=0.05, adaptive_noise=False)
    vad = VoiceActivityDetector(config)

    speech_pcm = make_pcm_sine(300.0, 0.05, sample_rate=16000, amplitude=0.3)
    r1 = vad.process_chunk(speech_pcm, sample_rate=16000)
    assert r1.state == VADState.SPEECH

    for _ in range(5):
        rn = vad.process_chunk(speech_pcm, sample_rate=16000)
        assert rn.state == VADState.SPEECH
        assert rn.is_speech
        assert rn.transition is None  # no new transition, stays in SPEECH


def test_vad_audio_chunk_integration():
    """Verify processing directly with W1 AudioChunk objects."""
    fmt = AudioFormat(sample_rate=16000, channels=1, sample_width=2)
    vad = VoiceActivityDetector(VADConfig(energy_threshold=0.02, min_speech_duration_s=0.05))

    speech_pcm = make_pcm_sine(440.0, 0.1, sample_rate=16000, amplitude=0.3)
    chunk = AudioChunk(sequence_id=0, timestamp_s=0.0, format=fmt, data=speech_pcm)

    res = vad.process_chunk(chunk)
    assert res.state == VADState.SPEECH
    assert res.is_speech
    assert res.energy > 0.02
    assert res.transition == "SPEECH_START"


def test_vad_reset():
    """Verify that reset clears temporal state and accumulated runs."""
    vad = VoiceActivityDetector(VADConfig(energy_threshold=0.02, min_speech_duration_s=0.05))
    speech_pcm = make_pcm_sine(300.0, 0.1, sample_rate=16000, amplitude=0.3)
    vad.process_chunk(speech_pcm, sample_rate=16000)
    assert vad.current_state == VADState.SPEECH

    vad.reset()
    assert vad.current_state == VADState.SILENCE

