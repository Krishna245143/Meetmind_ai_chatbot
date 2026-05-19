import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"

WHISPER_MODEL = "base"
EMBED_MODEL = "all-MiniLM-L6-v2"

# llama3-70b-8192 is decommissioned — use these instead
# llama-3.1-8b-instant  → fastest, good quality
# llama-3.3-70b-versatile → best quality, slightly slower
GROQ_MODEL = "llama-3.3-70b-versatile"

CHUNK_SIZE = 300
CHUNK_OVERLAP = 50
QDRANT_PATH = "./qdrant_data"
COLLECTION = "meetmind"
MAX_FILE_MB = 500
ALLOWED_VIDEO = {".mp4", ".mkv", ".avi", ".mov", ".webm"}
ALLOWED_AUDIO = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".ogg"}
ALLOWED_TEXT  = {".txt", ".vtt", ".srt"}