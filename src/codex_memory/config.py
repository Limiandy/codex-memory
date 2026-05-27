from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_MODEL = "gpt-5.4-mini"


@dataclass(frozen=True)
class Config:
    model: str
    state_dir: Path
    ledger_path: Path
    palace_path: str | None
    min_active_confidence: float
    min_quarantine_confidence: float
    duplicate_threshold: float
    max_evidence_quote_chars: int
    primary_store: str = "ledger"
    mirror_mempalace: bool = False


def _default_state_dir() -> Path:
    return Path(os.environ.get("CODEX_MEMORY_STATE_DIR", "~/.codex-memory")).expanduser()


def load_config() -> Config:
    state_dir = _default_state_dir()
    config_file = state_dir / "config.json"
    data: dict = {}
    if config_file.is_file():
        try:
            data = json.loads(config_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}

    model = os.environ.get("CODEX_MEMORY_MODEL") or data.get("model") or DEFAULT_MODEL
    palace_path = os.environ.get("MEMPALACE_PALACE_PATH") or data.get("palace_path")
    ledger_path = Path(data.get("ledger_path") or state_dir / "ledger.sqlite3").expanduser()
    primary_store = str(os.environ.get("CODEX_MEMORY_PRIMARY_STORE") or data.get("primary_store") or "ledger")
    mirror_mempalace = _bool(os.environ.get("CODEX_MEMORY_MIRROR_MEMPALACE"), bool(data.get("mirror_mempalace", False)))

    return Config(
        model=str(model),
        state_dir=state_dir,
        ledger_path=ledger_path,
        palace_path=str(palace_path) if palace_path else None,
        min_active_confidence=float(data.get("min_active_confidence", 0.82)),
        min_quarantine_confidence=float(data.get("min_quarantine_confidence", 0.62)),
        duplicate_threshold=float(data.get("duplicate_threshold", 0.9)),
        max_evidence_quote_chars=int(data.get("max_evidence_quote_chars", 500)),
        primary_store=primary_store,
        mirror_mempalace=mirror_mempalace,
    )


def ensure_state_dir(config: Config) -> None:
    config.state_dir.mkdir(parents=True, exist_ok=True)
    try:
        config.state_dir.chmod(0o700)
    except OSError:
        pass


def _bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
