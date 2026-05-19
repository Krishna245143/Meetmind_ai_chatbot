import subprocess
import os
from pathlib import Path

def validate_video(filepath: str) -> dict:
    """
    Use ffprobe to check if file has an audio stream.
    Returns {"ok": True} or {"ok": False, "error": "reason"}
    """
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        filepath
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        return {"ok": False, "error": "Could not read file. It may be corrupted or unsupported format."}

    import json
    try:
        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        has_audio = any(s.get("codec_type") == "audio" for s in streams)
        if not has_audio:
            return {"ok": False, "error": "No audio track found in this video file."}
        return {"ok": True}
    except Exception:
        return {"ok": False, "error": "Could not parse file info."}


def extract_audio(video_path: str, output_dir: str) -> dict:
    """
    Extract audio from video using ffmpeg with noise reduction.
    Returns {"ok": True, "audio_path": "..."} or {"ok": False, "error": "..."}
    """
    # Validate first
    check = validate_video(video_path)
    if not check["ok"]:
        return check

    filename = Path(video_path).stem
    audio_path = os.path.join(output_dir, f"{filename}_audio.wav")

    # ffmpeg command:
    # -i input file
    # -af noise reduction filter (reduces background hiss/noise)
    # -ar 16000 sample rate whisper expects
    # -ac 1 mono (whisper works on mono)
    # -y overwrite if exists
    cmd = [
        "ffmpeg", "-i", video_path,
        "-af", "afftdn=nf=-25",   # noise filter: reduce background noise
        "-ar", "16000",
        "-ac", "1",
        "-y",
        audio_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        # Try without noise filter as fallback
        cmd_fallback = [
            "ffmpeg", "-i", video_path,
            "-ar", "16000", "-ac", "1",
            "-y", audio_path
        ]
        result2 = subprocess.run(cmd_fallback, capture_output=True, text=True)
        if result2.returncode != 0:
            return {"ok": False, "error": f"Audio extraction failed: {result2.stderr[-300:]}"}

    if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
        return {"ok": False, "error": "Extracted audio file is empty. Video may have silent audio."}

    return {"ok": True, "audio_path": audio_path}


def convert_audio_to_wav(audio_path: str, output_dir: str) -> dict:
    """
    Convert any audio format to 16kHz mono WAV for Whisper.
    """
    filename = Path(audio_path).stem
    wav_path = os.path.join(output_dir, f"{filename}_converted.wav")

    cmd = [
        "ffmpeg", "-i", audio_path,
        "-af", "afftdn=nf=-25",
        "-ar", "16000", "-ac", "1",
        "-y", wav_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        # Fallback without filter
        cmd2 = ["ffmpeg", "-i", audio_path, "-ar", "16000", "-ac", "1", "-y", wav_path]
        result2 = subprocess.run(cmd2, capture_output=True, text=True)
        if result2.returncode != 0:
            return {"ok": False, "error": "Could not convert audio file."}

    return {"ok": True, "audio_path": wav_path}
