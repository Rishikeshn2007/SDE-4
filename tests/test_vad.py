import math
from array import array

import pytest

from academia_audio import (
    AudioChunk,
    AudioError,
    AudioErrorCode,
    AudioFormat,
    MockVAD,
    compute_rms,
)

FMT = AudioFormat(16000, 1)


def make_tone_chunk(seq: int, amplitude: float = 0.5, freq: float = 440.0) -> AudioChunk:
    total_frames = 320  # 20ms at 16000 Hz
    peak = int(amplitude * 32767)
    samples = array("h")
    for n in range(total_frames):
        t = (seq * 320 + n) / 16000
        val = int(peak * math.sin(2 * math.pi * freq * t))
        samples.append(val)
    data = samples.tobytes()
    return AudioChunk(
        sequence_id=seq,
        timestamp_s=seq * 0.02,
        format=FMT,
        data=data,
    )


def make_silence_chunk(seq: int) -> AudioChunk:
    return AudioChunk(
        sequence_id=seq,
        timestamp_s=seq * 0.02,
        format=FMT,
        data=b"\x00\x00" * 320,
    )


def make_noise_chunk(seq: int, amplitude: float = 0.01) -> AudioChunk:
    # Low amplitude noise below standard energy threshold (0.05)
    return make_tone_chunk(seq, amplitude=amplitude, freq=200.0)


def test_compute_rms():
    assert compute_rms(b"") == 0.0
    assert compute_rms(b"\x00\x00" * 100) == 0.0

    tone = make_tone_chunk(0, amplitude=0.5)
    rms = compute_rms(tone.data)
    # Sine wave RMS is amplitude / sqrt(2) ≈ 0.5 / 1.414 ≈ 0.3535
    assert rms == pytest.approx(0.3535, rel=1e-2)


def test_vad_param_validation():
    with pytest.raises(AudioError) as exc:
        MockVAD(energy_threshold=0.0)
    assert exc.value.code == AudioErrorCode.INVALID_PARAMETER

    with pytest.raises(AudioError) as exc:
        MockVAD(energy_threshold=1.5)
    assert exc.value.code == AudioErrorCode.INVALID_PARAMETER

    with pytest.raises(AudioError) as exc:
        MockVAD(min_speech_duration_ms=-10.0)
    assert exc.value.code == AudioErrorCode.INVALID_PARAMETER


def test_vad_silence():
    vad = MockVAD(energy_threshold=0.05)
    chunk = make_silence_chunk(0)
    res = vad.process_chunk(chunk)
    assert res.is_speech is False
    assert res.energy == 0.0
    assert res.speech_duration_s == 0.0
    assert res.confidence < 0.1


def test_vad_background_noise_rejected():
    # Noise has RMS around 0.007 < threshold 0.05
    vad = MockVAD(energy_threshold=0.05, min_speech_duration_ms=60.0)
    for i in range(10):
        chunk = make_noise_chunk(i, amplitude=0.01)
        res = vad.process_chunk(chunk)
        assert res.is_speech is False
        assert res.energy < 0.05
        assert res.speech_duration_s == 0.0


def test_vad_transient_filtering():
    # A single 20ms click or spike should NOT trigger speech when min duration is 60ms
    vad = MockVAD(energy_threshold=0.05, min_speech_duration_ms=60.0)
    click = make_tone_chunk(0, amplitude=0.5)  # 20ms
    res1 = vad.process_chunk(click)
    assert res1.is_speech is False  # 20ms < 60ms

    silence = make_silence_chunk(1)
    res2 = vad.process_chunk(silence)
    assert res2.is_speech is False


def test_vad_sustained_speech_detected():
    # 3 consecutive 20ms chunks (60ms) reaches min_speech_duration_ms
    vad = MockVAD(energy_threshold=0.05, min_speech_duration_ms=60.0, speech_pad_ms=0.0)

    res1 = vad.process_chunk(make_tone_chunk(0, amplitude=0.5))
    assert res1.is_speech is False  # 20ms

    res2 = vad.process_chunk(make_tone_chunk(1, amplitude=0.5))
    assert res2.is_speech is False  # 40ms

    res3 = vad.process_chunk(make_tone_chunk(2, amplitude=0.5))
    assert res3.is_speech is True   # 60ms reached!
    assert res3.speech_duration_s == pytest.approx(0.06)
    assert res3.confidence >= 0.5


def test_vad_determinism():
    vad1 = MockVAD(energy_threshold=0.05, min_speech_duration_ms=60.0)
    vad2 = MockVAD(energy_threshold=0.05, min_speech_duration_ms=60.0)

    chunks = [
        make_silence_chunk(0),
        make_tone_chunk(1, amplitude=0.5),
        make_tone_chunk(2, amplitude=0.5),
        make_tone_chunk(3, amplitude=0.5),
        make_silence_chunk(4),
    ]

    res1 = [vad1.process_chunk(c) for c in chunks]
    res2 = [vad2.process_chunk(c) for c in chunks]

    assert res1 == res2


def test_vad_reset():
    vad = MockVAD(energy_threshold=0.05, min_speech_duration_ms=40.0)
    vad.process_chunk(make_tone_chunk(0, amplitude=0.5))
    vad.process_chunk(make_tone_chunk(1, amplitude=0.5))
    assert vad.process_chunk(make_tone_chunk(2, amplitude=0.5)).is_speech is True

    vad.reset()
    # After reset, accumulator is back to 0ms
    res = vad.process_chunk(make_tone_chunk(3, amplitude=0.5))
    assert res.is_speech is False
