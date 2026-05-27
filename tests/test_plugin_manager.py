import json
import unittest
from pathlib import Path


class PluginConfigTest(unittest.TestCase):
    def test_mcp_config_is_portable(self):
        data = json.loads(Path(".mcp.json").read_text(encoding="utf-8"))
        server = data["mcpServers"]["codex-memory"]
        rendered = json.dumps(server)
        self.assertEqual(server["command"], "bash")
        self.assertIn("CODEX_PLUGIN_ROOT", rendered)
        self.assertNotIn("/Users/" + "limengkai", rendered)
        self.assertNotIn(str(Path.home()), rendered)

    def test_hooks_config_is_portable(self):
        rendered = Path("hooks.json").read_text(encoding="utf-8")
        self.assertIn("CODEX_PLUGIN_ROOT", rendered)
        self.assertNotIn("/Users/" + "limengkai", rendered)
        self.assertNotIn(str(Path.home()), rendered)
