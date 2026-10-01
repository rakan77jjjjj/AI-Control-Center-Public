import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
import server


class ServerTaskTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.tasks = self.base / "tasks"
        for status in server.TASK_STATUSES:
            (self.tasks / status).mkdir(parents=True, exist_ok=True)
        self.projects = self.base / "projects.json"
        self.projects.write_text(json.dumps({
            "active_project": "demo",
            "projects": {
                "demo": {"name": "Demo", "path": str(self.base), "enabled": True}
            }
        }), encoding="utf-8")
        self.patches = [
            mock.patch.object(server, "TASKS", self.tasks),
            mock.patch.object(server, "PROJECTS_FILE", self.projects),
            mock.patch.object(server, "workspace_summary", lambda: {
                "active_project": "demo",
                "scope": {"type": "project", "relative_path": ""},
            }),
        ]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()
        self.tmp.cleanup()

    def test_create_task_and_cancel(self):
        task = server.create_task({
            "title": "Demo task",
            "description": "Check task lifecycle",
            "agent": "chatgpt_code",
            "project": "demo",
        })
        self.assertIsNotNone(task)
        self.assertEqual(task["status"], "pending")
        ok, _ = server.move_task(task["id"], "cancelled")
        self.assertTrue(ok)
        path, status = server.find_task(task["id"])
        self.assertEqual(status, "cancelled")
        self.assertTrue(path.exists())

    def test_request_id_is_idempotent(self):
        payload = {
            "title": "Idempotent task",
            "agent": "claude_design",
            "project": "demo",
            "request_id": "same-request",
        }
        first = server.create_task(payload)
        second = server.create_task(payload)
        self.assertEqual(first["id"], second["id"])

    def test_invalid_agent_rejected(self):
        task = server.create_task({
            "title": "Bad",
            "agent": "unknown",
            "project": "demo",
        })
        self.assertIsNone(task)

    def test_completed_task_cannot_requeue(self):
        task = server.create_task({
            "title": "Done task",
            "agent": "chatgpt_code",
            "project": "demo",
        })
        ok, _ = server.move_task(task["id"], "completed")
        self.assertTrue(ok)
        ok, message = server.move_task(task["id"], "pending")
        self.assertFalse(ok)
        self.assertTrue("cannot" in message.lower() or "requeue" in message.lower())


if __name__ == "__main__":
    unittest.main()
