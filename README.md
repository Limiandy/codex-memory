# Codex Memory

Codex Memory is a local Codex plugin that uses GPT-5.4-Mini as a memory decision model, reviews candidates through deterministic gates, and stores approved long-term memories in a local SQLite Ledger.

## Runtime

- `memory-engine`: extracts, classifies, and ranks memory candidates with `gpt-5.4-mini`.
- `memory-review`: validates schema, evidence, confidence, TTL, duplicate risk, and secret-like content.
- `memory-ledger`: local SQLite audit trail at `~/.codex-memory/ledger.sqlite3`.
- `mcp`: exposes `codex_memory_status`, `codex_memory_search`, `codex_memory_ingest`, and `codex_memory_queue`.

The local SQLite Ledger is the only runtime store and source of truth.

## Commands

```bash
./scripts/codex-memory status
./scripts/codex-memory doctor
./scripts/codex-memory ingest "默认使用中文回答"
./scripts/codex-memory search "中文回答偏好"
./scripts/codex-memory queue --status quarantined
```

Set `CODEX_MEMORY_MODEL` to override the default model. The default is `gpt-5.4-mini`.

## Privacy

Codex Memory stores events in `~/.codex-memory/ledger.sqlite3`. By default, event payloads are sanitized before storage: allowed fields are retained, long strings are truncated, and secret-like values are redacted. Stored event payloads include `_raw_payload_stored: false`.

Reviewed memory content and evidence can still be stored when they pass review gates. Use `./scripts/codex-memory queue`, `promote`, `reject`, and `delete` to inspect and manage memory records.

To clear all local state, stop active Codex sessions that use this plugin and remove the local state directory:

```bash
rm -rf ~/.codex-memory
```

Raw event storage is opt-in and should only be used for local debugging:

```bash
CODEX_MEMORY_STORE_RAW_EVENTS=1 ./scripts/codex-memory ingest "debug text"
```

When raw event storage is enabled, original event payloads are written to the local Ledger with `_raw_payload_stored: true`.

## Experimental CLI

The public alpha command surface is focused on local memory: `status`, `doctor`, `ingest`, `search`, `queue`, `promote`, `reject`, `delete`, `recall-feedback`, `expire`, `audit`, `plugin`, `govern`, and `govern-periodic`.

Experimental cognitive, knowledge, skill, and workflow commands are hidden behind an explicit environment switch:

```bash
CODEX_MEMORY_ENABLE_EXPERIMENTAL_CLI=1 ./scripts/codex-memory workflow-plan "plan this task"
```
