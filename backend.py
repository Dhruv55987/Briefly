"""FastAPI server for the AI Video Assistant web interface."""
from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.rag_engine import ask_question
from main import run_pipeline

load_dotenv()
ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
DOWNLOADS = Path(os.getenv("DOWNLOAD_DIR") or ROOT / "downloads")
DOWNLOADS.mkdir(parents=True, exist_ok=True)
ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".mp4", ".mpeg", ".mpga", ".webm", ".ogg", ".flac"}

app = FastAPI(title="AI Video Assistant", version="1.0.0")
# Limit CPU and memory usage by processing one analysis at a time.
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="analysis")
jobs: dict[str, dict[str, Any]] = {}
jobs_lock = threading.Lock()


def _update_job(job_id: str, **changes: Any) -> None:
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id].update(changes)


def _run_job(job_id: str, source: str, language: str) -> None:
    _update_job(job_id, status="processing", message="Starting analysis")
    try:
        result = run_pipeline(source, language, progress_callback=lambda message, percent: _update_job(
            job_id, message=message, progress=percent
        ))
        public_result = {key: value for key, value in result.items() if key != "rag_chain"}
        _update_job(job_id, status="completed", message="Analysis complete", progress=100,
                    result=public_result, rag_chain=result["rag_chain"])
    except Exception as exc:
        _update_job(job_id, status="failed", message="Analysis failed", error=str(exc))


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/jobs", status_code=202)
async def create_job(language: str = Form("english"), source_url: str = Form(""),
                     file: UploadFile | None = File(None)) -> dict[str, str]:
    language = language.strip().lower()
    if language not in {"english", "hinglish"}:
        raise HTTPException(status_code=422, detail="Language must be english or hinglish")
    if bool(source_url.strip()) == bool(file):
        raise HTTPException(status_code=422, detail="Provide either a URL or an audio/video file")
    source = source_url.strip()
    if file:
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=415, detail="Unsupported file type")
        target = DOWNLOADS / f"upload_{uuid.uuid4().hex}{suffix}"
        try:
            with target.open("wb") as output:
                size = 0
                while block := await file.read(1024 * 1024):
                    size += len(block)
                    if size > 25 * 1024 * 1024:
                        raise HTTPException(status_code=413, detail="Maximum upload size is 25 MB")
                    output.write(block)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        finally:
            await file.close()
        source = str(target)
    elif not source.startswith(("https://", "http://")):
        raise HTTPException(status_code=422, detail="Enter a valid http or https URL")

    job_id = uuid.uuid4().hex
    with jobs_lock:
        jobs[job_id] = {"status": "queued", "progress": 0, "message": "Queued", "result": None}
    executor.submit(_run_job, job_id, source, language)
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Analysis job not found")
        return {key: value for key, value in job.items() if key != "rag_chain"}


class ChatRequest(BaseModel):
    question: str


@app.post("/api/jobs/{job_id}/chat")
def chat(job_id: str, payload: ChatRequest) -> dict[str, str]:
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question cannot be empty")
    with jobs_lock:
        job = jobs.get(job_id)
        chain = job.get("rag_chain") if job else None
        status = job.get("status") if job else None
    if job is None:
        raise HTTPException(status_code=404, detail="Analysis job not found")
    if status != "completed" or chain is None:
        raise HTTPException(status_code=409, detail="Analysis is not ready for chat")
    try:
        return {"answer": ask_question(chain, question)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not answer question: {exc}") from exc


app.mount("/", StaticFiles(directory=FRONTEND), name="frontend")
