"""Local speech transcription using Vosk. Audio is processed in memory."""

import json
import os
import wave
from vosk import Model, KaldiRecognizer


class LocalTranscriber:
    def __init__(self, model_path=None):
        self.model_path = model_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "models",
            "vosk-model-small-en-us-0.15",
        )

        if not os.path.isdir(self.model_path):
            raise FileNotFoundError(
                f"Vosk model not found: {self.model_path}"
            )

        self.model = Model(self.model_path)

    def transcribe_wav(self, audio_bytes):
        """Transcribe in-memory, mono PCM WAV audio."""

        if not audio_bytes:
            raise ValueError("Audio data is empty")

        import io

        with wave.open(io.BytesIO(audio_bytes), "rb") as audio:
            if audio.getnchannels() != 1:
                raise ValueError("Audio must be mono")

            if audio.getsampwidth() != 2:
                raise ValueError("Audio must use 16-bit PCM")

            sample_rate = audio.getframerate()
            recognizer = KaldiRecognizer(self.model, sample_rate)
            recognizer.SetWords(False)

            while True:
                frames = audio.readframes(4000)
                if not frames:
                    break
                recognizer.AcceptWaveform(frames)

            result = json.loads(recognizer.FinalResult())

        return result.get("text", "").strip()