from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


HOME = Path.home()
MARKETPLACE_ROOT = HOME
MARKETPLACE_NAME = "personal"
MARKETPLACE_PATH = HOME / ".agents" / "plugins" / "marketplace.json"
PLUGIN_NAME = "codex-memory"
PLUGIN_CONFIG_KEY = f'{PLUGIN_NAME}@{MARKETPLACE_NAME}'
PLUGIN_INSTALL_PATH = HOME / "plugins" / PLUGIN_NAME
CODEX_CONFIG = HOME / ".codex" / "config.toml"


@dataclass
class PluginState:
    marketplace_present: bool
    marketplace_policy: str | None
    installed_path_exists: bool
    codex_marketplace_enabled: bool
    codex_plugin_enabled: bool | None

    def to_dict(self) -> dict:
        status = "not_installed"
        if self.marketplace_present and self.installed_path_exists:
            if self.marketplace_policy == "NOT_AVAILABLE":
                status = "disabled_by_marketplace"
            elif self.codex_plugin_enabled is False:
                status = "off"
            elif self.codex_plugin_enabled is True:
                status = "on"
            else:
                status = "published"
        return {
            "status": status,
            "marketplace": MARKETPLACE_NAME,
            "marketplace_path": str(MARKETPLACE_PATH),
            "plugin_key": PLUGIN_CONFIG_KEY,
            "install_path": str(PLUGIN_INSTALL_PATH),
            "marketplace_present": self.marketplace_present,
            "marketplace_policy": self.marketplace_policy,
            "installed_path_exists": self.installed_path_exists,
            "codex_marketplace_enabled": self.codex_marketplace_enabled,
            "codex_plugin_enabled": self.codex_plugin_enabled,
        }


def status() -> dict:
    market = _read_marketplace()
    entry = _find_entry(market)
    config = _read_config()
    return PluginState(
        marketplace_present=entry is not None,
        marketplace_policy=(entry or {}).get("policy", {}).get("installation"),
        installed_path_exists=PLUGIN_INSTALL_PATH.is_dir(),
        codex_marketplace_enabled=f"[marketplaces.{MARKETPLACE_NAME}]" in config,
        codex_plugin_enabled=_plugin_enabled(config),
    ).to_dict()


def install(source_path: Path) -> dict:
    source_path = source_path.expanduser().resolve()
    if not (source_path / ".codex-plugin" / "plugin.json").is_file():
        raise RuntimeError(f"not a Codex plugin path: {source_path}")
    PLUGIN_INSTALL_PATH.parent.mkdir(parents=True, exist_ok=True)
    if PLUGIN_INSTALL_PATH.exists():
        shutil.rmtree(PLUGIN_INSTALL_PATH)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".DS_Store")
    shutil.copytree(source_path, PLUGIN_INSTALL_PATH, ignore=ignore)
    _write_marketplace("AVAILABLE")
    _upsert_config(enabled=True)
    return status()


def enable() -> dict:
    _write_marketplace("AVAILABLE")
    _upsert_config(enabled=True)
    return status()


def disable() -> dict:
    _upsert_config(enabled=False)
    return status()


def block() -> dict:
    _write_marketplace("NOT_AVAILABLE")
    _upsert_config(enabled=False)
    return status()


def uninstall(delete_files: bool = False) -> dict:
    market = _read_marketplace()
    market["plugins"] = [entry for entry in market.get("plugins", []) if entry.get("name") != PLUGIN_NAME]
    _save_marketplace(market)
    _remove_plugin_config()
    if delete_files and PLUGIN_INSTALL_PATH.exists():
        shutil.rmtree(PLUGIN_INSTALL_PATH)
    return status()


def _read_marketplace() -> dict:
    if MARKETPLACE_PATH.is_file():
        try:
            return json.loads(MARKETPLACE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"name": MARKETPLACE_NAME, "interface": {"displayName": "Personal"}, "plugins": []}


def _save_marketplace(data: dict) -> None:
    MARKETPLACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKETPLACE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_marketplace(policy: str) -> None:
    market = _read_marketplace()
    market["name"] = MARKETPLACE_NAME
    market.setdefault("interface", {}).setdefault("displayName", "Personal")
    plugins = [entry for entry in market.get("plugins", []) if entry.get("name") != PLUGIN_NAME]
    plugins.append(
        {
            "name": PLUGIN_NAME,
            "source": {"source": "local", "path": f"./plugins/{PLUGIN_NAME}"},
            "policy": {"installation": policy, "authentication": "ON_INSTALL"},
            "category": "Productivity",
        }
    )
    market["plugins"] = plugins
    _save_marketplace(market)


def _find_entry(market: dict) -> dict | None:
    for entry in market.get("plugins", []):
        if entry.get("name") == PLUGIN_NAME:
            return entry
    return None


def _read_config() -> str:
    if not CODEX_CONFIG.is_file():
        return ""
    return CODEX_CONFIG.read_text(encoding="utf-8")


def _write_config(text: str) -> None:
    CODEX_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    if CODEX_CONFIG.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        shutil.copy2(CODEX_CONFIG, CODEX_CONFIG.with_suffix(f".toml.codex-memory-{stamp}.bak"))
    CODEX_CONFIG.write_text(text, encoding="utf-8")


def _upsert_config(enabled: bool) -> None:
    text = _read_config()
    text = _remove_section(text, f"marketplaces.{MARKETPLACE_NAME}")
    text = _remove_section(text, f'plugins."{PLUGIN_CONFIG_KEY}"')
    block_text = (
        f'\n[marketplaces.{MARKETPLACE_NAME}]\n'
        f'last_updated = "{datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")}"\n'
        f'source_type = "local"\n'
        f'source = "{MARKETPLACE_ROOT}"\n'
        f'\n[plugins."{PLUGIN_CONFIG_KEY}"]\n'
        f"enabled = {str(enabled).lower()}\n"
    )
    _write_config(text.rstrip() + "\n" + block_text)


def _remove_plugin_config() -> None:
    text = _read_config()
    text = _remove_section(text, f'plugins."{PLUGIN_CONFIG_KEY}"')
    _write_config(text.rstrip() + "\n")


def _plugin_enabled(config: str) -> bool | None:
    section = _extract_section(config, f'plugins."{PLUGIN_CONFIG_KEY}"')
    if section is None:
        return None
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("enabled"):
            return stripped.split("=", 1)[1].strip().lower() == "true"
    return None


def _remove_section(text: str, name: str) -> str:
    lines = text.splitlines()
    out = []
    i = 0
    header = f"[{name}]"
    while i < len(lines):
        if lines[i].strip() == header:
            i += 1
            while i < len(lines) and not lines[i].lstrip().startswith("["):
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out).rstrip() + ("\n" if out else "")


def _extract_section(text: str, name: str) -> str | None:
    lines = text.splitlines()
    header = f"[{name}]"
    for idx, line in enumerate(lines):
        if line.strip() == header:
            section = [line]
            for next_line in lines[idx + 1 :]:
                if next_line.lstrip().startswith("["):
                    break
                section.append(next_line)
            return "\n".join(section)
    return None
