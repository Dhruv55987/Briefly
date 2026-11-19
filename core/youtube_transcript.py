"""Free YouTube captions through the open-source youtube-transcript-api package."""
import re
from urllib.parse import parse_qs, urlparse

from requests import Session, RequestException
from youtube_transcript_api import (
    YouTubeTranscriptApi, CouldNotRetrieveTranscript, IpBlocked,
    NoTranscriptFound, RequestBlocked, TranscriptsDisabled,
)


class _TimeoutSession(Session):
    def request(self, method, url, **kwargs):
        kwargs.setdefault("timeout", 20)
        return super().request(method, url, **kwargs)


def is_youtube_url(source: str) -> bool:
    parsed = urlparse(source)
    return parsed.scheme in {"http", "https"} and parsed.hostname in {
        "youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
        "youtu.be", "www.youtu.be",
    }


def extract_video_id(source: str) -> str:
    if not is_youtube_url(source):
        raise ValueError("Enter a valid YouTube URL")
    parsed = urlparse(source)
    parts = parsed.path.strip("/").split("/")
    if parsed.hostname in {"youtu.be", "www.youtu.be"}:
        video_id = parts[0]
    elif parsed.path == "/watch":
        video_id = parse_qs(parsed.query).get("v", [""])[0]
    elif len(parts) == 2 and parts[0] in {"shorts", "embed", "live"}:
        video_id = parts[1]
    else:
        video_id = ""
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise ValueError("Enter a YouTube video link, rather than a channel or playlist link")
    return video_id


def fetch_youtube_transcript(source: str) -> str:
    video_id = extract_video_id(source)
    try:
        with _TimeoutSession() as session:
            transcripts = YouTubeTranscriptApi(http_client=session).list(video_id)
            try:
                track = transcripts.find_transcript(["en", "en-US", "en-GB", "hi"])
            except NoTranscriptFound:
                track = next(iter(transcripts), None)
            if track is None:
                raise RuntimeError("No existing captions were found for this video")
            if not track.language_code.startswith("en") and track.is_translatable:
                track = track.translate("en")
            segments = track.fetch()
    except (RequestBlocked, IpBlocked) as exc:
        raise RuntimeError(
            "YouTube blocked transcript requests from this server's IP address. "
            "The free transcript package cannot override this restriction. "
            "Try running the app locally, or use Upload file."
        ) from exc
    except (TranscriptsDisabled, NoTranscriptFound) as exc:
        raise RuntimeError("No accessible captions were found for this video") from exc
    except CouldNotRetrieveTranscript as exc:
        raise RuntimeError("YouTube captions could not be retrieved. The video may be unavailable or restricted.") from exc
    except RequestException as exc:
        raise RuntimeError("Could not connect to YouTube for captions. Try again later.") from exc

    transcript = " ".join(segment.text.strip() for segment in segments).strip()
    if not transcript:
        raise RuntimeError("No existing captions were found for this video")
    if len(transcript) > 50000:
        raise ValueError("Video transcript is too long for this demo")
    return transcript
