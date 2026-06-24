"""Transcribe all remaining videos (FLV, AVI, WMV) using faster-whisper on GPU."""
import os, sys, subprocess, sqlite3, time, tempfile
from pathlib import Path

# Setup env
os.environ['HF_HOME'] = 'D:/huggingface_cache'
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ['PATH'] = 'D:/Solfware/ShareX;' + os.environ['PATH']

from faster_whisper import WhisperModel

SRC = Path('D:/WSL/@张雪峰志愿填报合集')
FF = 'D:/Solfware/ShareX/ffmpeg.exe'
DB = Path('D:/zhangxuefengagent/data/zhangxuefeng.db')
OUT = Path('D:/zhangxuefengagent/data/extracted')

VIDEO_EXTS = {'.flv', '.avi', '.wmv', '.mov', '.mkv', '.mp4'}

conn = sqlite3.connect(str(DB))

# Get already processed files
done = set(r[0] for r in conn.execute('SELECT source_file FROM raw_data').fetchall())

# Find remaining videos
videos = sorted(
    [p for p in SRC.rglob('*') if p.suffix.lower() in VIDEO_EXTS and p.name not in done],
    key=lambda p: p.stat().st_size
)

if not videos:
    print('No remaining videos to transcribe!')
    conn.close()
    sys.exit(0)

total_size = sum(p.stat().st_size for p in videos) // 1024 // 1024
print(f'Remaining videos: {len(videos)} ({total_size} MB total)')

# Load model
print('Loading Whisper medium on CUDA...')
model = WhisperModel('medium', device='cuda', compute_type='float16')
print('Model ready.')

success = 0
skip = 0
start_time = time.time()

for idx, fpath in enumerate(videos):
    rel = fpath.relative_to(SRC)
    out_txt = OUT / rel.parent / (rel.stem + '.txt')
    size_mb = fpath.stat().st_size // 1024 // 1024

    # Ensure output dir exists
    out_txt.parent.mkdir(parents=True, exist_ok=True)

    # Skip if already extracted
    if out_txt.exists() and out_txt.stat().st_size > 100:
        conn.execute('INSERT OR IGNORE INTO raw_data(source_file,source_dir,format,content,word_count) VALUES(?,?,?,?,?)',
                     (fpath.name, str(rel.parent), fpath.suffix.lower(), out_txt.read_text(encoding='utf-8'), out_txt.stat().st_size))
        conn.commit()
        skip += 1
        continue

    # ETA
    elapsed = time.time() - start_time
    processed = success + skip
    rate = processed / max(elapsed, 1)
    remaining = len(videos) - idx - 1
    eta_min = remaining / max(rate, 0.001) / 60

    print(f'[{idx+1}/{len(videos)}] [{size_mb}MB] {rel.parent.name}/{fpath.name[:40]} (ETA: {eta_min:.0f}min)', flush=True)

    try:
        # Extract audio to temp file (avoid long path issues)
        audio_fd, audio_path = tempfile.mkstemp(suffix='.wav', prefix='whisper_')
        os.close(audio_fd)

        r = subprocess.run(
            [FF, '-y', '-i', str(fpath), '-ar', '16000', '-ac', '1', '-vn', audio_path],
            capture_output=True, timeout=300
        )
        if r.returncode != 0:
            print(f'  FFmpeg error: {r.stderr.decode("utf-8","ignore")[:200]}', flush=True)
            os.remove(audio_path)
            continue

        # Transcribe
        segments, info = model.transcribe(audio_path, language='zh')
        text = ''.join(s.text for s in segments)

        # Cleanup temp audio
        os.remove(audio_path)

        if len(text.strip()) < 20:
            print(f'  WARN: very short transcript ({len(text)} chars), skipping', flush=True)
            continue

        # Save
        out_txt.write_text(text, encoding='utf-8')

        # DB insert
        conn.execute(
            'INSERT OR IGNORE INTO raw_data(source_file,source_dir,format,content,word_count) VALUES(?,?,?,?,?)',
            (fpath.name, str(rel.parent), fpath.suffix.lower(), text, len(text))
        )
        conn.commit()

        # Delete source video after success
        fpath.unlink()

        success += 1
        print(f'  OK: {len(text)} chars, deleted.', flush=True)

    except Exception as e:
        print(f'  FAIL: {e}', flush=True)

conn.close()

total_time = (time.time() - start_time) / 60
print(f'\nDone! Transcribed {success} videos, skipped {skip}, in {total_time:.0f} min.')
