"""Extract text from old .doc and .ppt files using Microsoft Office COM automation."""
import os, sys, sqlite3, time, traceback
from pathlib import Path
import win32com.client
import pythoncom

SRC = Path('D:/WSL/@张雪峰志愿填报合集')
OUT = Path('D:/zhangxuefengagent/data/extracted')
DB = Path('D:/zhangxuefengagent/data/zhangxuefeng.db')

# Get already processed
conn = sqlite3.connect(str(DB))
in_db = set(r[0] for r in conn.execute('SELECT source_file FROM raw_data WHERE format != ".mp4" AND format != ".flv" AND format != ".avi"').fetchall())

# Find missing .doc and .ppt files
missing = sorted(
    [p for p in SRC.rglob('*') if p.suffix.lower() in {'.doc', '.ppt'} and p.name not in in_db],
    key=lambda p: p.stat().st_size
)

print(f'Files to process: {len(missing)}')
for f in missing:
    ext = f.suffix.lower()
    print(f'  [{ext}] {f.parent.name}/{f.name[:50]} ({f.stat().st_size//1024//1024}MB)')

if not missing:
    print('Nothing to do!')
    conn.close()
    sys.exit(0)

# Init COM (single-threaded, reuse app for all files)
pythoncom.CoInitialize()

word = None
ppt = None
success = 0

for idx, fpath in enumerate(missing):
    ext = fpath.suffix.lower()
    rel = fpath.relative_to(SRC)
    out_txt = OUT / rel.parent / (rel.stem + '.txt')
    out_txt.parent.mkdir(parents=True, exist_ok=True)

    print(f'[{idx+1}/{len(missing)}] {ext} {fpath.name[:50]}', flush=True)

    try:
        text = ''

        if ext == '.doc':
            if word is None:
                word = win32com.client.Dispatch('Word.Application')
                word.Visible = False
                word.DisplayAlerts = 0  # wdAlertsNone

            doc = None
            try:
                doc = word.Documents.Open(str(fpath), ReadOnly=True)
                text = doc.Content.Text
                doc.Close(SaveChanges=0)  # wdDoNotSaveChanges
            except Exception as e:
                print(f'  Word open error: {e}', flush=True)
                # Try recovery mode
                try:
                    doc = word.Documents.Open(str(fpath), ReadOnly=True, Format='wdOpenFormatText')
                    text = doc.Content.Text
                    doc.Close(SaveChanges=0)
                except:
                    pass

        elif ext == '.ppt':
            if ppt is None:
                ppt = win32com.client.Dispatch('PowerPoint.Application')
                ppt.Visible = False

            pres = None
            try:
                pres = ppt.Presentations.Open(str(fpath), ReadOnly=True, WithWindow=False)
                for slide in pres.Slides:
                    for shape in slide.Shapes:
                        if shape.HasTextFrame:
                            text += shape.TextFrame.TextRange.Text + '\n'
                pres.Close()
            except Exception as e:
                print(f'  PPT open error: {e}', flush=True)

        # Clean up text
        text = text.strip()
        # Remove excessive whitespace
        import re
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {3,}', '  ', text)

        if len(text) < 20:
            print(f'  SKIP: too short ({len(text)} chars)', flush=True)
            continue

        out_txt.write_text(text, encoding='utf-8')
        conn.execute(
            'INSERT OR IGNORE INTO raw_data(source_file,source_dir,format,content,word_count) VALUES(?,?,?,?,?)',
            (fpath.name, str(rel.parent), ext, text, len(text))
        )
        conn.commit()
        success += 1
        print(f'  OK: {len(text)} chars', flush=True)

    except Exception as e:
        print(f'  FAIL: {e}', flush=True)
        traceback.print_exc()

# Cleanup
if word:
    word.Quit()
if ppt:
    ppt.Quit()
pythoncom.CoUninitialize()

conn.close()
print(f'\nDone! Extracted {success}/{len(missing)} files.')
