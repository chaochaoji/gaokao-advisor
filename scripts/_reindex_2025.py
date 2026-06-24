"""Index 2025 gaokao data files into ChromaDB as score_data type.

Usage: python scripts/_reindex_2025.py
"""

import sys, os, hashlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from src.knowledge.chroma_store import get_chroma_collection, add_chunks
from src.config import load_config

DATA_DIR = Path(__file__).resolve().parent.parent / 'data' / 'extracted' / '2025_高考数据'

config = load_config()
col = get_chroma_collection(config)

# Remove existing 2025_高考数据 chunks before re-indexing
existing = col.get()
ids_to_delete = [i for i in existing['ids'] if i.startswith('2025_score_')]
if ids_to_delete:
    col.delete(ids=ids_to_delete)
    print(f'Deleted {len(ids_to_delete)} existing 2025_score_ chunks')

total_chunks = 0
for txt_file in sorted(DATA_DIR.glob('*.txt')):
    content = txt_file.read_text(encoding='utf-8')
    if not content.strip():
        continue

    # Split into chunks of ~1000 chars on paragraph boundaries
    paragraphs = content.split('\n\n')
    chunks = []
    current = ''
    for p in paragraphs:
        if len(current) + len(p) < 1200:
            current += p + '\n\n'
        else:
            if current.strip():
                chunks.append(current.strip())
            current = p + '\n\n'
    if current.strip():
        chunks.append(current.strip())

    for i, chunk in enumerate(chunks):
        chunk_id = f"2025_score_{txt_file.stem}_{i}"

        # Extract province from filename
        fname = txt_file.stem
        province = '全国'
        for p in ['北京', '天津', '上海', '广东', '江苏', '浙江', '山东', '河南',
                   '河北', '湖北', '湖南', '福建', '安徽', '江西', '辽宁', '四川',
                   '重庆', '陕西', '山西', '云南', '贵州', '广西', '甘肃', '吉林',
                   '黑龙江', '内蒙古', '新疆', '海南', '宁夏', '青海', '西藏']:
            if p in fname:
                province = p
                break

        add_chunks(col, [{
            'id': chunk_id,
            'content': chunk,
            'metadata': {
                'source': f'2025_高考数据/{txt_file.name}',
                'content_type': 'score_data',
                'date': '2025',
                'province': province,
                'chunk_index': i,
                'total_chunks': len(chunks),
            }
        }])
        total_chunks += 1

    print(f'  {txt_file.name}: {len(chunks)} chunks')

print(f'\nDone. Indexed {total_chunks} chunks as score_data.')
print(f'Collection size: {len(col._ids)}')
