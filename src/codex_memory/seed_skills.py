from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
from typing import Any

from .security import redact_secrets
from .taxonomy import tokenize


DEFAULT_AGENCY_AGENTS_REPO = "https://github.com/msitarzewski/agency-agents.git"


class AgencySkillSeeder:
    def __init__(self, ledger: Any):
        self.ledger = ledger

    def seed(
        self,
        source: str | None = None,
        repo_url: str = DEFAULT_AGENCY_AGENTS_REPO,
        limit: int | None = None,
        category: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(source).expanduser().resolve() if source else _clone_repo(repo_url, Path(tmp) / "agency-agents")
            commit = _git_commit(root)
            skills = _load_agent_skills(root, limit=limit, category=category)
            if dry_run:
                return {"source": str(root), "repo_url": repo_url, "commit": commit, "dry_run": True, "skill_count": len(skills), "skills": [_summary(item) for item in skills[:20]]}
            created = []
            for skill in skills:
                record = self.ledger.record_cognitive_record(
                    "skill",
                    "seed_skill",
                    f"agency-agents:{skill['path']}",
                    skill["content"],
                    "active",
                    "global",
                    domain=skill["category"],
                    category="seed_skill",
                    subcategory=skill["slug"],
                    confidence=0.76,
                    importance=0.68,
                    strength=0.95,
                    metadata={
                        "skill_type": "seed_skill",
                        "name": skill["name"],
                        "description": skill["description"],
                        "category": skill["category"],
                        "source_repo": repo_url,
                        "source_commit": commit,
                        "source_path": skill["path"],
                        "license": "MIT",
                        "frontmatter": skill["frontmatter"],
                    },
                    source_kind="agency_agents_seed",
                )
                created.append({"id": record.get("id"), "name": skill["name"], "path": skill["path"]})
            return {"source": str(root), "repo_url": repo_url, "commit": commit, "dry_run": False, "skill_count": len(created), "created": created[:50]}


def relevant_seed_skills(ledger: Any, prompt: str, limit: int = 4) -> list[dict[str, Any]]:
    tokens = set(tokenize(prompt))
    if not tokens:
        return []
    candidates = []
    for record in ledger.list_cognitive_records(layer="skill", status="active", limit=1000):
        if record.get("record_type") != "seed_skill":
            continue
        metadata = record.get("metadata_json") or {}
        haystack = " ".join(
            [
                str(metadata.get("name") or ""),
                str(metadata.get("description") or ""),
                str(metadata.get("category") or ""),
                str(record.get("content") or "")[:2000],
            ]
        )
        overlap = len(tokens.intersection(set(tokenize(haystack))))
        if overlap <= 0:
            continue
        candidates.append((overlap, float(record.get("importance") or 0), record))
    candidates.sort(key=lambda item: (item[0], item[1], str(item[2].get("updated_at") or "")), reverse=True)
    return [item[2] for item in candidates[:limit]]


def seed_skill_basis_summary(skills: list[dict[str, Any]]) -> str:
    if not skills:
        return "No seed skills matched this task."
    parts = []
    for skill in skills[:4]:
        metadata = skill.get("metadata_json") or {}
        parts.append(f"{metadata.get('name')}: {metadata.get('description')}")
    return " | ".join(parts)


def _clone_repo(repo_url: str, target: Path) -> Path:
    proc = subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, str(target)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError("failed to clone seed skill repository: " + proc.stderr[:500])
    return target


def _git_commit(root: Path) -> str | None:
    proc = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def _load_agent_skills(root: Path, limit: int | None = None, category: str | None = None) -> list[dict[str, Any]]:
    skills = []
    for path in sorted(root.rglob("*.md")):
        relative = path.relative_to(root).as_posix()
        if relative.startswith((".git/", ".github/", "integrations/", "examples/")):
            continue
        if category and not relative.startswith(category.strip("/") + "/"):
            continue
        parsed = _parse_agent_file(root, path)
        if not parsed:
            continue
        skills.append(parsed)
        if limit and len(skills) >= limit:
            break
    return skills


def _parse_agent_file(root: Path, path: Path) -> dict[str, Any] | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = _frontmatter(text)
    name = str(frontmatter.get("name") or "").strip()
    description = str(frontmatter.get("description") or "").strip()
    if not name or not description:
        return None
    relative = path.relative_to(root).as_posix()
    category = relative.split("/", 1)[0]
    content = _content(name, description, body)
    return {
        "name": name,
        "description": description,
        "path": relative,
        "category": category,
        "slug": path.stem,
        "frontmatter": frontmatter,
        "content": content,
    }


def _frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    raw = text[4:end]
    data = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"')
    body = text[end + 4 :].strip()
    return data, body


def _content(name: str, description: str, body: str) -> str:
    clean = " ".join(str(redact_secrets(body)).split())
    return f"Seed skill: {name}. Description: {description}. Source guidance: {clean[:4000]}"


def _summary(skill: dict[str, Any]) -> dict[str, str]:
    return {"name": skill["name"], "description": skill["description"], "path": skill["path"]}
