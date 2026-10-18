# /// script
# requires-python = ">=3.10"
# dependencies = ["faster-whisper>=1.0"]
# ///
"""Local speech-to-text for threadsift.py: transcribe.py <audio.wav> <out.txt>. Model via WHISPER_MODEL (default small)."""
import os
import sys
import wave

import numpy as np
from faster_whisper import WhisperModel

path, out = sys.argv[1], sys.argv[2]
# threadsift.py writes 16 kHz mono PCM; reading it directly avoids PyAV (its newer versions break faster-whisper's decoder)
with wave.open(path) as w:
    audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
name = os.environ.get("WHISPER_MODEL", "small")  # small: ~13s/clip on an RTX 3050 and gets names right; base mishears
device = "cuda"
try:
    model = WhisperModel(name, device="cuda", compute_type="int8_float16")
    segments, info = model.transcribe(audio, vad_filter=True)
    segments = list(segments)
except Exception:  # no usable CUDA/cuDNN on this machine: CPU is slower but always works
    device = "cpu"
    model = WhisperModel(name, device="cpu", compute_type="int8")
    segments, info = model.transcribe(audio, vad_filter=True)
    segments = list(segments)

lines = [f"[{s.start:6.1f}s] {s.text.strip()}" for s in segments]
with open(out, "w", encoding="utf-8") as f:
    f.write(f"(language: {info.language} p={info.language_probability:.2f}, {info.duration:.0f}s, whisper-{name} on {device})\n" + ("\n".join(lines) or "(no speech detected)") + "\n")
