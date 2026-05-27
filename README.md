# Codex Memory

Codex Memory is a local Codex plugin that uses GPT-5.4-Mini as a memory decision model, reviews candidates through deterministic gates, and stores approved long-term memories in a local SQLite Ledger.

## Runtime

- `memory-engine`: extracts, classifies, and ranks memory candidates with `gpt-5.4-mini`.
- `memory-review`: validates schema, evidence, confidence, TTL, duplicate risk, and secret-like content.
- `memory-ledger`: local SQLite audit trail at `~/.codex-memory/ledger.sqlite3`.
- `mcp`: exposes `codex_memory_status`, `codex_memory_search`, `codex_memory_ingest`, and `codex_memory_queue`.

MemPalace is no longer supported. The Ledger is the only runtime store and source of truth.

## Commands

```bash
./scripts/codex-memory status
./scripts/codex-memory ingest "默认使用中文回答"
./scripts/codex-memory search "中文回答偏好"
./scripts/codex-memory queue --status quarantined
```

Set `CODEX_MEMORY_MODEL` to override the default model. The default is `gpt-5.4-mini`.
