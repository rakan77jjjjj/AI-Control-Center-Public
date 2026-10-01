import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import real_agents
import server


class _Request:
    def __init__(self, host, origin=None):
        self.headers = {"Host": host}
        if origin is not None:
            self.headers["Origin"] = origin


class SecurityBoundaryTests(unittest.TestCase):
    def test_local_request_accepts_loopback(self):
        request = _Request(
            "127.0.0.1:4177",
            "http://127.0.0.1:4177",
        )
        self.assertTrue(
            server.request_is_local(
                request,
                require_same_origin=True,
            )
        )

    def test_local_request_rejects_dns_rebinding_host(self):
        request = _Request(
            "example.test:4177",
            "http://example.test:4177",
        )
        self.assertFalse(
            server.request_is_local(
                request,
                require_same_origin=True,
            )
        )

    def test_local_request_rejects_cross_origin(self):
        request = _Request(
            "127.0.0.1:4177",
            "http://example.test:4177",
        )
        self.assertFalse(
            server.request_is_local(
                request,
                require_same_origin=True,
            )
        )

    def test_agent_environment_does_not_inherit_unrelated_secrets(self):
        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": "/tmp/example",
            "OPENAI_API_KEY": "example-openai-key",
            "ANTHROPIC_API_KEY": "example-anthropic-key",
            "GITHUB_TOKEN": "must-not-be-forwarded",
            "AWS_SECRET_ACCESS_KEY": "must-not-be-forwarded",
        }

        with mock.patch.dict(os.environ, env, clear=True):
            child = real_agents._child_env("chatgpt_code")

        self.assertIn("OPENAI_API_KEY", child)
        self.assertNotIn("ANTHROPIC_API_KEY", child)
        self.assertNotIn("GITHUB_TOKEN", child)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", child)


if __name__ == "__main__":
    unittest.main()
