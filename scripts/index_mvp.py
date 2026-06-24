"""Clean, chunk, embed, and index the best extracted text for MVP."""
import sys, os, re
from pathlib import Path

_PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT))
sys.path.insert(0, str(_PROJECT / "src"))

from config import load_config
from knowledge.sqlite_store import get_db, init_db
from knowledge.chroma_store import get_chroma_collection, add_chunks
from retrieval.embedding_service import EmbeddingService
from data.splitter import GaokaoTextSplitter

config = load_config()
db = get_db(config)
init_db(db)
chroma = get_chroma_collection(config)
embed = EmbeddingService(mode="local", local_path="models/bge-m3")
splitter = GaokaoTextSplitter()

# MVP: pick the best 5 files by pattern matching
MVP_PATTERNS = [
    ("专业介绍(详细)", "article"),
    ("认识专业-12大学科门类", "article"),
    ("高考志愿填报指南", "article"),
    ("志愿填报家长", "article"),
    ("中南财经政法大学", "article"),
]

total_chunks = 0
extracted_dir = Path("data/extracted")

# Find actual files matching patterns
to_index = []
for txt_file in extracted_dir.rglob("*.txt"):
    name = txt_file.name
    for pattern, content_type in MVP_PATTERNS:
        if pattern in name:
            to_index.append((txt_file, content_type))
            break

print(f"Found {len(to_index)} files to index")
for txt_file, content_type in to_index:
    text = txt_file.read_text(encoding="utf-8").strip()

    # Clean: remove excessive whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {3,}", "  ", text)

    if len(text) < 500:
        print(f"TOO SHORT ({len(text)}): {txt_file.name}")
        continue

    print(f"Chunking {txt_file.name} ({len(text)} chars)...")
    chunks = splitter.split_text(text, content_type, {
        "source": str(txt_file.parent.relative_to(extracted_dir)),
        "content_type": content_type,
        "date": "2025",
    })

    # Insert into FTS5
    import jieba
    for i, c in enumerate(chunks):
        chunk_id = f"{txt_file.stem}_chunk_{i}"
        tokenized = " ".join(jieba.cut_for_search(c["content"]))

        db.execute(
            "INSERT INTO corpus_fts (content, source, content_type, date, chunk_index) VALUES (?,?,?,?,?)",
            (c["content"], c["metadata"]["source"], content_type, "2025", i)
        )

        c["id"] = chunk_id
        total_chunks += 1

    db.commit()

    # Embed and add to ChromaDB
    print(f"  Embedding {len(chunks)} chunks...")
    add_chunks(chroma, [
        {"id": c["id"], "content": c["content"], "metadata": c["metadata"]}
        for c in chunks
    ])

    print(f"  -> {len(chunks)} chunks indexed")

print(f"\nDone! Total: {total_chunks} chunks in FTS5 + ChromaDB")
