"""OCR scanned PDFs using PyMuPDF + Tesseract. CPU-only, reliable."""
import os, sys, sqlite3, time, re, io
from pathlib import Path

# Setup Tesseract
os.environ['TESSDATA_PREFIX'] = 'D:/zhangxuefengagent/tessdata'
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

import fitz
from PIL import Image

SRC = Path('D:/WSL/@张雪峰志愿填报合集')
OUT = Path('D:/zhangxuefengagent/data/extracted')
DB = Path('D:/zhangxuefengagent/data/zhangxuefeng.db')

# Get already in DB
conn = sqlite3.connect(str(DB))
in_db = set(r[0] for r in conn.execute('SELECT source_file FROM raw_data WHERE format != ".mp4" AND format != ".flv" AND format != ".avi"').fetchall())

# Find missing scanned PDFs
missing = []
for p in sorted(SRC.rglob('*.pdf'), key=lambda p: p.stat().st_size):
    if p.name in in_db:
        continue
    try:
        doc = fitz.open(str(p))
        text_sample = ''.join(doc[i].get_text() for i in range(min(3, len(doc)))).strip()
        if len(text_sample) < 100:
            missing.append((p, doc.page_count))
        doc.close()
    except:
        pass

if not missing:
    print('No scanned PDFs to OCR!')
    conn.close()
    sys.exit(0)

total_pages = sum(p[1] for p in missing)
print(f'PDFs to OCR: {len(missing)}, total pages: {total_pages}')
print('Using Tesseract (CPU), chi_sim+eng, 200 DPI')

success = 0
start_time = time.time()
pages_done = 0

for idx, (fpath, page_count) in enumerate(missing):
    rel = fpath.relative_to(SRC)
    out_txt = OUT / rel.parent / (rel.stem + '.txt')
    out_txt.parent.mkdir(parents=True, exist_ok=True)

    if out_txt.exists() and out_txt.stat().st_size > 100:
        text = out_txt.read_text(encoding='utf-8')
        conn.execute('INSERT OR IGNORE INTO raw_data(source_file,source_dir,format,content,word_count) VALUES(?,?,?,?,?)',
                     (fpath.name, str(rel.parent), '.pdf', text, len(text)))
        conn.commit()
        pages_done += page_count
        continue

    # ETA
    elapsed = max(time.time() - start_time, 1)
    rate = pages_done / elapsed
    remaining = total_pages - pages_done
    eta_min = remaining / max(rate, 0.01) / 60

    size_mb = fpath.stat().st_size // 1024 // 1024
    print(f'[{idx+1}/{len(missing)}] {page_count}p {size_mb}MB {rel.parent.name}/{fpath.name[:40]} (ETA: {eta_min:.0f}min)', flush=True)

    try:
        doc = fitz.open(str(fpath))
        full_text = []
        t_page_start = time.time()

        for page_num in range(page_count):
            page = doc[page_num]
            # 200 DPI balance speed/quality
            mat = fitz.Matrix(200/72, 200/72)
            pix = page.get_pixmap(matrix=mat)
            img = Image.open(io.BytesIO(pix.tobytes('png')))

            # Tesseract OCR
            text = pytesseract.image_to_string(img, lang='chi_sim+eng', config='--psm 6')
            if text.strip():
                full_text.append(text.strip())

        doc.close()

        if not full_text:
            print(f'  WARN: no text OCRed', flush=True)
            pages_done += page_count
            continue

        combined = '\n\n'.join(full_text)
        combined = re.sub(r'\n{3,}', '\n\n', combined)
        combined = re.sub(r' {3,}', '  ', combined)

        out_txt.write_text(combined, encoding='utf-8')
        conn.execute(
            'INSERT OR IGNORE INTO raw_data(source_file,source_dir,format,content,word_count) VALUES(?,?,?,?,?)',
            (fpath.name, str(rel.parent), '.pdf', combined, len(combined))
        )
        conn.commit()
        success += 1
        pages_done += page_count
        pps = page_count / max(time.time() - t_page_start, 1)
        print(f'  OK: {len(combined)} chars ({pps:.1f} p/s)', flush=True)

    except Exception as e:
        pages_done += page_count
        print(f'  FAIL: {e}', flush=True)

conn.close()
total_time = (time.time() - start_time) / 60
print(f'\nDone! OCRed {success}/{len(missing)} PDFs in {total_time:.0f} min.')
