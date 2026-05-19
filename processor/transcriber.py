import whisper
import os
from config import WHISPER_MODEL

_model = None

def get_model():
    global _model
    if _model is None:
        cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "whisper")
        model_file = os.path.join(cache_dir, f"{WHISPER_MODEL}.pt")
        if os.path.exists(model_file):
            size_mb = os.path.getsize(model_file) / (1024*1024)
            if size_mb < 50:
                os.remove(model_file)
        _model = whisper.load_model(WHISPER_MODEL)
    return _model


def transcribe(audio_path: str, progress_callback=None) -> dict:
    if not os.path.exists(audio_path):
        return {"ok": False, "error": "Audio file not found."}
    if os.path.getsize(audio_path) == 0:
        return {"ok": False, "error": "Audio file is empty."}

    try:
        if progress_callback:
            progress_callback("Loading Whisper model...")
        model = get_model()
        if progress_callback:
            progress_callback("Transcribing audio... (2-3 mins for a 4min audio on CPU)")

        result = model.transcribe(
            audio_path,
            verbose=False,
            task="transcribe",   # auto-detects language
            fp16=False,
            condition_on_previous_text=True,
            beam_size=1,
            best_of=1,
        )

        if not result or not result.get("text", "").strip():
            return {"ok": False, "error": "Transcription produced empty text. Audio may be silent or too noisy."}

        # Build segments with REAL timestamps from Whisper
        segments = []
        for seg in result.get("segments", []):
            segments.append({
                "start": round(seg["start"], 1),
                "end":   round(seg["end"],   1),
                "text":  seg["text"].strip()
            })

        # Build readable transcript with actual timestamps
        # Format: [MM:SS] text — each segment on its own line
        lines = []
        for seg in segments:
            mins = int(seg["start"] // 60)
            secs = int(seg["start"] % 60)
            lines.append(f"[{mins:02d}:{secs:02d}] {seg['text']}")

        full_text = "\n".join(lines)
        detected_lang = result.get("language", "unknown")

        if progress_callback:
            progress_callback(f"Done! Language detected: {detected_lang}")

        return {
            "ok": True,
            "full_text": full_text,   # now has real timestamps per line
            "segments": segments,
            "language": detected_lang
        }

    except Exception as e:
        error_msg = str(e)
        if "SHA256" in error_msg or "checksum" in error_msg.lower():
            cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "whisper")
            model_file = os.path.join(cache_dir, f"{WHISPER_MODEL}.pt")
            if os.path.exists(model_file):
                os.remove(model_file)
            return {"ok": False, "error": "Whisper model was corrupted. Deleted automatically — please try again, it will re-download fresh (145MB)."}
        return {"ok": False, "error": f"Transcription failed: {error_msg}"}


def parse_text_transcript(text: str) -> dict:
    """Parse uploaded .txt/.vtt file — preserve existing timestamps if present."""
    import re
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    result_lines = []

    for i, line in enumerate(lines):
        # If line already has a timestamp like [00:00] or 00:00 — keep it
        has_ts = re.match(r'^\[?\d{1,2}:\d{2}\]?', line)
        if has_ts:
            result_lines.append(line)
        else:
            # Assign sequential fake timestamps (5 sec per line)
            mins = (i * 5) // 60
            secs = (i * 5) % 60
            result_lines.append(f"[{mins:02d}:{secs:02d}] {line}")

    full_text = "\n".join(result_lines)
    segments = [{"start": i*5.0, "end": (i+1)*5.0, "text": l}
                for i, l in enumerate(lines)]

    return {"ok": True, "full_text": full_text, "segments": segments, "language": "auto"}