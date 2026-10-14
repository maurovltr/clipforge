# ClipForge — personal video clipping MVP

A phone-friendly web app with a FastAPI backend. It accepts YouTube URLs, processes videos using `yt-dlp` and FFmpeg, and exports vertical 9:16 MP4 clips. This MVP selects spaced sections; it does **not yet** use AI to detect highlights or generate subtitles.

## Requirements
- Python 3.10+
- FFmpeg and FFprobe installed and available on PATH
- Internet access on the machine running the backend

## Run locally

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000` on the same computer. To use your iPhone, host the app on a computer/server reachable by the phone and open that host's URL in Safari. Both devices need network connectivity to that host; `localhost` on the phone means the phone itself, not your computer.

## Docker option

```bash
docker build -t clipforge .
docker run --rm -p 8000:8000 -v "$PWD/work:/app/work" clipforge
```

## Important
- Use only videos you own or are authorized to download and edit. Follow YouTube's Terms of Service and copyright law. This is not designed to bypass access controls or DRM.
- This is a prototype. Jobs are kept in process memory and are lost on restart; don't expose it publicly without authentication, rate limits, cleanup, and secure deployment.
- The server does the video processing. The iPhone is the control panel, not the heavy processing device.
- AI highlight detection and subtitles are planned next; this initial version cuts evenly spaced sections, center-crops them to 9:16, and exports MP4.
