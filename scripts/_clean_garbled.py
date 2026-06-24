"""Clean garbled documents from ChromaDB collection.

Documents with CJK character ratio < 30% are considered garbled
(corrupted OCR output) and are deleted.

Usage: python scripts/_clean_garbled.py [--dry-run] [--threshold 30]
"""

import sys, os, io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from src.knowledge.chroma_store import get_chroma_collection
from src.config import load_config
from collections import Counter


def cjk_ratio(text: str) -> float:
    """Return ratio of CJK characters in text."""
    if not text:
        return 0
    cjk = sum(1 for c in text if '一' <= c <= '鿿' or '㐀' <= c <= '䶿')
    return cjk / len(text)


def main():
    dry_run = '--dry-run' in sys.argv
    threshold = 30
    for arg in sys.argv:
        if arg.startswith('--threshold='):
            threshold = int(arg.split('=')[1])

    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE DELETE'}")
    print(f"CJK threshold: < {threshold}%")
    print()

    config = load_config()
    col = get_chroma_collection(config)
    ids = col._ids
    print(f"Total documents: {len(ids)}")

    # Identify garbled documents
    garbled_ids = []
    garbled_by_source = Counter()
    source_totals = Counter()

    batch_size = 5000
    for start in range(0, len(ids), batch_size):
        batch_ids = ids[start:start + batch_size]
        result = col.get(ids=batch_ids, include=['documents', 'metadatas'])
        docs = result.get('documents', [])
        metas = result.get('metadatas', [])

        for doc_id, doc, meta in zip(batch_ids, docs, metas):
            src = str(meta.get('source', 'unknown')) if meta else 'unknown'
            source_totals[src] += 1

            ratio = cjk_ratio(doc or '')
            if ratio * 100 < threshold:
                garbled_ids.append(doc_id)
                garbled_by_source[src] += 1

        if start % 20000 == 0 and start > 0:
            print(f"  Scanned {start}/{len(ids)}... found {len(garbled_ids)} garbled so far")

    print(f"\nGarbled documents: {len(garbled_ids)} ({len(garbled_ids) / max(len(ids), 1) * 100:.1f}%)")
    print(f"\n--- Top garbled sources ---")
    for src, cnt in garbled_by_source.most_common(15):
        total = source_totals.get(src, 1)
        print(f"  [{cnt}/{total} = {cnt / max(total, 1) * 100:.0f}%] {src[:90]}")

    if dry_run:
        print(f"\n[DRY RUN] Would delete {len(garbled_ids)} documents. No changes made.")
        return

    if not garbled_ids:
        print("\nNo garbled documents found.")
        return

    # Confirm
    print(f"\nAbout to DELETE {len(garbled_ids)} documents from ChromaDB.")
    print("Proceed? (y/N): ", end='')
    answer = input().strip().lower()
    if answer != 'y':
        print("Aborted.")
        return

    # Delete in batches
    delete_batch_size = 1000
    deleted = 0
    for i in range(0, len(garbled_ids), delete_batch_size):
        batch = garbled_ids[i:i + delete_batch_size]
        col.delete(ids=batch)
        deleted += len(batch)
        if i % 5000 == 0:
            print(f"  Deleted {deleted}/{len(garbled_ids)}...")

    print(f"\nDone. Deleted {deleted} garbled documents.")
    print(f"Remaining: {len(col._ids)} documents.")
    print("Collection auto-saved to pickle.")


if __name__ == '__main__':
    main()
