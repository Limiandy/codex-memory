from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .model_client import ModelError
from .security import redact_secrets
from .skill_need import SkillNeedDecision


@dataclass(frozen=True)
class RuntimeSkill:
    name: str
    applies_to: str
    goal: str
    memory_basis_ids: list[str]
    memory_basis_summary: str
    strategy: list[str]
    first_action: dict[str, Any]
    avoid: list[str] = field(default_factory=list)
    confidence: float = 0.0
    intent: str = ""
    domain: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_type": "runtime",
            "name": self.name,
            "applies_to": self.applies_to,
            "goal": self.goal,
            "memory_basis_ids": self.memory_basis_ids,
            "memory_basis_summary": self.memory_basis_summary,
            "strategy": self.strategy,
            "first_action": self.first_action,
            "avoid": self.avoid,
            "confidence": self.confidence,
            "intent": self.intent,
            "domain": self.domain,
        }


class RuntimeSkillSynthesizer:
    def __init__(self, model: Any | None = None):
        self.model = model

    def synthesize(self, prompt: str, decision: SkillNeedDecision, memory_basis: dict[str, Any]) -> RuntimeSkill | None:
        if not decision.skill_needed:
            return None
        memories = memory_basis.get("memories") or []
        basis_ids = [str(item.get("id")) for item in memories if item.get("id")]
        basis_summary = str(memory_basis.get("memory_basis_summary") or "")
        if self.model is not None:
            modeled = self._model_synthesize(prompt, decision, memories, basis_ids, basis_summary)
            if modeled:
                return modeled
        return self._fallback_synthesize(decision, basis_ids, basis_summary, memories)

    def _fallback_synthesize(
        self,
        decision: SkillNeedDecision,
        basis_ids: list[str],
        basis_summary: str,
        memories: list[dict[str, Any]],
    ) -> RuntimeSkill:
        if decision.intent == "brand_logo_design":
            return RuntimeSkill(
                name="brand_logo_design_intake",
                applies_to="brand logo and visual identity design requests",
                goal="Use clean long-term preferences to narrow the design brief before any image generation.",
                memory_basis_ids=basis_ids,
                memory_basis_summary=basis_summary,
                strategy=[
                    "Do not generate the logo immediately.",
                    "First ask for brand name, industry or product, target audience, logo type, color or style constraints, and forbidden elements.",
                    "After clarification, offer 2-3 visual directions grounded in the memory basis.",
                ],
                first_action={
                    "type": "ask_clarifying_questions",
                    "questions": [
                        "品牌名称是什么？",
                        "面向什么行业或产品？",
                        "目标客户是谁？",
                        "希望文字标、图形标还是组合标？",
                        "有没有颜色、风格或禁忌元素？",
                    ],
                },
                avoid=[
                    "Do not invent organization positioning that is not present in memory basis.",
                    "Do not use complex gradients, noisy symbols, or cartoon-like style unless the user asks for them.",
                ],
                confidence=0.86 if memories else 0.72,
                intent=decision.intent,
                domain=decision.domain,
            )
        if decision.domain == "software_engineering":
            return RuntimeSkill(
                name="software_change_guarded_workflow",
                applies_to="bug fixes, code changes, refactors, and implementation tasks",
                goal="Make code changes through inspected context, minimal edits, and explicit verification evidence.",
                memory_basis_ids=basis_ids,
                memory_basis_summary=basis_summary,
                strategy=[
                    "Inspect the relevant repository context before editing.",
                    "Make the smallest focused change that satisfies the task.",
                    "Run the most relevant test, build, or lint command and report the result honestly.",
                ],
                first_action={"type": "inspect_repository"},
                avoid=[
                    "Do not edit before inspecting relevant files.",
                    "Do not claim completion without verification evidence.",
                    "Do not describe failed verification as success.",
                ],
                confidence=0.84,
                intent=decision.intent,
                domain=decision.domain,
            )
        return RuntimeSkill(
            name="memory_grounded_task_strategy",
            applies_to="multi-step task requiring remembered preferences or project context",
            goal="Use clean long-term memory to choose a task-specific strategy before acting.",
            memory_basis_ids=basis_ids,
            memory_basis_summary=basis_summary,
            strategy=[
                "Use only the memory basis listed below; do not invent missing user or organization facts.",
                "Ask for clarification when required information is missing.",
                "Keep the first response aligned with the task goal and known preferences.",
            ],
            first_action={"type": "proceed_or_clarify"},
            avoid=["Do not overfit unrelated memories.", "Do not expose raw memory internals."],
            confidence=0.78 if memories else 0.62,
            intent=decision.intent,
            domain=decision.domain,
        )

    def _model_synthesize(
        self,
        prompt: str,
        decision: SkillNeedDecision,
        memories: list[dict[str, Any]],
        basis_ids: list[str],
        basis_summary: str,
    ) -> RuntimeSkill | None:
        prompt_text = (
            "Generate a Runtime Skill for the current Codex request. "
            "A Runtime Skill is temporary, task-specific guidance for this turn. "
            "Use only the supplied clean memory basis. Do not invent user preferences, organization facts, or project constraints. "
            "If key information is missing, make first_action ask clarifying questions. "
            "Return concise JSON only.\n\n"
            f"User request:\n{redact_secrets(prompt)[:1200]}\n\n"
            f"Skill need decision:\n{decision.to_dict()}\n\n"
            f"Allowed memory basis:\n{_memory_basis_for_model(memories)}"
        )
        schema = {
            "name": "short_snake_case_name",
            "applies_to": "what current tasks this skill applies to",
            "goal": "one sentence",
            "memory_basis_ids": ["ids from allowed memory basis only"],
            "strategy": ["3-5 concise execution steps"],
            "first_action": {"type": "ask_clarifying_questions|inspect_repository|proceed_or_clarify", "questions": ["optional"]},
            "avoid": ["2-5 concise anti-patterns"],
            "confidence": 0.0,
        }
        try:
            result = self.model.complete_json(prompt_text, schema)
        except (ModelError, ValueError, TypeError):
            return None
        if not isinstance(result, dict):
            return None
        return _skill_from_model(result, decision, basis_ids, basis_summary)


class RuntimeSkillInjector:
    def format(self, skill: RuntimeSkill | None) -> str:
        if not skill:
            return ""
        lines = [
            f"Runtime Skill: {skill.name}",
            "Use this skill for the current request.",
            f"Applies to: {skill.applies_to}",
            f"Goal: {skill.goal}",
            "Memory basis:",
        ]
        lines.append("- " + skill.memory_basis_summary if skill.memory_basis_ids else "- No clean long-term memory matched; ask before assuming missing facts.")
        lines.append("Execution:")
        for index, step in enumerate(skill.strategy, 1):
            lines.append(f"{index}. {step}")
        if skill.first_action:
            lines.append("First action: " + _first_action_text(skill.first_action))
        if skill.avoid:
            lines.append("Avoid:")
            for item in skill.avoid[:5]:
                lines.append(f"- {item}")
        return "\n".join(lines)


def _first_action_text(action: dict[str, Any]) -> str:
    action_type = str(action.get("type") or "proceed")
    questions = [str(item) for item in action.get("questions") or [] if item]
    if not questions:
        return action_type
    return action_type + " -> " + " | ".join(questions[:6])


def _memory_basis_for_model(memories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    basis = []
    for memory in memories[:8]:
        basis.append(
            {
                "id": memory.get("id"),
                "type": memory.get("memory_type"),
                "content": str(redact_secrets(memory.get("content") or ""))[:240],
                "confidence": memory.get("confidence"),
                "importance": memory.get("importance"),
            }
        )
    return basis


def _skill_from_model(
    result: dict[str, Any],
    decision: SkillNeedDecision,
    allowed_basis_ids: list[str],
    basis_summary: str,
) -> RuntimeSkill | None:
    name = _safe_identifier(str(result.get("name") or "memory_grounded_runtime_skill"))
    applies_to = _clean_text(result.get("applies_to"), 180)
    goal = _clean_text(result.get("goal"), 220)
    strategy = [_clean_text(item, 220) for item in result.get("strategy") or [] if _clean_text(item, 220)]
    avoid = [_clean_text(item, 180) for item in result.get("avoid") or [] if _clean_text(item, 180)]
    first_action = result.get("first_action") if isinstance(result.get("first_action"), dict) else {}
    memory_basis_ids = [str(item) for item in result.get("memory_basis_ids") or [] if str(item) in set(allowed_basis_ids)]
    if not applies_to or not goal or len(strategy) < 2:
        return None
    if not first_action.get("type"):
        first_action = {"type": "proceed_or_clarify"}
    first_action = {
        "type": _clean_text(first_action.get("type"), 80) or "proceed_or_clarify",
        "questions": [_clean_text(item, 120) for item in first_action.get("questions") or [] if _clean_text(item, 120)][:6],
    }
    try:
        confidence = float(result.get("confidence"))
    except (TypeError, ValueError):
        confidence = 0.72
    return RuntimeSkill(
        name=name,
        applies_to=applies_to,
        goal=goal,
        memory_basis_ids=memory_basis_ids,
        memory_basis_summary=basis_summary,
        strategy=strategy[:5],
        first_action=first_action,
        avoid=avoid[:5],
        confidence=max(0.0, min(1.0, confidence)),
        intent=decision.intent,
        domain=decision.domain,
    )


def _clean_text(value: Any, limit: int) -> str:
    return " ".join(str(redact_secrets(value or "")).split())[:limit]


def _safe_identifier(value: str) -> str:
    text = "".join(ch if ch.isalnum() else "_" for ch in value.strip().lower())
    text = "_".join(part for part in text.split("_") if part)
    return (text or "runtime_skill")[:80]
