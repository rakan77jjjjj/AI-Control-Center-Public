import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
import workspace


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.project = self.base / "project"
        self.project.mkdir()
        (self.project / "sub").mkdir()
        (self.project / "sub" / "file.txt").write_text("ok", encoding="utf-8")
        self.config = self.base / "projects.json"
        self.state = self.base / "workspace_state.json"
        self.config.write_text(json.dumps({
            "active_project": "test",
            "projects": {
                "test": {
                    "name": "Test",
                    "path": str(self.project),
                    "enabled": True
                }
            }
        }), encoding="utf-8")
        self.patches = [
            mock.patch.object(workspace, "PROJECTS_FILE", self.config),
            mock.patch.object(workspace, "WORKSPACE_FILE", self.state),
        ]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()
        self.tmp.cleanup()

    def test_safe_path_stays_inside_project(self):
        _, _, root, target = workspace.safe_path("sub/file.txt")
        self.assertEqual(root, self.project.resolve())
        self.assertEqual(target, (self.project / "sub" / "file.txt").resolve())

    def test_path_traversal_is_blocked(self):
        with self.assertRaises(ValueError):
            workspace.safe_path("../outside.txt")

    def test_browse_project(self):
        result = workspace.browse_project("sub")
        self.assertEqual(result["current"], "sub")
        self.assertEqual(result["items"][0]["name"], "file.txt")

    def test_empty_registry_gets_generic_control_center_default(self):
        self.config.write_text("{}", encoding="utf-8")
        with mock.patch.object(workspace, "ROOT", self.base):
            result = workspace.normalize_registry()
        self.assertEqual(result["active_project"], "control_center")
        self.assertIn("control_center", result["projects"])
        self.assertNotIn("last_light", result["projects"])


if __name__ == "__main__":
    unittest.main()
