import os
import threading
try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    WhisperModel = None

# -------------------------------
# Thread-safe global model cache
# -------------------------------
_model = None
_model_lock = threading.Lock()

def get_model():
    """
    Lazy-load and cache the Faster Whisper model (thread-safe).
    Optimized for CPU-only, low-RAM environments.
    """
    global _model
    
    if not WHISPER_AVAILABLE:
        print("[Warning] faster-whisper not installed. Transcription disabled.")
        return None

    if _model is None:
        with _model_lock:
            if _model is None:  # Double-check locking
                print("Loading Faster Whisper Model (tiny.en | CPU | int8)...")
                try:
                    _model = WhisperModel(
                        "base",
                        device="cpu",
                        compute_type="int8",
                        cpu_threads=max(1, os.cpu_count() // 2),
                        num_workers=1
                    )
                    print("Model loaded successfully.")
                except Exception as e:
                    print(f"[WhisperModel Error] {e}")
                    return None
    return _model


def transcribe_audio_chunk(file_path: str) -> str:
    """
    Transcribe an audio chunk with aggressive silence removal
    and hallucination filtering.
    """
    model = get_model()
    if model is None:
        return ""

    if not os.path.exists(file_path):
        return ""

    try:
        segments, info = model.transcribe(
            file_path,
            language="en",
            beam_size=1,                         # Fast greedy decoding
            vad_filter=True,                     # Skip silence
            vad_parameters={
                "min_silence_duration_ms": 500
            },
            condition_on_previous_text=False,
            temperature=0.0                     # Reduces hallucinations
        )

        results = []

        for segment in segments:
            text = segment.text.strip()

            # Confidence filter
            if segment.avg_logprob < -1.0:
                continue

            # Length filter
            if len(text) < 2:
                continue

            # Hallucination blacklist
            blacklist = {
                "you",
                "thank you",
                "thanks",
                "watching",
                "subscribe",
                "subtitle by",
                ".",
                ""
            }

            if text.lower() in blacklist:
                continue

            results.append(text)

        return " ".join(results)

    except Exception as e:
        print(f"[Transcription Error] {e}")
        return ""

    finally:
        # Always clean up temp files
        try:
            os.remove(file_path)
        except Exception:
            pass
