from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os, uuid, threading, json
from pathlib import Path
from datetime import datetime

from config import (UPLOAD_DIR, OUTPUT_DIR, ALLOWED_VIDEO,
                    ALLOWED_AUDIO, ALLOWED_TEXT, MAX_FILE_MB)

def get_extractor():
    from processor.extractor import extract_audio, convert_audio_to_wav
    return extract_audio, convert_audio_to_wav

def get_transcriber():
    from processor.transcriber import transcribe, parse_text_transcript
    return transcribe, parse_text_transcript

def get_summarizer():
    from generator.summarizer import generate_output
    return generate_output

def get_exporter():
    from generator.exporter import export_docx, export_txt
    return export_docx, export_txt

app = FastAPI(title="MeetMind")
app.mount("/static", StaticFiles(directory="static"), name="static")

JOBS_FILE = "jobs.json"
JOBS: dict = {}

def load_jobs():
    global JOBS
    if os.path.exists(JOBS_FILE):
        try:
            with open(JOBS_FILE, "r", encoding="utf-8") as f:
                JOBS = json.load(f)
        except Exception:
            JOBS = {}

def save_jobs():
    try:
        slim = {}
        for jid, j in JOBS.items():
            slim[jid] = {
                "status":      j.get("status"),
                "filename":    j.get("filename"),
                "file_type":   j.get("file_type"),
                "file_path":   j.get("file_path"),
                "created":     j.get("created"),
                "progress":    j.get("progress"),
                "transcript":  j.get("transcript"),
                "exports":     j.get("exports", {}),
                "tokens_used": j.get("tokens_used", 0),
                "format_used": j.get("format_used", ""),
            }
        with open(JOBS_FILE, "w", encoding="utf-8") as f:
            json.dump(slim, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[WARN] Could not save jobs: {e}")

load_jobs()

@app.get("/")
def root():
    return FileResponse("static/index.html")

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext in ALLOWED_VIDEO:       file_type = "video"
    elif ext in ALLOWED_AUDIO:     file_type = "audio"
    elif ext in ALLOWED_TEXT:      file_type = "text"
    else:
        raise HTTPException(400, f"Unsupported type '{ext}'. Allowed: mp4 mkv mp3 wav m4a txt vtt")

    contents = await file.read()
    size_mb = len(contents) / (1024*1024)
    if size_mb > MAX_FILE_MB:
        raise HTTPException(400, f"File too large ({size_mb:.0f}MB). Max: {MAX_FILE_MB}MB")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR,  exist_ok=True)

    job_id    = str(uuid.uuid4())[:8]
    safe_name = "".join(c for c in file.filename if c.isalnum() or c in "._- ")
    save_path = os.path.join(UPLOAD_DIR, f"{job_id}_{safe_name}")
    with open(save_path, "wb") as f:
        f.write(contents)

    JOBS[job_id] = {
        "status": "uploaded", "file_path": save_path,
        "file_type": file_type, "filename": file.filename,
        "progress": "File uploaded", "transcript": None,
        "exports": {}, "tokens_used": 0, "format_used": "",
        "created": datetime.now().strftime("%d %b %Y %I:%M %p")
    }
    save_jobs()
    return {"job_id": job_id, "file_type": file_type, "filename": file.filename}

@app.post("/transcribe/{job_id}")
def start_transcription(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job["status"] not in ("uploaded", "error"):
        return {"message": "Already processing"}

    job["status"] = "processing"
    job["progress"] = "Starting..."

    def run():
        try:
            fp = job["file_path"]
            ft = job["file_type"]

            if ft == "video":
                job["progress"] = "Extracting audio from video..."
                extract_audio, _ = get_extractor()
                r = extract_audio(fp, UPLOAD_DIR)
                if not r["ok"]:
                    job["status"] = "error"; job["progress"] = r["error"]; save_jobs(); return
                audio_path = r["audio_path"]

            elif ft == "audio":
                job["progress"] = "Converting audio..."
                _, convert_fn = get_extractor()
                r = convert_fn(fp, UPLOAD_DIR)
                if not r["ok"]:
                    job["status"] = "error"; job["progress"] = r["error"]; save_jobs(); return
                audio_path = r["audio_path"]

            else:
                job["progress"] = "Reading text file..."
                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
                _, parse_fn = get_transcriber()
                r = parse_fn(text)
                job["status"] = "needs_review"
                job["transcript"] = r["full_text"]
                job["progress"] = "Transcript ready — review below"
                save_jobs()
                return

            def prog(msg): job["progress"] = msg
            transcribe_fn, _ = get_transcriber()
            r = transcribe_fn(audio_path, progress_callback=prog)
            if not r["ok"]:
                job["status"] = "error"; job["progress"] = r["error"]; save_jobs(); return

            job["status"] = "needs_review"
            job["transcript"] = r["full_text"]
            job["progress"] = "Transcription done — review and fix any mistakes"
            save_jobs()

        except Exception as e:
            job["status"] = "error"
            job["progress"] = f"Error: {str(e)}"
            save_jobs()

    threading.Thread(target=run, daemon=True).start()
    return {"message": "started", "job_id": job_id}

@app.get("/status/{job_id}")
def get_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {
        "status": job["status"], "progress": job["progress"],
        "has_transcript": job.get("transcript") is not None,
        "exports": job.get("exports", {}),
        "tokens_used": job.get("tokens_used", 0),
        "format_used": job.get("format_used", ""),
    }

@app.get("/transcript/{job_id}")
def get_transcript(job_id: str):
    job = JOBS.get(job_id)
    if not job or not job.get("transcript"):
        raise HTTPException(404, "Transcript not ready")
    return {"transcript": job["transcript"]}

@app.post("/correct/{job_id}")
async def save_corrections(job_id: str, corrected_transcript: str = Form(...)):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    job["transcript"] = corrected_transcript
    job["status"] = "corrected"
    job["progress"] = "Corrections saved"
    save_jobs()
    return {"message": "Saved"}

@app.post("/generate/{job_id}")
async def generate(
    job_id: str,
    format_type: str = Form(...),
    custom_instruction: str = Form(""),
    output_format: str = Form("docx"),
):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    transcript = job.get("transcript")
    if not transcript:
        raise HTTPException(400, "No transcript found.")

    job["status"] = "generating"
    job["progress"] = f"Generating {format_type.replace('_',' ')} with AI..."

    generate_fn = get_summarizer()
    result = generate_fn(transcript, format_type, custom_instruction)
    if not result["ok"]:
        job["status"] = "error"; job["progress"] = result["error"]
        save_jobs()
        raise HTTPException(500, result["error"])

    content = result["content"]
    highlights = result["highlights"]

    export_docx_fn, export_txt_fn = get_exporter()
    safe_name = f"meetmind_{job_id}_{format_type}"
    exports = {}

    if output_format in ("docx", "both"):
        r = export_docx_fn(content, highlights, OUTPUT_DIR, safe_name)
        if r["ok"]: exports["docx"] = f"/download/{os.path.basename(r['path'])}"

    if output_format in ("txt", "both"):
        r = export_txt_fn(content, OUTPUT_DIR, safe_name)
        if r["ok"]: exports["txt"] = f"/download/{os.path.basename(r['path'])}"

    job["status"] = "done"; job["progress"] = "Done!"
    job["exports"] = exports
    job["tokens_used"] = result.get("tokens_used", 0)
    job["format_used"] = format_type
    save_jobs()

    return {"content": content, "highlights": highlights,
            "exports": exports, "tokens_used": result.get("tokens_used", 0)}

@app.get("/download/{filename}")
def download(filename: str):
    path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(404, "File not found")
    return FileResponse(path, filename=filename)

@app.get("/jobs")
def list_jobs():
    out = [{"job_id": jid, "filename": j.get("filename",""),
            "file_type": j.get("file_type",""), "status": j.get("status",""),
            "created": j.get("created",""), "format_used": j.get("format_used",""),
            "exports": j.get("exports",{}), "tokens_used": j.get("tokens_used",0)}
           for jid, j in JOBS.items()]
    return sorted(out, key=lambda x: x["created"], reverse=True)

@app.delete("/jobs/{job_id}")
def delete_job(job_id: str):
    if job_id in JOBS:
        del JOBS[job_id]
        save_jobs()
    return {"message": "Deleted"}