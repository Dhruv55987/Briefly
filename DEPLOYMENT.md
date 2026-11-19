# Deploy AI Video Assistant to Render Free

The frontend and FastAPI API run together at one public HTTPS URL. Render builds
our Dockerfile, which installs Python dependencies, FFmpeg, ffprobe, and Deno.
YouTube links fetch existing captions through the free `youtube-transcript-api`
package, with no extra key or audio download. Uploaded English audio is sent
to Groq Whisper (`whisper-large-v3-turbo`). Summaries
and chat also use Groq. Hinglish translation uses Sarvam. No local model runs.

## 1. Test locally

In your own PowerShell terminal, from this project directory:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend:app --reload --port 8001
```

Keep the terminal open and open http://127.0.0.1:8001. If that port is already in
use, stop the previous server or choose another port. Ensure `.env` contains a
valid `GROQ_API_KEY`. Only add `SARVAM_API_KEY` if you need Hinglish. Do not
replace an existing `.env` with the blank example.

Test a short English audio upload first, then the summary and chat. Test YouTube
separately, since YouTube caption access can fail independently of transcription.
`ffmpeg -version` and `ffprobe -version` should both work in this terminal.

## 2. Create an empty GitHub repository

1. Sign in to https://github.com and create a new repository.
2. Use a name such as `ai-video-assistant` and choose Private if desired.
3. Leave the initialization options for README, .gitignore, and license unchecked
   because the project already has local files.
4. Create the repository and copy its HTTPS repository URL.

## 3. Push this project

The project was not a Git repository when checked. Run these commands from its
root directory. Replace the remote URL with the URL you copied.

```powershell
git init
git branch -M main
git add .gitignore .dockerignore .env.example README.md DEPLOYMENT.md Dockerfile render.yaml requirements.txt requirements-dev.txt backend.py main.py core frontend utils tests
git status --short
```

Check the staged file list before committing: `.env`, `.venv`, `downloads`,
`vector_db`, and Python caches must not appear. The supplied ignore files exclude
them. The downloaded Whisper model is outside the project and is not needed.

```powershell
git commit -m "Prepare API-only video assistant for deployment"
git remote add origin https://github.com/YOUR_USERNAME/ai-video-assistant.git
git push -u origin main
```

GitHub may ask you to sign in. If Git asks for your name or email, configure your
own Git identity and retry the commit. If `origin` already exists, check
`git remote -v` before changing it. Confirm GitHub shows `Dockerfile` and
`render.yaml` at the repository root, alongside `backend.py`.

## 4. Connect Render

1. Sign in at https://dashboard.render.com using your GitHub account.
2. Choose **New > Blueprint**.
3. Connect GitHub and grant access to this repository.
4. Select `ai-video-assistant`, branch `main`, and the root `render.yaml` file.
5. Review the proposed resources: one Docker web service on the **Free** plan,
   one instance, with no persistent disk or database.

The Blueprint already configures `/health` and a five-minute media limit. The
Dockerfile provides the start command and uses Render's `PORT` environment
variable. No separate frontend service or CORS configuration is needed.

## 5. Set API keys and deploy

Enter `GROQ_API_KEY` when prompted by the Blueprint. For Hinglish, also add
`SARVAM_API_KEY` under the service's Environment settings:

| Variable | Value |
| --- | --- |
| `GROQ_API_KEY` | Your actual Groq API key, required for English transcription, summaries, and chat |
| `SARVAM_API_KEY` | Your actual Sarvam API key, only needed for Hinglish |

The Blueprint also sets `SARVAM_STT_MODEL`, `DOWNLOAD_DIR`, and
`MAX_MEDIA_SECONDS=300`. Keep the supplied values initially. The optional Sarvam key is not requested
by the Blueprint; add it manually if you need Hinglish.

Apply/deploy the Blueprint. Inspect build and runtime logs until the service is
Live. Never paste keys into source code, the frontend, or public logs.

## 6. Verify the public deployment

1. Open the HTTPS URL shown on the service page.
2. Add `/health` to that URL. It should return `{"status":"ok"}`.
3. Upload a short English recording under 25 MB and five minutes.
4. Confirm the transcript, summary, action items, and chat work.
5. Try a short YouTube URL independently.
6. Test Hinglish only after configuring its Sarvam key.

A successful `/health` check confirms the web server responds; it does not verify
API credentials, quotas, or YouTube access. The Docker build and live audio flow
must be verified on Render; they were not run from this restricted workspace.

## 7. Update the deployed app

After making and testing changes locally:

```powershell
git add .
git status --short
git commit -m "Update video assistant"
git push
```

Check staged files before each commit. With automatic deployment enabled, Render
redeploys after changes reach the connected branch.

## Troubleshooting and free-service limits

- **Build failed:** inspect the first error in Render's build logs; confirm all
  source folders and `requirements.txt` were pushed at the repository root.
- **Missing API key / 401:** correct the key in Render Environment and redeploy.
- **429:** the transcription or text model quota was reached; wait for the quota
  window to reset and check your Groq account limits.
- **YouTube error:** test an uploaded recording. Cloud IPs can face YouTube IP
  blocks even with the free transcript package. No YouTube API key is required;
  uploaded-file transcription can work independently.
- **Media too long:** uploaded media is limited to 300 seconds and 25 MB.
  YouTube caption-only requests instead have a 50,000-character text limit.
- **Cold start:** Render Free sleeps after 15 idle minutes; waking can take about
  a minute. Free services have additional monthly usage limits.
- **Lost results:** jobs and chat chains live in memory. Uploads are on ephemeral
  storage. Sleep, restart, and deployment lose jobs/results; no disk is configured.
- **Memory:** one process and one analysis worker are configured. Keep test files
  short. Free hosting is suited to a small demo, not a durable production queue.
- **Cost:** hosting and API usage have separate allowances. Check your accounts;
  there is no unlimited-free transcription or Sarvam guarantee.

## Official references

- Render Blueprints: https://render.com/docs/infrastructure-as-code
- Blueprint configuration: https://render.com/docs/blueprint-spec
- Free service limits: https://render.com/docs/free
- Groq speech API: https://console.groq.com/docs/speech-to-text
- Groq quotas: https://console.groq.com/docs/rate-limits
