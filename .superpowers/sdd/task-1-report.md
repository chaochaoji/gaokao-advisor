# Task 1: Session Store Migration — Structured Messages

## Status: DONE

## Commits
- `150e63c` feat: session_store supports structured messages with content_type + metadata

## Test Summary
- Isolated in-memory SQLite tests pass: structured dict messages, content_type propagation, metadata JSON round-trip, backward compatibility with old `add_turn(sid, user, assistant)` calls
- Old callers receive `content_type='text'` as default; no schema migration errors on existing databases (ALTER TABLE wrapped in try/except)

## Changes Made (single file)
- `src/knowledge/session_store.py`:
  - Added `import json` at top
  - `_init_tables`: added ALTER TABLE migration for `content_type TEXT DEFAULT 'text'` and `metadata TEXT` columns (wrapped in try/except for idempotency)
  - `add_turn`: extended signature with `content_type='text'` and `metadata=None`; accepts dict for `assistant_msg` (auto-unpack into structured_data, content_type, fallback_text)
  - `get_messages`: now returns `content_type` and `metadata` fields; defaults `content_type` to `'text'` if null; auto-deserializes `metadata` from JSON string

## Concerns
None. All assertions pass, backward compatibility verified.
