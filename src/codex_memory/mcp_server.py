from __future__ import annotations

import json
import sys
from typing import Any, Callable

from . import __version__
from .config import ensure_state_dir, load_config
from .ledger import Ledger
from .mempalace_adapter import MemPalaceAdapter
from .service import MemoryService


TOOLS = {
    "codex_memory_status": {
        "description": "Show lightweight Codex Memory ledger status.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "codex_memory_search": {
        "description": "Search reviewed long-term memory for context.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
                "cwd": {"type": "string"},
                "session_id": {"type": "string"},
            },
            "required": ["query"],
        },
    },
    "codex_memory_ingest": {
        "description": "Submit content to the memory engine for review and possible storage.",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}, "event_type": {"type": "string", "default": "manual"}},
            "required": ["text"],
        },
    },
    "codex_memory_queue": {
        "description": "List local memory ledger entries by status.",
        "inputSchema": {
            "type": "object",
            "properties": {"status": {"type": "string"}, "limit": {"type": "integer", "default": 20}},
        },
    },
    "codex_memory_promote": {
        "description": "Promote a reviewed memory to active and optionally file it to MemPalace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "memory_id": {"type": "string"},
                "note": {"type": "string", "default": ""},
                "file_to_mempalace": {"type": "boolean", "default": True},
            },
            "required": ["memory_id"],
        },
    },
    "codex_memory_reject": {
        "description": "Reject a memory candidate with optional review note.",
        "inputSchema": {
            "type": "object",
            "properties": {"memory_id": {"type": "string"}, "note": {"type": "string", "default": ""}},
            "required": ["memory_id"],
        },
    },
    "codex_memory_delete": {
        "description": "Soft-delete a memory from local active use.",
        "inputSchema": {
            "type": "object",
            "properties": {"memory_id": {"type": "string"}, "note": {"type": "string", "default": ""}},
            "required": ["memory_id"],
        },
    },
    "codex_memory_recall_feedback": {
        "description": "Mark an explicit recall result as useful or harmful.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "memory_id": {"type": "string"},
                "outcome": {"type": "string", "enum": ["positive", "negative"]},
                "note": {"type": "string", "default": ""},
            },
            "required": ["memory_id", "outcome"],
        },
    },
    "codex_memory_expire": {
        "description": "Expire active memories whose TTL has elapsed.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "codex_memory_reconcile": {
        "description": "Reconcile old audit-only hook events so pending counts reflect real work.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "codex_memory_consolidate": {
        "description": "Consolidate repeated project memories into global cross-project experience.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "codex_memory_govern": {
        "description": "Evaluate global memory quality and optionally apply safe optimization actions.",
        "inputSchema": {
            "type": "object",
            "properties": {"apply": {"type": "boolean", "default": False}},
        },
    },
    "codex_memory_govern_periodic": {
        "description": "Run global memory governance only if its periodic interval is due.",
        "inputSchema": {
            "type": "object",
            "properties": {"interval_minutes": {"type": "integer", "default": 60}},
        },
    },
    "codex_memory_reconcile_mempalace": {
        "description": "Check and optionally repair Ledger/MemPalace consistency.",
        "inputSchema": {
            "type": "object",
            "properties": {"apply": {"type": "boolean", "default": False}},
        },
    },
    "codex_memory_audit": {
        "description": "Summarize memory review health and queue counts.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "codex_memory_diagnostics": {
        "description": "Run heavier diagnostics, including MemPalace status.",
        "inputSchema": {"type": "object", "properties": {}},
    },
}


def main() -> int:
    config = load_config()
    ensure_state_dir(config)
    ledger = Ledger(config.ledger_path)
    handlers: dict[str, Callable[[dict[str, Any]], Any]] = {
        "codex_memory_status": lambda args: _status(config, ledger),
        "codex_memory_search": lambda args: _with_service(
            lambda service: service.search_context(
                str(args["query"]),
                int(args.get("limit", 5)),
                cwd=args.get("cwd"),
                session_id=args.get("session_id"),
            )
        ),
        "codex_memory_ingest": lambda args: _with_service(
            lambda service: service.ingest_event(str(args.get("event_type", "manual")), {"text": args["text"]})
        ),
        "codex_memory_queue": lambda args: ledger.list_memories(args.get("status"), int(args.get("limit", 20))),
        "codex_memory_promote": lambda args: _with_service(
            lambda service: service.promote_memory(
                str(args["memory_id"]),
                str(args.get("note", "")),
                bool(args.get("file_to_mempalace", True)),
            )
        ),
        "codex_memory_reject": lambda args: _with_service(
            lambda service: service.reject_memory(str(args["memory_id"]), str(args.get("note", "")))
        ),
        "codex_memory_delete": lambda args: _with_service(
            lambda service: service.delete_memory(str(args["memory_id"]), str(args.get("note", "")))
        ),
        "codex_memory_recall_feedback": lambda args: _with_service(
            lambda service: service.recall_feedback(
                str(args["memory_id"]),
                str(args["outcome"]),
                str(args.get("note", "")),
            )
        ),
        "codex_memory_expire": lambda args: _with_service(lambda service: service.expire_due_memories()),
        "codex_memory_reconcile": lambda args: _with_service(lambda service: service.reconcile()),
        "codex_memory_consolidate": lambda args: _with_service(lambda service: service.consolidate_memories()),
        "codex_memory_govern": lambda args: _with_service(lambda service: service.govern_memories(bool(args.get("apply", False)))),
        "codex_memory_govern_periodic": lambda args: _with_service(
            lambda service: service.periodic_governance(int(args.get("interval_minutes", 60)))
        ),
        "codex_memory_reconcile_mempalace": lambda args: _with_service(
            lambda service: service.reconcile_mempalace(bool(args.get("apply", False)))
        ),
        "codex_memory_audit": lambda args: _audit(ledger),
        "codex_memory_diagnostics": lambda args: _diagnostics(config, ledger),
    }
    try:
        for line in sys.stdin:
            if not line.strip():
                continue
            _handle(line, handlers)
    finally:
        ledger.close()
    return 0


def _status(config, ledger: Ledger) -> dict[str, Any]:
    return {
        "ledger": ledger.stats(),
        "model": config.model,
        "mempalace": {"status": "not_loaded", "hint": "Use codex_memory_diagnostics for MemPalace checks."},
    }


def _diagnostics(config, ledger: Ledger) -> dict[str, Any]:
    return {
        "ledger": ledger.stats(),
        "model": config.model,
        "mempalace": MemPalaceAdapter(config).status(),
    }


def _audit(ledger: Ledger) -> dict[str, Any]:
    stats = ledger.stats()
    return {
        "stats": stats,
        "quarantine_sample": ledger.list_memories("quarantined", 10),
        "rejected_sample": ledger.list_memories("rejected", 10),
    }


def _with_service(callback: Callable[[MemoryService], Any]) -> Any:
    service = MemoryService(load_config())
    try:
        return callback(service)
    finally:
        service.close()


def _handle(line: str, handlers: dict[str, Callable[[dict[str, Any]], Any]]) -> None:
    try:
        request = json.loads(line)
        method = request.get("method")
        request_id = request.get("id")
        if method == "initialize":
            _send({"jsonrpc": "2.0", "id": request_id, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "codex-memory", "version": __version__}}})
            return
        if method == "notifications/initialized":
            return
        if method == "tools/list":
            tools = [{"name": name, **spec} for name, spec in TOOLS.items()]
            _send({"jsonrpc": "2.0", "id": request_id, "result": {"tools": tools}})
            return
        if method == "tools/call":
            params = request.get("params") or {}
            name = params.get("name")
            args = params.get("arguments") or {}
            if name not in handlers:
                raise ValueError(f"unknown tool: {name}")
            result = handlers[name](args)
            _send({"jsonrpc": "2.0", "id": request_id, "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}})
            return
        _send({"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"unknown method: {method}"}})
    except Exception as exc:
        request_id = None
        try:
            request_id = json.loads(line).get("id")
        except Exception:
            pass
        _send({"jsonrpc": "2.0", "id": request_id, "error": {"code": -32000, "message": str(exc)}})


def _send(data: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    raise SystemExit(main())
