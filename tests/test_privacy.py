import tempfile
import unittest
from pathlib import Path

from codex_memory.config import Config
from codex_memory.service import MemoryService


def _config(tmp: str, store_raw_events: bool = False) -> Config:
    return Config(
        model="gpt-5.4-mini",
        state_dir=Path(tmp),
        ledger_path=Path(tmp) / "ledger.sqlite3",
        min_active_confidence=0.82,
        min_quarantine_confidence=0.62,
        duplicate_threshold=0.9,
        max_evidence_quote_chars=500,
        store_raw_events=store_raw_events,
    )


class PrivacyTest(unittest.TestCase):
    def test_event_payload_is_sanitized_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = MemoryService(_config(tmp))
            try:
                event_id = service.record_event(
                    "manual",
                    {
                        "text": "use token=supersecretvalue1234567890",
                        "api_key": "sk-secretsecretsecret",
                        "attachment": "/private/tmp/raw.bin",
                    },
                    processed=True,
                )
                payload = service.ledger.get_event(event_id)["payload_json"]
                self.assertFalse(payload["_raw_payload_stored"])
                self.assertIn("_omitted_keys", payload)
                self.assertNotIn("api_key", payload)
                self.assertNotIn("supersecretvalue1234567890", str(payload))
                self.assertIn("[REDACTED]", payload["text"])
            finally:
                service.close()

    def test_raw_event_storage_requires_explicit_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = MemoryService(_config(tmp, store_raw_events=True))
            try:
                event_id = service.record_event(
                    "manual",
                    {"text": "token=supersecretvalue1234567890", "api_key": "sk-secretsecretsecret"},
                    processed=True,
                )
                payload = service.ledger.get_event(event_id)["payload_json"]
                self.assertTrue(payload["_raw_payload_stored"])
                self.assertEqual(payload["api_key"], "sk-secretsecretsecret")
                self.assertIn("supersecretvalue1234567890", payload["text"])
            finally:
                service.close()


if __name__ == "__main__":
    unittest.main()
