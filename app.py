from pathlib import Path
import os, re, uuid, subprocess, shutil, threading
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl

ROOT = Path(__file__).parent
WORK = ROOT / 'work'
WORK.mkdir(exist_ok=True)
app = FastAPI(title='ClipForge Personal AI Clipper')
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')
JOBS = {}

class ClipRequest(BaseModel):
    url: HttpUrl
    clip_length: int = 30
    max_clips: int = 3


def run(cmd, timeout=None):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=True)


def process_job(job_id, url, clip_length, max_clips):
    folder = WORK / job_id
    folder.mkdir(parents=True, exist_ok=True)
    try:
        JOBS[job_id].update(status='downloading', message='Getting video details…')
        # Only process videos the user owns or is authorized to download/process.
        run(['yt-dlp', '--no-playlist', '-f', 'bv*[height<=720]+ba/b[height<=720]', '--merge-output-format', 'mp4', '-o', str(folder / 'source.%(ext)s'), str(url)], timeout=1800)
        files = [p for p in folder.glob('source.*') if p.suffix.lower() in ('.mp4','.mkv','.webm','.mov')]
        if not files:
            raise RuntimeError('Could not locate downloaded video file.')
        source = files[0]
        JOBS[job_id].update(status='analyzing', message='Checking video length…')
        info = run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(source)])
        duration = float(info.stdout.strip())
        if duration < 5:
            raise RuntimeError('This video is too short to clip.')
        # MVP moment selection: evenly spaced windows. Replace with transcript-based AI scoring next.
        actual_len = min(int(clip_length), max(5, int(duration)))
        count = min(int(max_clips), max(1, int(duration // actual_len)))
        if count == 0: count = 1
        starts = []
        if count == 1:
            starts = [max(0, (duration - actual_len) / 2)]
        else:
            usable = max(0, duration - actual_len)
            starts = [usable * i / (count - 1) for i in range(count)]
        clips = []
        JOBS[job_id].update(status='rendering', message='Creating vertical clips…')
        for i, start in enumerate(starts, 1):
            out = folder / f'clip-{i}.mp4'
            # Crop to vertical 9:16, scale to 720x1280; preserve audio when available.
            vf = "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280"
            run(['ffmpeg','-y','-ss',str(start),'-i',str(source),'-t',str(actual_len),'-vf',vf,'-c:v','libx264','-preset','veryfast','-crf','24','-c:a','aac','-b:a','128k','-movflags','+faststart',str(out)], timeout=1800)
            clips.append({'name': out.name, 'url': f'/jobs/{job_id}/{out.name}', 'start': round(start), 'duration': actual_len})
            JOBS[job_id]['message'] = f'Rendered clip {i} of {len(starts)}…'
        JOBS[job_id].update(status='done', message='Your clips are ready.', clips=clips)
    except subprocess.TimeoutExpired:
        JOBS[job_id].update(status='error', message='Processing took too long. Try a shorter or lower-resolution video.')
    except subprocess.CalledProcessError as e:
        detail = (e.stderr or e.stdout or 'Media processing failed')[-1200:]
        JOBS[job_id].update(status='error', message='Could not process this link. Check that the video is accessible and that you have permission to process it.', detail=detail)
    except Exception as e:
        JOBS[job_id].update(status='error', message=str(e))

@app.get('/', response_class=HTMLResponse)
def home():
    return (ROOT / 'templates' / 'index.html').read_text()

@app.post('/api/jobs')
def create_job(req: ClipRequest, background: BackgroundTasks):
    host = req.url.host.lower()
    if not (host == 'youtube.com' or host.endswith('.youtube.com') or host == 'youtu.be' or host.endswith('.youtu.be')):
        raise HTTPException(400, 'Please enter a YouTube URL.')
    if req.clip_length not in (30,45,60):
        raise HTTPException(400, 'Clip length must be 30, 45, or 60 seconds.')
    if req.max_clips not in (1,2,3,5):
        raise HTTPException(400, 'Choose 1, 2, 3, or 5 clips.')
    job_id = uuid.uuid4().hex[:10]
    JOBS[job_id] = {'id': job_id, 'status':'queued', 'message':'Queued…', 'clips':[]}
    background.add_task(process_job, job_id, str(req.url), req.clip_length, req.max_clips)
    return {'id': job_id}

@app.get('/api/jobs/{job_id}')
def get_job(job_id: str):
    if job_id not in JOBS: raise HTTPException(404, 'Job not found.')
    return JOBS[job_id]

@app.get('/jobs/{job_id}/{filename}')
def get_clip(job_id: str, filename: str):
    if not re.fullmatch(r'clip-\d+\.mp4', filename): raise HTTPException(400, 'Invalid filename.')
    path = WORK / job_id / filename
    if not path.is_file(): raise HTTPException(404, 'Clip not found.')
    return FileResponse(path, media_type='video/mp4', filename=filename)
