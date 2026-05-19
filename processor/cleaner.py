import re

def apply_speaker_names(segments: list, speaker_map: dict) -> list:
    """
    Replace "SPEAKER_00", "SPEAKER_01" etc with real names.
    speaker_map = {"SPEAKER_00": "Krishna", "SPEAKER_01": "Priya"}
    """
    updated = []
    for seg in segments:
        text = seg["text"]
        for code, name in speaker_map.items():
            text = text.replace(code, name)
        updated.append({**seg, "text": text})
    return updated


def build_readable_transcript(segments: list) -> str:
    """
    Convert segments list into clean readable text with timestamps.
    Example output:
      [00:00] Hello everyone, welcome to the meeting.
      [00:05] Today we discuss the Q3 roadmap.
    """
    lines = []
    for seg in segments:
        mins = int(seg["start"] // 60)
        secs = int(seg["start"] % 60)
        timestamp = f"[{mins:02d}:{secs:02d}]"
        lines.append(f"{timestamp} {seg['text']}")
    return "\n".join(lines)


def apply_corrections(text: str, corrections: dict) -> str:
    """
    Apply user corrections to transcript text.
    corrections = {"Christine": "Krishna", "fast API": "FastAPI"}
    Simple find-and-replace, case-sensitive.
    """
    for wrong, right in corrections.items():
        if wrong and right:
            text = text.replace(wrong, right)
    return text


def detect_speakers(segments: list) -> list:
    """
    Try to detect speaker labels in transcript if they exist.
    Whisper base doesn't do diarization, but if transcript
    has lines like "Speaker 1: hello" we extract them.
    Returns list of unique speaker labels found.
    """
    pattern = re.compile(r'^(speaker\s*\d+|[A-Z][a-z]+)\s*:', re.IGNORECASE)
    speakers = set()
    for seg in segments:
        m = pattern.match(seg["text"].strip())
        if m:
            speakers.add(m.group(1).strip())
    return list(speakers)
