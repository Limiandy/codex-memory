from __future__ import annotations

import json
from pathlib import Path

from .feedback_classifier import RuntimeSkillFeedbackClassifier
from .skill_need import SkillNeedClassifier


DEFAULT_BENCHMARK_FIXTURE = Path(__file__).resolve().parents[2] / "benchmarks" / "runtime_skill" / "tasks.jsonl"


def run_runtime_skill_benchmark(fixture_path: str | None = None, synthetic: bool = False) -> dict[str, object]:
    classifier = SkillNeedClassifier(model=None)
    feedback = RuntimeSkillFeedbackClassifier()
    loaded = None if synthetic else _load_fixture(Path(fixture_path).expanduser() if fixture_path else DEFAULT_BENCHMARK_FIXTURE)
    tasks = loaded["tasks"] if loaded else _benchmark_tasks()
    feedback_cases = loaded["feedback"] if loaded else _feedback_cases()
    trigger_total = 0
    trigger_correct = 0
    trigger_false_positive = 0
    trigger_false_negative = 0
    direct_total = 0
    direct_correct = 0
    error_samples = []
    for item in tasks:
        decision = classifier.classify(item["prompt"])
        expected = bool(item["skill_needed"])
        if expected:
            trigger_total += 1
            if decision.skill_needed:
                trigger_correct += 1
            else:
                trigger_false_negative += 1
                error_samples.append({"kind": "false_negative", "prompt": item["prompt"], "expected": expected, "actual": decision.skill_needed})
        else:
            direct_total += 1
            if not decision.skill_needed:
                direct_correct += 1
            else:
                trigger_false_positive += 1
                error_samples.append({"kind": "false_positive", "prompt": item["prompt"], "expected": expected, "actual": decision.skill_needed})
    feedback_correct = 0
    feedback_errors = []
    for item in feedback_cases:
        decision = feedback.classify(item["prompt"])
        if decision and decision.feedback_target == item["target"]:
            feedback_correct += 1
        else:
            feedback_errors.append({"prompt": item["prompt"], "expected": item["target"], "actual": decision.feedback_target if decision else None})
    return {
        "task_count": len(tasks),
        "feedback_count": len(feedback_cases),
        "source": "synthetic" if synthetic or not loaded else str(loaded["path"]),
        "skill_trigger_recall": _ratio(trigger_correct, trigger_total),
        "skill_trigger_precision": _ratio(trigger_correct, trigger_correct + trigger_false_positive),
        "direct_answer_skip_accuracy": _ratio(direct_correct, direct_total),
        "feedback_attribution_accuracy": _ratio(feedback_correct, len(feedback_cases)),
        "counts": {
            "trigger_total": trigger_total,
            "trigger_correct": trigger_correct,
            "trigger_false_positive": trigger_false_positive,
            "trigger_false_negative": trigger_false_negative,
            "direct_total": direct_total,
            "direct_correct": direct_correct,
            "feedback_correct": feedback_correct,
        },
        "error_samples": error_samples[:20],
        "feedback_error_samples": feedback_errors[:20],
        "categories": loaded["categories"] if loaded else {
            "direct_answer": 100,
            "creative_design": 100,
            "planning_business": 100,
            "engineering": 100,
            "feedback": 100,
            "ambiguous": 50,
        },
    }


def _load_fixture(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    tasks: list[dict[str, object]] = []
    feedback: list[dict[str, str]] = []
    categories: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = json.loads(line)
        kind = str(item.get("kind") or "task")
        category = str(item.get("category") or kind)
        categories[category] = categories.get(category, 0) + 1
        if kind == "feedback":
            feedback.append({"prompt": str(item["prompt"]), "target": str(item["target"])})
        else:
            tasks.append({"prompt": str(item["prompt"]), "skill_needed": bool(item["skill_needed"])})
    return {"path": path, "tasks": tasks, "feedback": feedback, "categories": categories}


def _benchmark_tasks() -> list[dict[str, object]]:
    direct = [{"prompt": f"现在天气怎么样？ #{idx}", "skill_needed": False} for idx in range(100)]
    creative = [{"prompt": f"帮我设计一个品牌 logo 方向 #{idx}", "skill_needed": True} for idx in range(100)]
    planning = [{"prompt": f"帮我制定一个产品营销策略 #{idx}", "skill_needed": True} for idx in range(100)]
    engineering = [{"prompt": f"帮我修复这个 bug 并运行测试 #{idx}", "skill_needed": True} for idx in range(100)]
    ambiguous_signals = ["测试", "修复", "代码", "test", "fix"] * 10
    ambiguous = [{"prompt": prompt, "skill_needed": False} for prompt in ambiguous_signals[:50]]
    return [*direct, *creative, *planning, *engineering, *ambiguous]


def _feedback_cases() -> list[dict[str, str]]:
    base = [
        ("很好", "final_result"),
        ("这个方向很好", "skill_strategy"),
        ("这个提问方式很好", "first_action"),
        ("不是我的偏好", "memory_basis"),
        ("这个模板不适合", "seed_skill"),
    ]
    return [{"prompt": text + f" #{idx}", "target": target} for idx in range(20) for text, target in base]


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0
