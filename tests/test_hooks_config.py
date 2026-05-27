import json
import unittest
from pathlib import Path


class HooksConfigTest(unittest.TestCase):
    def test_root_hooks_cover_memory_collection_chain(self):
        config = json.loads(Path("hooks.json").read_text(encoding="utf-8"))
        hooks = config["hooks"]
        for name in ("SessionStart", "UserPromptSubmit", "PostToolUse", "Stop", "PreCompact"):
            self.assertIn(name, hooks)

    def test_hook_commands_are_portable(self):
        text = Path("hooks.json").read_text(encoding="utf-8")
        self.assertNotIn("/Users/limengkai", text)
        self.assertNotIn("hook-probe", text)
        self.assertIn("CODEX_PLUGIN_ROOT", text)

    def test_release_probe_hooks_are_not_present(self):
        self.assertFalse(Path(".codex/hooks.json").exists())


if __name__ == "__main__":
    unittest.main()
