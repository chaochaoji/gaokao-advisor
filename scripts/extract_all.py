"""Batch extract text from all sources, filter by year validity."""
import sys, os, re
from pathlib import Path
sys.path.insert(0, '.')
sys.path.insert(0, 'src')
from config import load_config
from knowledge.sqlite_store import get_db, init_db
from data.extractor import extract_text
import fitz

config = load_config()
db = get_db(config)
init_db(db)

# Add raw_data table if missing
db.executescript("""
CREATE TABLE IF NOT EXISTS raw_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT NOT NULL, source_dir TEXT NOT NULL,
    format TEXT NOT NULL, content TEXT NOT NULL,
    word_count INTEGER DEFAULT 0, metadata TEXT,
    status TEXT DEFAULT 'raw',
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_raw_status ON raw_data(status);
""")
db.commit()

SOURCE = Path("D:/WSL/@张雪峰志愿填报合集")
OUT = Path("data/extracted")
OUT.mkdir(parents=True, exist_ok=True)

SKIP_SCANNED = True
YEAR_MIN = 2022  # Only process content from 2022+

def is_scanned_pdf(path):
    try:
        doc = fitz.open(path)
        return all(len(doc[i].get_text().strip()) < 50 for i in range(min(3,len(doc))))
    except: return True

def has_valid_year(name, dname):
    years = re.findall(r'20(\d{2})', name + dname)
    if not years: return True  # No year = keep (likely timeless content)
    return any(int(y) >= YEAR_MIN % 100 for y in years)

formats = {'.pdf','.docx','.doc','.pptx','.ppt','.txt','.md','.xlsx','.xls'}
total = 0
for fpath in sorted(SOURCE.rglob('*')):
    if not fpath.is_file(): continue
    ext = fpath.suffix.lower()
    if ext not in formats: continue
    
    rel_dir = str(fpath.parent.relative_to(SOURCE))
    
    # Year filter
    if not has_valid_year(fpath.name, rel_dir):
        continue
    
    # Skip scanned PDFs
    if ext == '.pdf' and SKIP_SCANNED:
        try:
            if is_scanned_pdf(str(fpath)):
                continue
        except: continue
    
    # Skip video (process later)
    if ext in ('.mp4','.mkv','.avi','.mov','.flv'): continue
    
    out_sub = OUT / rel_dir
    out_sub.mkdir(parents=True, exist_ok=True)
    out_txt = out_sub / (fpath.stem + '.txt')
    
    # Skip if already extracted
    if out_txt.exists() and out_txt.stat().st_size > 100:
        # But ensure DB entry
        exists = db.execute('SELECT 1 FROM raw_data WHERE source_file=?',(fpath.name,)).fetchone()
        if not exists:
            text = out_txt.read_text(encoding='utf-8')
            db.execute('INSERT INTO raw_data(source_file,source_dir,format,content,word_count) VALUES(?,?,?,?,?)',(fpath.name,rel_dir,ext,text,len(text)))
            db.commit()
        continue
    
    print(f'Extracting: {rel_dir}/{fpath.name}')
    text = extract_text(str(fpath))
    if not text or len(text.strip()) < 50:
        print(f'  SKIP ({len(text)} chars)')
        continue
    
    out_txt.write_text(text, encoding='utf-8')
    wc = len(text)
    total += wc
    db.execute('INSERT INTO raw_data(source_file,source_dir,format,content,word_count) VALUES(?,?,?,?,?)',(fpath.name,rel_dir,ext,text,wc))
    db.commit()
    print(f'  -> {wc} chars')

print(f'Done: {total} chars total')
