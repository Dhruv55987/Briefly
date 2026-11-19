"""Fetch existing YouTube captions without downloading audio on the app server."""
import os
import time
from urllib.parse import urlparse

import requests


API_URL = "https://api.supadata.ai/v1/transcript"


def is_youtube_url(source: str) -> bool:
    parsed = urlparse(source)
    return parsed.scheme in {"http", "https"} and parsed.hostname in {
        "youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
        "youtu.be", "www.youtu.be",
    }


def fetch_youtube_transcript(source: str) -> str:
    if not is_youtube_url(source):
        raise ValueError("Enter a valid YouTube URL")
    api_key = os.getenv("SUPADATA_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Set SUPADATA_API_KEY in the server environment to fetch YouTube captions")
    headers = {"x-api-key": api_key}
    response = requests.get(
        API_URL,
        headers=headers,
        params={"url": source, "text": "false", "mode": "native", "lang": "en"},
        timeout=30,
    )
    _check_response(response)
    payload = response.json()
    if response.status_code == 202:
        job_id = payload.get("jobId")
        if not isinstance(job_id, str) or not job_id or not all(
            char.isalnum() or char == "-" for char in job_id
        ):
            raise RuntimeError("Transcript provider returned an invalid job ID")
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            time.sleep(2)
            response = requests.get(f"{API_URL}/{job_id}", headers=headers, timeout=15)
            _check_response(response)
            payload = response.json()
            if payload.get("status") == "completed":
                break
            if payload.get("status") == "failed":
                raise RuntimeError("YouTube captions could not be retrieved for this video")
        else:
            raise RuntimeError("YouTube captions took too long to retrieve. Try again later.")

    content = payload.get("content")
    if not isinstance(content, list):
        raise RuntimeError("Transcript provider returned invalid caption segments")
    limit = int(os.getenv("MAX_MEDIA_SECONDS", "0"))
    if limit and any(
        segment.get("offset", 0) + segment.get("duration", 0) > limit * 1000
        for segment in content
    ):
        raise ValueError(f"Free demo supports captions up to {limit} seconds")
    transcript = " ".join(segment.get("text", "").strip() for segment in content).strip()
    if not transcript:
        raise RuntimeError("No existing captions were found for this video")
    if len(transcript) > 50000:
        raise ValueError("Video transcript is too long for this demo")
    return transcript


def _check_response(response) -> None:
    if response.status_code in {401, 403}:
        raise RuntimeError("The transcript API key is invalid or lacks access. Check SUPADATA_API_KEY.")
    if response.status_code in {402, 429}:
        raise RuntimeError("The transcript API quota was reached. Check your Supadata account limits.")
    if response.status_code in {404, 422}:
        raise RuntimeError("No accessible existing captions were found for this video")
    response.raise_for_status()
