import yt_dlp
from pydub import AudioSegment
import os 
import json
import subprocess
import uuid

DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR") or 'downloads'
os.makedirs(DOWNLOAD_DIR,exist_ok= True)


def download_youtube_audio(url : str) -> str:
    output_path = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4().hex}.%(ext)s")
    ydl_opts = {
        "format" : "bestaudio/best",
        "outtmpl" : output_path,
        "postprocessors" :[
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ],
        "quiet": True,
        "noplaylist": True,
        "postprocessor_args": ["-ac", "1", "-ar", "16000"],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        limit = int(os.getenv("MAX_MEDIA_SECONDS", "0"))
        if limit and (not info.get("duration") or info["duration"] > limit):
            raise ValueError(f"Free demo supports videos up to {limit} seconds with a known duration")
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info).replace(".webm", ".wav").replace(".m4a", ".wav")
    return filename



def convert_to_wav(input_path: str) -> str:
    """Convert any audio/video file to WAV format using pydub."""
    output_path = os.path.splitext(input_path)[0] + "_converted.wav"
    limit = int(os.getenv("MAX_MEDIA_SECONDS", "0"))
    if limit:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "json", input_path], check=True, capture_output=True, text=True,
            timeout=30,
        )
        duration = float(json.loads(probe.stdout)["format"]["duration"])
        if not 0 < duration <= limit:
            raise ValueError(f"Free demo supports media up to {limit} seconds")
    # Convert in a subprocess instead of decoding the full original into Python RAM.
    subprocess.run(
        ["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", input_path,
         "-vn", "-ac", "1", "-ar", "16000", output_path],
        check=True, capture_output=True, timeout=180,
    )
    return output_path



def chunk_audio(wav_path : str , chunk_minutes : int = 10) -> list:
    audio = AudioSegment.from_wav(wav_path)
    chunk_ms = chunk_minutes * 60 * 1000 

    chunks = []

    for i, start in enumerate(range(0,len(audio),chunk_ms)):
        chunk = audio[start : start + chunk_ms]
        chunk_path = f"{wav_path}_chunk_{i}.wav"
        chunk.export(chunk_path , format = "wav")

        chunks.append(chunk_path)
    
    return chunks



def process_input(source: str) -> list:
    if source.startswith("http://") or source.startswith("https://"):
        print("Detected YouTube URL. Downloading audio...")
        wav_path = download_youtube_audio(source)
    else:
        print("Detected local file. Converting to WAV...")
        wav_path = convert_to_wav(source)

    print("Chunking audio...")
    chunks = chunk_audio(wav_path)
    print(f"Audio ready — {len(chunks)} chunk(s) created.")
    return chunks
