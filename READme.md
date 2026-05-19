# 🧠 MeetMind — Meeting Intelligence Platform

> Turn any meeting recording, audio, or transcript into structured, highlighted, downloadable documents — in any language — with human verification built in.

---

## What is MeetMind?

MeetMind is an AI-powered meeting documentation tool. You give it a meeting in any form — a video file, an audio recording, a WhatsApp voice note, or a plain text transcript — and it gives you back a professional, structured document with decisions highlighted, action items extracted, and risks flagged.

No manual copy-pasting. No expensive subscriptions. No data leaving your machine for transcription.

---

## The Problem It Solves

Every team runs meetings. Almost nobody properly documents them.

- Action items get lost in chat messages
- New employees have no record of past decisions
- Important risks mentioned in meetings are forgotten
- Writing MOMs manually takes 30–45 minutes after every meeting
- Tools like ChatGPT need you to manually transcribe and paste — too much friction

MeetMind removes all that friction. Upload → review → download. Three steps.

---

## Why These Technology Choices

### FastAPI — not Flask, not Django

Flask is simple but has no async support — each request blocks the server while Whisper is transcribing (which takes minutes). Django is heavy and built for traditional web apps, not APIs.

FastAPI gives us:
- **Async endpoints** — server stays responsive while transcription runs in a background thread
- **Automatic validation** — Pydantic models catch bad inputs before they reach our logic
- **Auto-generated API docs** at `/docs` — useful for testing every endpoint
- **Speed** — one of the fastest Python web frameworks, benchmarked faster than Flask and Django

For a tool where audio processing takes minutes in the background, async is not optional. FastAPI is the right choice.

### OpenAI Whisper — not Google Speech API, not AssemblyAI

Cloud speech APIs cost money per minute and — critically — **send your audio to their servers**. For meetings discussing salaries, client deals, legal matters, or product strategy, that is a hard no for enterprise users.

Whisper runs 100% locally:
- Audio never leaves your machine
- Free, no API key needed
- Supports 99 languages including Telugu, Hindi, Tamil, Kannada
- Handles code-switching (English mixed with Telugu mid-sentence)
- `base` model runs on CPU with 4GB RAM — no GPU needed

The `beam_size=1, best_of=1` settings we use give roughly 2–3x speedup over defaults on CPU with minimal quality loss.

### Groq API (LLaMA 3.3) — not OpenAI GPT-4

GPT-4 costs $0.03 per 1K tokens. A typical meeting summary uses 3,000–5,000 tokens — that's $0.09–$0.15 per meeting. Multiply by 50 meetings a week for a team, it adds up fast.

Groq's free tier gives:
- 14,400 requests per day
- LLaMA 3.3 70B — same quality as GPT-4 for summarization tasks
- Fastest inference available — LLaMA 3.3 on Groq is ~10x faster than GPT-4 on OpenAI
- Free at this scale

For this use case (structured text generation from a transcript), LLaMA 3.3 70B performs identically to GPT-4. No reason to pay.

### python-docx — not PDF generation

Word documents (`.docx`) are the standard for business documentation. Every manager, HR person, and executive has Microsoft Word or Google Docs. PDFs are read-only — if the AI makes a mistake, the user cannot correct it.

`.docx` gives:
- Native Word highlighting (yellow decisions, green action items, red risks)
- Fully editable — user can fix AI mistakes directly in Word
- Compatible with Google Docs, LibreOffice, Apple Pages
- No dependency on a browser or PDF viewer

### Threading — not Celery, not Redis

Celery is the production choice for background tasks but requires Redis as a broker — two extra services to install and run. For a local tool, that overhead is unnecessary.

Python's built-in `threading.Thread` gives us background processing with zero infrastructure. The transcription runs in a background thread, the server stays responsive, and the frontend polls `/status/{job_id}` every 1.8 seconds to show progress. Simple, works, no ops overhead.

### JSON file persistence — not PostgreSQL, not SQLite

PostgreSQL and SQLite require schema migrations, connection pools, and ORMs. For storing job metadata (filename, status, transcript, export paths), a JSON file is perfectly sufficient.

`jobs.json` is written after every state change. It survives server restarts. It's human-readable. You can open it and see exactly what's stored. Zero setup.

---

## Architecture

```
User uploads file
        │
        ▼
┌─────────────────┐
│   FastAPI       │  ← receives upload, validates file type/size
│   /upload       │    saves to uploads/ folder, creates job entry
└────────┬────────┘
         │ background thread starts
         ▼
┌─────────────────────────────────────────────┐
│              Processing Pipeline            │
│                                             │
│  Video file → ffmpeg → extract audio (WAV) │
│  Audio file → ffmpeg → convert to 16kHz    │
│  Text file  → read directly                │
│                                             │
│  Audio → Whisper (local) → transcript      │
│          with real timestamps per segment  │
└────────┬────────────────────────────────────┘
         │ status: needs_review
         ▼
┌─────────────────┐
│  User reviews   │  ← sees raw transcript, fixes names/errors
│  transcript     │    clicks "looks good"
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│              Generation Pipeline            │
│                                             │
│  Transcript → Groq API (LLaMA 3.3 70B)    │
│  with format-specific prompt:              │
│    MOM / Summary / Action Items /          │
│    Clean Transcript / Custom               │
│                                             │
│  Output → python-docx → .docx             │
│           with color highlights            │
│         → plain .txt (optional)            │
└─────────────────────────────────────────────┘
         │
         ▼
  User downloads highlighted Word file
```

---

## Problems Solved

| Problem | How MeetMind Solves It |
|---|---|
| Bad audio quality | ffmpeg noise filter (`afftdn`) runs before Whisper |
| No audio track in video | ffprobe validates before extraction, clear error shown |
| Whisper name errors | Editable transcript shown before generation — user fixes first |
| Corrupted Whisper model | Auto-detects small file size, deletes and re-downloads |
| Wrong speaker timestamps | Real timestamps from Whisper segments, not fake ones |
| Telugu/Hindi not working | Language auto-detected — not forced to English |
| Slow transcription | `beam_size=1, best_of=1` — 2-3x faster on CPU |
| History lost on restart | All jobs saved to `jobs.json` after every state change |
| Data privacy | Whisper runs locally — audio never leaves your machine |
| LLM hallucinations | Human correction step before AI generation |
| Output not editable | Word `.docx` format — edit directly in Word |

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Backend | FastAPI (Python) | Async, fast, auto-validation |
| Transcription | OpenAI Whisper (local) | Free, private, multilingual |
| Audio extraction | ffmpeg | Industry standard, handles any format |
| LLM | Groq API — LLaMA 3.3 70B | Free tier, GPT-4 quality, fastest inference |
| Document export | python-docx | Native Word highlights, fully editable |
| Persistence | JSON file | Zero infrastructure, human-readable |
| Background tasks | Python threading | No Redis/Celery overhead for local tool |
| Frontend | Vanilla HTML/CSS/JS | No framework needed, instant load |

---

## How to Run

### Prerequisites

- Python 3.10 or higher
- ffmpeg installed (`winget install ffmpeg` on Windows, `brew install ffmpeg` on Mac)
- Free Groq API key from [console.groq.com](https://console.groq.com)

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/meetmind.git
cd meetmind

# 2. Create virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment
cp .env.example .env
# Open .env and add your Groq API key:
# GROQ_API_KEY=your_key_here

# 5. Create required folders
mkdir uploads outputs

# 6. Run the server
uvicorn main:app --reload --port 8000
```

### Open in browser

```
http://localhost:8000
```

### First test (no audio needed)

Create `test.txt`:
```
Krishna: Good morning everyone. Today we discuss the product launch.
Priya: I suggest April 15th as the target launch date.
Krishna: Agreed. Priya handles marketing. Ravi fixes the payment bug by Friday.
Ravi: Risk — payment gateway might delay us by one week.
Krishna: Noted. Let's review again on Thursday.
```

Upload → select MOM → Word → "Looks good" → download the `.docx` → open in Word to see highlights.

---




| Method | Endpoint | What it does |
|---|---|---|
| POST | `/upload` | Upload video/audio/text file |
| POST | `/transcribe/{job_id}` | Start transcription in background |
| GET | `/status/{job_id}` | Poll job status and progress |
| GET | `/transcript/{job_id}` | Get raw transcript for review |
| POST | `/correct/{job_id}` | Save user corrections to transcript |
| POST | `/generate/{job_id}` | Generate output in chosen format |
| GET | `/download/{filename}` | Download generated file |
| GET | `/jobs` | List all past jobs |
| DELETE | `/jobs/{job_id}` | Delete a job from history |

Test all endpoints live at `http://localhost:8000/docs` (FastAPI auto-generates this).

---

## Output Formats

| Format | What you get |
|---|---|
| **MOM** | Formal Minutes of Meeting — date, attendees, agenda, key decisions, action items table, risks |
| **Summary** | 3–5 sentence paragraph with purpose, conclusions, next steps |
| **Action Items** | Table of tasks with owner, deadline, priority — nothing else |
| **Clean Transcript** | Speaker-formatted, filler words removed, timestamps preserved |
| **Custom** | You write the instruction — AI follows it exactly |

Each output available as `.docx` (highlighted) or `.txt` or both.

---

## Conclusion

MeetMind is not another AI chatbot. It is a focused, production-grade document pipeline that solves one real problem — meeting documentation — better than any generic AI tool.

The architecture choices prioritize practicality: local transcription for privacy, async processing for responsiveness, human verification for accuracy, and editable Word output for real-world use. Every technology was chosen to solve a specific problem, not because it was trendy.

Built with FastAPI, Whisper, Groq, and python-docx. Runs on a laptop. Works offline for transcription. Free to use.

---

*Built by Krishna — Final Year B.Tech CSE (Data Science), Pragati Engineering College, Kakinada*