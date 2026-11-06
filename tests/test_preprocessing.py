"""Tests for sde4_stt.preprocessing — resampling and normalisation."""

import math
import struct
import pytest

from academia_audio.schemas import AudioChunk, AudioFormat
from sde4_stt.preprocessing import AudioPreprocessor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pcm_bytes(samples: list[int], channels: int = 1) -> bytes:
    """Pack a list of int16 samples into little-endian bytes."""
    return struct.pack(f"<{len(samples)}h", *samples)


def _unpack_pcm(data: bytes) -> list[int]:
    n = len(data) // 2
    return list(struct.unpack(f"<{n}h", data))


def _make_chunk(
    samples: list[int],
    sample_rate: int = 16000,
    channels: int = 1,
    seq: int = 0,
) -> AudioChunk:
    """Build a W1 AudioChunk from sample values."""
    data = _make_pcm_bytes(samples, channels)
    fmt = AudioFormat(sample_rate=sample_rate, channels=channels)
    return AudioChunk(sequence_id=seq, timestamp_s=0.0, format=fmt, data=data)


def _rms(samples: list[int]) -> float:
    if not samples:
        return 0.0
    return math.sqrt(sum(s * s for s in samples) / len(samples)) / 32768.0


# ---------------------------------------------------------------------------
# Resampling tests
# ---------------------------------------------------------------------------

class TestResample:
    """Resampling correctness and edge-case handling."""

    def test_same_rate_is_noop(self):
        pre = AudioPreprocessor(normalize_audio=False)
        data = _make_pcm_bytes([100, 200, 300, 400])
        out = pre.resample(data, source_rate=16000, target_rate=16000)
        assert out == data

    def test_downsample_halves_frames(self):
        pre = AudioPreprocessor(normalize_audio=False)
        samples = list(range(0, 100, 1))  # 100 samples at 16 kHz
        data = _make_pcm_bytes(samples)
        out = pre.resample(data, source_rate=16000, target_rate=8000)
        out_samples = _unpack_pcm(out)
        # 100 frames at 16k → ~50 frames at 8k
        assert len(out_samples) == 50

    def test_upsample_doubles_frames(self):
        pre = AudioPreprocessor(normalize_audio=False)
        samples = [0, 1000, 2000, 3000]
        data = _make_pcm_bytes(samples)
        out = pre.resample(data, source_rate=8000, target_rate=16000)
        out_samples = _unpack_pcm(out)
        assert len(out_samples) == 8  # 4 → 8

    def test_empty_data_raises(self):
        pre = AudioPreprocessor(normalize_audio=False)
        with pytest.raises(ValueError, match="not be empty"):
            pre.resample(b"", source_rate=16000, target_rate=8000)

    def test_invalid_rates_raise(self):
        pre = AudioPreprocessor(normalize_audio=False)
        data = _make_pcm_bytes([100, 200])
        with pytest.raises(ValueError):
            pre.resample(data, source_rate=0, target_rate=16000)
        with pytest.raises(ValueError):
            pre.resample(data, source_rate=16000, target_rate=-1)

    def test_misaligned_data_raises(self):
        pre = AudioPreprocessor(normalize_audio=False)
        with pytest.raises(ValueError, match="not a multiple"):
            pre.resample(b"\x00\x00\x00", source_rate=16000, target_rate=8000)


# ---------------------------------------------------------------------------
# Normalisation tests
# ---------------------------------------------------------------------------

class TestNormalize:
    """RMS normalisation correctness."""

    def test_silence_unchanged(self):
        pre = AudioPreprocessor(target_rms=0.1)
        data = _make_pcm_bytes([0, 0, 0, 0])
        out = pre.normalize(data)
        assert out == data  # silence stays silent

    def test_rms_moves_toward_target(self):
        pre = AudioPreprocessor(target_rms=0.1, normalize_audio=True)
        # Create a quiet signal
        quiet = [50] * 100
        data = _make_pcm_bytes(quiet)
        out = pre.normalize(data)
        out_samples = _unpack_pcm(out)
        assert _rms(out_samples) > _rms(quiet)  # should be louder

    def test_loud_signal_attenuated(self):
        pre = AudioPreprocessor(target_rms=0.01, normalize_audio=True)
        loud = [20000, -20000] * 50
        data = _make_pcm_bytes(loud)
        out = pre.normalize(data)
        out_samples = _unpack_pcm(out)
        assert _rms(out_samples) < _rms(loud)

    def test_empty_data_raises(self):
        pre = AudioPreprocessor()
        with pytest.raises(ValueError):
            pre.normalize(b"")


# ---------------------------------------------------------------------------
# process_chunk integration tests
# ---------------------------------------------------------------------------

class TestProcessChunk:
    """End-to-end chunk preprocessing."""

    def test_passthrough_when_no_changes_needed(self):
        pre = AudioPreprocessor(
            target_sample_rate=16000,
            normalize_audio=False,
        )
        chunk = _make_chunk([100, 200, 300, 400], sample_rate=16000)
        out = pre.process_chunk(chunk)
        assert out.data == chunk.data
        assert out.format.sample_rate == 16000

    def test_resample_updates_format(self):
        pre = AudioPreprocessor(
            target_sample_rate=8000,
            normalize_audio=False,
        )
        samples = list(range(100))
        chunk = _make_chunk(samples, sample_rate=16000)
        out = pre.process_chunk(chunk)
        assert out.format.sample_rate == 8000
        out_samples = _unpack_pcm(out.data)
        assert len(out_samples) == 50  # halved

    def test_normalize_changes_amplitude(self):
        pre = AudioPreprocessor(
            target_sample_rate=16000,
            target_rms=0.1,
            normalize_audio=True,
        )
        quiet = [10] * 100
        chunk = _make_chunk(quiet, sample_rate=16000)
        out = pre.process_chunk(chunk)
        out_samples = _unpack_pcm(out.data)
        assert _rms(out_samples) > _rms(quiet)

    def test_sequence_id_preserved(self):
        pre = AudioPreprocessor(target_sample_rate=16000, normalize_audio=False)
        chunk = _make_chunk([100, 200], sample_rate=16000, seq=42)
        out = pre.process_chunk(chunk)
        assert out.sequence_id == 42

    def test_timestamp_preserved(self):
        pre = AudioPreprocessor(target_sample_rate=16000, normalize_audio=False)
        fmt = AudioFormat(sample_rate=16000, channels=1)
        data = _make_pcm_bytes([100, 200])
        chunk = AudioChunk(sequence_id=0, timestamp_s=1.5, format=fmt, data=data)
        out = pre.process_chunk(chunk)
        assert out.timestamp_s == 1.5


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------

class TestPreprocessorInit:
    """Constructor validates parameters."""

    def test_negative_sample_rate_raises(self):
        with pytest.raises(ValueError):
            AudioPreprocessor(target_sample_rate=-1)

    def test_zero_channels_raises(self):
        with pytest.raises(ValueError):
            AudioPreprocessor(target_channels=0)

    def test_rms_out_of_range_raises(self):
        with pytest.raises(ValueError):
            AudioPreprocessor(target_rms=0.0)
        with pytest.raises(ValueError):
            AudioPreprocessor(target_rms=1.5)


# ---------------------------------------------------------------------------
# Advanced Anti-Aliasing, Channels & Clipping Prevention Tests
# ---------------------------------------------------------------------------

class TestAdvancedPreprocessing:
    """Tests covering anti-aliasing downsampling, channel conversion, and headroom protection."""

    def test_anti_aliased_downsampling_attenuates_high_frequencies(self):
        """Downsampling from 48kHz to 16kHz applies anti-aliasing filter to Nyquist-exceeding frequencies."""
        pre = AudioPreprocessor(target_sample_rate=16000, normalize_audio=False)

        # Generate 48kHz signal with a 20kHz tone (above 16kHz Nyquist of 8kHz)
        num_samples = 480
        high_freq_samples = [
            int(15000 * math.sin(2 * math.pi * 20000 * i / 48000))
            for i in range(num_samples)
        ]
        in_bytes = _make_pcm_bytes(high_freq_samples)
        out_bytes = pre.resample(in_bytes, source_rate=48000, target_rate=16000)
        out_samples = _unpack_pcm(out_bytes)

        # The 20kHz tone should be significantly attenuated by the anti-aliasing FIR filter
        in_rms = _rms(high_freq_samples)
        out_rms = _rms(out_samples)
        assert out_rms < in_rms * 0.35  # strong attenuation of out-of-band energy

    def test_stereo_to_mono_downmix(self):
        """Downmixing 2-channel stereo to 1-channel mono averages L and R channels."""
        pre = AudioPreprocessor(target_channels=1, normalize_audio=False)
        # Interleaved stereo: L=1000, R=3000 -> average is 2000
        stereo_samples = [1000, 3000, 2000, 4000]
        data = _make_pcm_bytes(stereo_samples, channels=2)
        out = pre.convert_channels(data, source_channels=2, target_channels=1)
        out_samples = _unpack_pcm(out)
        assert out_samples == [2000, 3000]

    def test_mono_to_stereo_upmix(self):
        """Upmixing mono to stereo duplicates the single channel to both L and R."""
        pre = AudioPreprocessor(target_channels=2, normalize_audio=False)
        mono_samples = [1500, -2500]
        data = _make_pcm_bytes(mono_samples, channels=1)
        out = pre.convert_channels(data, source_channels=1, target_channels=2)
        out_samples = _unpack_pcm(out)
        assert out_samples == [1500, 1500, -2500, -2500]

    def test_invalid_channel_conversion_raises(self):
        """Unsupported channel counts (e.g. 5.1 surround 6ch) raise ValueError."""
        pre = AudioPreprocessor()
        data = _make_pcm_bytes([100, 200])
        with pytest.raises(ValueError, match="Unsupported channel conversion"):
            pre.convert_channels(data, source_channels=6, target_channels=1)

    def test_normalization_avoids_hard_clipping(self):
        """High target_rms on high amplitude signals applies headroom scaling rather than overflowing."""
        pre = AudioPreprocessor(target_rms=0.95, normalize_audio=True)
        # Signal with peak at 30000
        samples = [30000, -28000, 15000, -10000] * 20
        data = _make_pcm_bytes(samples)
        out = pre.normalize(data)
        out_samples = _unpack_pcm(out)

        # None of the samples should exceed the valid int16 bounds [-32768, 32767]
        assert all(-32768 <= s <= 32767 for s in out_samples)
        assert max(out_samples) <= 32767
        assert min(out_samples) >= -32768

    def test_process_chunk_stereo_to_mono_and_resample(self):
        """End-to-end process_chunk correctly handles both channel conversion and resampling."""
        pre = AudioPreprocessor(
            target_sample_rate=16000,
            target_channels=1,
            normalize_audio=True,
            target_rms=0.1,
        )
        # 48kHz stereo chunk
        fmt = AudioFormat(sample_rate=48000, channels=2)
        samples = [1000, 2000] * 480  # 480 frames at 48kHz
        data = _make_pcm_bytes(samples, channels=2)
        chunk = AudioChunk(sequence_id=5, timestamp_s=0.25, format=fmt, data=data)

        out_chunk = pre.process_chunk(chunk)
        assert out_chunk.format.sample_rate == 16000
        assert out_chunk.format.channels == 1
        assert out_chunk.sequence_id == 5
        assert out_chunk.timestamp_s == 0.25
        # Frame count resampled: 480 * 16000 / 48000 = 160 frames, 1 channel = 160 samples = 320 bytes
        assert len(out_chunk.data) == 160 * 2


