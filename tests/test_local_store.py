import os
import tempfile
import unittest
from pathlib import Path

from codex_memory.config import Config, load_config
from codex_memory.schema import Evidence, MemoryCandidate
from codex_memory.service import MemoryService


class LocalStoreTest(unittest.TestCase):
    def setUp(self):
        os.environ["CODEX_MEMORY_FAKE_MODEL"] = "1"
        os.environ.pop("CODEX_MEMORY_MIRROR_MEMPALACE", None)

    def tearDown(self):
        os.environ.pop("CODEX_MEMORY_FAKE_MODEL", None)
        os.environ.pop("CODEX_MEMORY_STATE_DIR", None)
        os.environ.pop("CODEX_MEMORY_MIRROR_MEMPALACE", None)

    def test_default_config_uses_ledger_primary_without_mempalace_mirror(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["CODEX_MEMORY_STATE_DIR"] = tmp
            config = load_config()
            self.assertEqual(config.primary_store, "ledger")
            self.assertFalse(config.mirror_mempalace)

    def test_active_memory_is_usable_without_mempalace(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(
                model="gpt-5.4-mini",
                state_dir=Path(tmp),
                ledger_path=Path(tmp) / "ledger.sqlite3",
                palace_path=str(Path(tmp) / "palace"),
                min_active_confidence=0.82,
                min_quarantine_confidence=0.62,
                duplicate_threshold=0.9,
                max_evidence_quote_chars=500,
            )
            service = MemoryService(config)
            try:
                memory_id = service.ledger.add_candidate(
                    MemoryCandidate(
                        content="经验：自有 ledger 数据层必须作为主存储，MemPalace 只能作为可选镜像。",
                        memory_type="experience",
                        proposed_action="store",
                        confidence=0.95,
                        importance=0.9,
                        ttl="long",
                        scope="global",
                        domain="memory_system",
                        category="architecture",
                        subcategory="mempalace",
                        triggers=["ledger", "MemPalace", "主存储"],
                        evidence=[Evidence(source="test", quote="自有 ledger 数据层必须作为主存储")],
                        reason="local store test",
                    ),
                    "active",
                    {"status": "active"},
                )
                service.runtime.sync_memory(memory_id)
                status = service.status()
                self.assertTrue(status["store"]["primary"])
                self.assertTrue(status["mempalace"]["disabled"])
                result = service.store.search("ledger 主存储 MemPalace", limit=3)
                self.assertEqual(result[0]["id"], memory_id)
            finally:
                service.close()
