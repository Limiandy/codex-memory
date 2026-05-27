from __future__ import annotations

import os
from typing import Any

from .config import Config
from . import logger
from .schema import MemoryCandidate


TYPE_TO_LOCATION = {
    "user_preference": ("wing_user", "preferences"),
    "project_context": ("wing_project", "context"),
    "experience": ("wing_project", "lessons"),
    "fact": ("wing_facts", "facts"),
    "task_state": ("wing_project", "task_state"),
    "relationship": ("wing_user", "relationships"),
    "temporary": ("wing_sessions", "temporary"),
}


class MemPalaceAdapter:
    def __init__(self, config: Config):
        self.config = config
        self.disabled = bool(os.environ.get("CODEX_MEMORY_DISABLE_MEMPALACE")) or not config.mirror_mempalace
        if config.palace_path:
            os.environ["MEMPALACE_PALACE_PATH"] = config.palace_path

    def status(self) -> dict[str, Any]:
        if self.disabled:
            return {"disabled": True, "role": "optional_mirror", "primary_store": self.config.primary_store}
        try:
            from mempalace.mcp_server import tool_status

            result = tool_status()
            logger.debug("mempalace status", result=result)
            return result
        except Exception as exc:
            logger.error("mempalace status failed", error=str(exc))
            return {"error": str(exc)}

    def search(self, query: str, limit: int = 5, wing: str | None = None, room: str | None = None) -> dict[str, Any]:
        if self.disabled:
            return {"disabled": True, "results": []}
        try:
            from mempalace.mcp_server import tool_search

            result = tool_search(query=query, limit=limit, wing=wing, room=room)
            logger.debug("mempalace search", query=query, limit=limit, wing=wing, room=room, result=result)
            return result
        except Exception as exc:
            logger.error("mempalace search failed", query=query, error=str(exc))
            return {"error": str(exc), "results": []}

    def check_duplicate(self, content: str, threshold: float) -> list[dict[str, Any]]:
        if self.disabled:
            return []
        try:
            from mempalace.mcp_server import tool_check_duplicate

            result = tool_check_duplicate(content=content, threshold=threshold)
            logger.debug("mempalace duplicate check", content=content, threshold=threshold, result=result)
            return list(result.get("matches") or [])
        except Exception as exc:
            logger.error("mempalace duplicate check failed", content=content, error=str(exc))
            return []

    def file_candidate(self, candidate: MemoryCandidate) -> dict[str, Any]:
        if self.disabled:
            return {"skipped": "mempalace_disabled", "drawer_id": None, "triple_ids": []}
        wing, room = self.location_for(candidate)
        content = self._drawer_content(candidate)
        try:
            from mempalace.mcp_server import tool_add_drawer, tool_kg_add

            drawer = tool_add_drawer(
                wing=wing,
                room=room,
                content=content,
                added_by="codex-memory",
            )
            if not drawer.get("success"):
                logger.error("mempalace drawer write failed", candidate=candidate.to_dict(), drawer=drawer)
                return {
                    "error": drawer.get("error") or drawer.get("hint") or "mempalace_write_failed",
                    "drawer": drawer,
                    "drawer_id": None,
                    "triple_ids": [],
                }
            triple_ids: list[str] = []
            drawer_id = drawer.get("drawer_id")
            if candidate.memory_type == "fact" and drawer_id:
                for evidence in candidate.evidence[:3]:
                    triple = tool_kg_add(
                        subject="Codex memory",
                        predicate="records",
                        object=candidate.content[:120],
                        source_drawer_id=drawer_id,
                        source_closet=evidence.quote[:200],
                    )
                    if triple.get("success"):
                        triple_ids.append(str(triple.get("triple_id")))
            return {"drawer": drawer, "drawer_id": drawer_id, "triple_ids": triple_ids}
        except Exception as exc:
            logger.error("mempalace filing failed", candidate=candidate.to_dict(), error=str(exc))
            return {"error": str(exc), "drawer_id": None, "triple_ids": []}

    def location_for(self, candidate: MemoryCandidate) -> tuple[str, str]:
        default_wing, default_room = TYPE_TO_LOCATION.get(candidate.memory_type, ("wing_sessions", "memory"))
        wing = candidate.wing or default_wing
        room = candidate.room or default_room
        if candidate.scope == "project" and wing == "wing_project":
            wing = "wing_current_project"
        return wing, room

    def _drawer_content(self, candidate: MemoryCandidate) -> str:
        evidence = " | ".join(f"{e.source}: {e.quote[:240]}" for e in candidate.evidence[:3])
        return (
            f"TYPE:{candidate.memory_type}\n"
            f"SCOPE:{candidate.scope}\n"
            f"TTL:{candidate.ttl}\n"
            f"CONFIDENCE:{candidate.confidence:.2f}\n"
            f"IMPORTANCE:{candidate.importance:.2f}\n"
            f"MEMORY:{candidate.content}\n"
            f"EVIDENCE:{evidence}\n"
            f"REASON:{candidate.reason}"
        )
