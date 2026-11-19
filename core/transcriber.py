"""API-only speech processing: Groq Whisper and optional Sarvam translation."""
import os
import requests
from pydub import AudioSegment

# Sarvam's sync STT-translate API rejects audio longer than 30s.
# We slice each chunk into 25s pieces (with a 5s safety margin) before sending.
SARVAM_PIECE_SECONDS = 25


SARVAM_STT_TRANSLATE_URL = "https://api.sarvam.ai/speech-to-text-translate"
SARVAM_MODEL = os.getenv("SARVAM_STT_MODEL") or "saaras:v2.5"

def transcribe_chunk_groq(chunk_path: str) -> str:
    """Run hosted Whisper without importing the local model or PyTorch."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is required for hosted transcription")
    if os.path.getsize(chunk_path) > 25 * 1024 * 1024:
        raise ValueError("Audio chunk exceeds Groq's 25 MB free-tier upload limit")
    with open(chunk_path, "rb") as audio:
        response = requests.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (os.path.basename(chunk_path), audio, "audio/wav")},
            data={"model": "whisper-large-v3-turbo", "response_format": "json"},
            timeout=120,
        )
    response.raise_for_status()
    text = response.json().get("text")
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("Groq Whisper returned an empty or invalid transcript")
    return text.strip()


def _send_to_sarvam(piece_path: str) -> str:
    """Send one ≤30s WAV file to Sarvam and return the English transcript."""
    headers = {"api-subscription-key": os.getenv("SARVAM_API_KEY")}

    with open(piece_path, "rb") as f:
        files = {"file": (os.path.basename(piece_path), f, "audio/wav")}
        data = {"model": SARVAM_MODEL, "with_diarization": "false"}
        response = requests.post(
            SARVAM_STT_TRANSLATE_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=120,
        )

    if not response.ok:
        print(f"\n❌ Sarvam returned {response.status_code}")
        print(f"Response body: {response.text}\n")
        response.raise_for_status()

    return response.json().get("transcript", "")


def transcribe_chunk_sarvam(chunk_path: str) -> str:
    """
    Sarvam sync API only accepts ≤30s audio. We split this chunk into
    25-second pieces, send each separately, and join the transcripts.
    """
    if not os.getenv("SARVAM_API_KEY"):
        raise RuntimeError("SARVAM_API_KEY is not set in environment / .env")

    audio = AudioSegment.from_wav(chunk_path)
    piece_ms = SARVAM_PIECE_SECONDS * 1000

    full_text = ""
    total_pieces = (len(audio) + piece_ms - 1) // piece_ms

    for i, start in enumerate(range(0, len(audio), piece_ms)):
        piece = audio[start: start + piece_ms]
        piece_path = f"{chunk_path}_sv_{i}.wav"
        piece.export(piece_path, format="wav")

        try:
            print(f"  → Sarvam piece {i + 1}/{total_pieces} ...")
            full_text += _send_to_sarvam(piece_path) + " "
        finally:
            if os.path.exists(piece_path):
                os.remove(piece_path)

    return full_text.strip()


def transcribe_chunk(chunk_path: str, language: str = "english") -> str:
    """
    Route one chunk to Whisper or Sarvam depending on language choice.
    - english  → Groq hosted Whisper
    - hinglish → Sarvam (translates to English while transcribing)
    """
    language = language.strip().lower()
    if language == "hinglish":
        return transcribe_chunk_sarvam(chunk_path)
    if language != "english":
        raise ValueError("Language must be english or hinglish")
    return transcribe_chunk_groq(chunk_path)


def transcribe_all(chunks: list, language: str = "english") -> str:

    full_transcript = "" 

    engine = "Sarvam AI" if language.strip().lower() == "hinglish" else "Groq hosted Whisper"
    print(f"Using {engine} for transcription.")

    for i, chunk in enumerate(chunks):  

        print(f"Transcribing chunk {i + 1}/{len(chunks)}...")

        text = transcribe_chunk(chunk, language=language)  

        full_transcript += text + " "  

    print("Transcription complete.")

    return full_transcript.strip()  
