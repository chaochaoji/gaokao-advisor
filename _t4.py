import os; os.environ['HF_HOME']='D:/huggingface_cache'
os.environ['HF_ENDPOINT']='https://hf-mirror.com'
import subprocess, sqlite3
from pathlib import Path
os.environ['PATH']='D:/Solfware/ShareX;'+os.environ['PATH']
from faster_whisper import WhisperModel

SRC=Path('D:/WSL/@张雪峰志愿填报合集')
FF='D:/Solfware/ShareX/ffmpeg.exe'
DB=Path('D:/zhangxuefengagent/data/zhangxuefeng.db')
OUT=Path('D:/zhangxuefengagent/data/extracted')

conn=sqlite3.connect(str(DB))
done=set(r[0] for r in conn.execute('SELECT source_file FROM raw_data').fetchall())
videos=sorted([p for p in SRC.rglob('*.mp4') if p.name not in done],key=lambda p:p.stat().st_size)
print(f'To transcribe: {len(videos)} videos')
print('Loading Whisper medium on CUDA (via HF mirror)...')
model=WhisperModel('medium',device='cuda',compute_type='float16')

for fpath in videos:
    size_mb=fpath.stat().st_size//1024//1024
    rel=fpath.relative_to(SRC)
    out_txt=OUT/rel.parent/(rel.stem+'.txt')
    if out_txt.exists() and out_txt.stat().st_size>100:continue
    print(f'[{size_mb}MB] {rel}')
    audio=str(out_txt)+'.wav'
    subprocess.run([FF,'-y','-i',str(fpath),'-ar','16000','-ac','1','-vn',audio],capture_output=True,timeout=120)
    seg,info=model.transcribe(audio,language='zh')
    text=''.join(s.text for s in seg)
    out_txt.parent.mkdir(parents=True,exist_ok=True)
    out_txt.write_text(text,encoding='utf-8')
    conn.execute('INSERT OR IGNORE INTO raw_data(source_file,source_dir,format,content,word_count) VALUES(?,?,?,?,?)',(fpath.name,str(rel.parent),'.mp4',text,len(text)))
    conn.commit()
    os.remove(audio)
    fpath.unlink()
    print(f'  -> {len(text)} chars, deleted')
conn.close()
print('Done!')
