import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
import execution_support


class ExecutionSupportTests(unittest.TestCase):
    def test_redact_known_secret_shapes(self):
        with mock.patch.dict(os.environ, {"DEMO_API_KEY": "super-secret-value"}, clear=False):
            text = execution_support.redact(
                "bearer abcdef123 token=hello sk-abcdefghijklmnop super-secret-value"
            )
        self.assertNotIn("super-secret-value", text)
        self.assertNotIn("abcdef123", text)
        self.assertNotIn("sk-abcdefghijklmnop", text)

    def test_inventory_skips_hidden_and_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ok.txt").write_text("ok", encoding="utf-8")
            (root / ".hidden.txt").write_text("hidden", encoding="utf-8")
            (root / "backups").mkdir()
            (root / "backups" / "old.txt").write_text("old", encoding="utf-8")
            found = execution_support.inventory(root)
            self.assertIn(str((root / "ok.txt").resolve()), found)
            self.assertNotIn(str((root / ".hidden.txt").resolve()), found)
            self.assertNotIn(str((root / "backups" / "old.txt").resolve()), found)

    def test_atomic_json_replaces_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "state.json"
            execution_support.atomic_json(target, {"ok": True})
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"ok": True})
            self.assertEqual(list(target.parent.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
