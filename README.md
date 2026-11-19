# AI Video Assistant

Summarize a YouTube video or a local audio/video file, extract action items and decisions, and ask questions about the transcript.

## Run the web app

1. Use Python 3.11 and install FFmpeg so it is available on `PATH`.
2. Install Python dependencies: `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and set `GROQ_API_KEY`. For Hinglish transcription, also set `SARVAM_API_KEY`.
4. Start the API and frontend:

   ```powershell
   uvicorn backend:app --reload
   ```

5. Open <http://127.0.0.1:8000>.

For YouTube downloads, install a supported JavaScript runtime such as Deno.
English transcription uses Groq hosted Whisper (`whisper-large-v3-turbo`). Audio is
sent to Groq; no Whisper weights or embedding models download with the default setup.
Store API keys only in `.env` locally or your host's environment settings.
A Groq API key is used for both transcription and summaries; no separate Whisper key is needed.

The API documentation is available at <http://127.0.0.1:8000/docs>.

## Deploy

See [DEPLOYMENT.md](DEPLOYMENT.md) for the Render Docker deployment. The included
`render.yaml` uses Render Free with hosted Groq Whisper transcription and
lightweight keyword retrieval. It requires no local model downloads or paid disk.
Local Python execution uses the same API-only transcription and keyword retrieval defaults.

## Run the command-line version

```powershell
python main.py
```

## Project structure

- `backend.py`: FastAPI routes, uploads, and analysis jobs; serves `frontend/`.
- `main.py`: shared analysis pipeline and command-line entry point.
- `core/transcriber.py`: Groq Whisper transcription; optional Sarvam Hinglish translation.
- `core/llm.py`: shared Groq text model configuration.
- `core/summarize.py`, `core/extractor.py`: hosted Groq text generation.
- `core/rag_engine.py`, `core/keyword_search.py`: transcript chat without model downloads.
- `utils/audio_processor.py`: FFmpeg conversion and audio chunking.
- `requirements.txt`: shared lightweight runtime dependencies for local and hosted use.

## Transcript retrieval

Transcript chat uses keyword matching with no local models. It may miss semantic
matches. English speech uses hosted Whisper; Hinglish uses hosted Sarvam translation.
Existing downloaded Whisper weights and old vector databases are no longer used.

## Verification

Install `pip install -r requirements-dev.txt`, then run
`python -m unittest discover -s tests -v` for offline transcription and API smoke tests.
Live transcription requires a valid Groq key, network access, and available API quota.

## Paste YouTube links on Railway

Set `SUPADATA_API_KEY` in Railway > Briefly > briefly > Variables, then apply the
change. Get a key from https://dash.supadata.ai. When configured, YouTube links
use Supadata's existing captions directly, without a Railway audio download or
Whisper call. Groq generates the summary and chat answers. Uploaded files still
use Whisper for English and Sarvam for Hinglish.

Only existing captions are requested (`mode=native`); private videos and videos
without accessible captions can fail. English captions are preferred; the API
may return another available language. The language selector controls uploaded
speech processing, not caption translation. No paid AI caption generation or
translation is enabled. The current free Supadata plan includes 100 monthly
credits; check https://supadata.ai/pricing for current terms.

The demo checks caption timestamps against `MAX_MEDIA_SECONDS`, and limits
transcripts to 50,000 characters. Without a Supadata key, YouTube uses the original
download path and can still be blocked by YouTube. Never put an API key in GitHub
or browser JavaScript. Restart/redeploy after changing environment variables.
