import os; os.environ['PATH']='D:/Solfware/ShareX;'+os.environ['PATH']
import sys, re; sys.path.insert(0,'.'); sys.path.insert(0,'src')
from pathlib import Path
import sqlite3, jieba, json
from config import load_config
from knowledge.sqlite_store import get_db, init_db
from knowledge.chroma_store import get_chroma_collection, add_chunks
from retrieval.embedding_service import EmbeddingService
from data.splitter import GaokaoTextSplitter

config=load_config()
db=get_db(config)
init_db(db)
chroma=get_chroma_collection(config)
embed=EmbeddingService(mode='local',local_path='models/bge-m3')
splitter=GaokaoTextSplitter()

# Clear old FTS5 content
db.execute('DELETE FROM corpus_fts')
db.commit()
print('Cleared old FTS5 data')

# Get all raw_data
rows=db.execute('SELECT id,source_file,source_dir,format,content FROM raw_data').fetchall()
print(f'Processing {len(rows)} documents...')

total_chunks=0
for row_id,fname,sdir,fmt,text in rows:
    if not text or len(text.strip()) < 50: continue
    # Clean: collapse whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {3,}', '  ', text)
    text = text.strip()
    if len(text) < 100: continue

    # Determine content type
    ctype = 'article'
    if '直播' in sdir or '演讲' in sdir or '课程' in sdir or '避坑' in sdir or '视频' in sdir:
        ctype = 'live_transcript'

    # Chunk
    chunks = splitter.split_text(text, ctype, {
        'source': sdir,
        'content_type': ctype,
        'source_file': fname,
        'date': '2025',
    })

    # Insert into FTS5
    for i, c in enumerate(chunks):
        chunk_id = f"{Path(fname).stem}_chunk_{i}"
        tokenized = " ".join(jieba.cut_for_search(c['content']))
        db.execute(
            'INSERT INTO corpus_fts (content, source, content_type, date, chunk_index) VALUES (?,?,?,?,?)',
            (c['content'], c['metadata']['source'], ctype, '2025', i)
        )
        c['id'] = chunk_id
        total_chunks += 1

    db.commit()

    # Embed and add to ChromaDB in batches
    batch_size = 50
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        add_chunks(chroma, [
            {'id': c['id'], 'content': c['content'], 'metadata': c['metadata']}
            for c in batch
        ])

    print(f'  [{fmt}] {fname[:40]} -> {len(chunks)} chunks')

print(f'Done! {total_chunks} total chunks indexed')
db.close()
