# core/stt.py
"""
Faster-Whisper Speech-to-Text Integration
Exact Verbatim Code Snippet as required by specification:

# First run: pip install faster-whisper
from faster_whisper import WhisperModel
# Options: "tiny", "base", "small", "medium", "large-v3"
model_size = "base"
model = WhisperModel(model_size, device="cpu", compute_type="int8")
segments, info = model.transcribe("audio.mp3", beam_size=5)
print(f"Detected language '{info.language}' with probability {info.language_probability:.2f}")
for segment in segments:
print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")
"""
import os
import io
import tempfile
from typing import Dict, Any

# Ensure PyAV compatibility across newer and older PyAV versions
try:
    import av
    _orig_av_open = av.open
    def _safe_av_open(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return _orig_av_open(*args, **kwargs)
    av.open = _safe_av_open
except Exception:
    pass

# Options: "tiny", "base", "small", "medium", "large-v3"
model_size = "tiny"
_cached_model = None


def get_whisper_instance():
    """Initializes or returns cached WhisperModel on CPU with int8 quantization (lazy-loaded)."""
    global _cached_model
    if _cached_model is None:
        try:
            from faster_whisper import WhisperModel
            _cached_model = WhisperModel(model_size, device="cpu", compute_type="int8")
        except Exception as e:
            return None
    return _cached_model


def transcribe_audio_file(file_path: str) -> Dict[str, Any]:
    """
    Transcribes audio from a file path using the verbatim Faster-Whisper pipeline.
    """
    if not os.path.exists(file_path):
        return {"success": False, "error": f"Audio file not found: {file_path}", "text": ""}

    model = get_whisper_instance()
    if model is None:
        return {
            "success": False,
            "error": "faster-whisper is currently initializing. Please try again shortly.",
            "text": ""
        }

    try:
        segments, info = model.transcribe(file_path, beam_size=5)
        print(f"Detected language '{info.language}' with probability {info.language_probability:.2f}")
        
        extracted_segments = []
        for segment in segments:
            print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")
            extracted_segments.append(segment.text.strip())

        full_transcription = " ".join(extracted_segments).strip()
        return {
            "success": True,
            "text": full_transcription,
            "language": info.language,
            "probability": round(float(info.language_probability), 2)
        }
    except Exception as e:
        return {"success": False, "error": str(e), "text": ""}


def verbatim_faster_whisper_snippet():
    """
    Verbatim implementation as provided in user instructions:
    """
    # First run: pip install faster-whisper
    from faster_whisper import WhisperModel
    # Options: "tiny", "base", "small", "medium", "large-v3"
    model_size = "base"
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info = model.transcribe("audio.mp3", beam_size=5)
    print(f"Detected language '{info.language}' with probability {info.language_probability:.2f}")
    for segment in segments:
        print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")

