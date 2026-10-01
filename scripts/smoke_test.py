import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = 4188


def request_json(path, payload=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"http://127.0.0.1:{PORT}{path}",
        data=data,
        headers=headers,
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=3) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def main():
    env = os.environ.copy()
    env["ACC_HOST"] = "127.0.0.1"
    env["ACC_PORT"] = str(PORT)
    env["ACC_NO_BROWSER"] = "1"
    process = subprocess.Popen(
        [sys.executable, str(ROOT / "app" / "server.py")],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.time() + 8
        last_error = None
        while time.time() < deadline:
            if process.poll() is not None:
                out, err = process.communicate(timeout=1)
                raise RuntimeError(f"Server exited early.\nSTDOUT:\n{out}\nSTDERR:\n{err}")
            try:
                status, health = request_json("/api/health")
                if status == 200 and health.get("ok"):
                    break
            except Exception as error:
                last_error = error
                time.sleep(0.15)
        else:
            raise RuntimeError(f"Server did not become ready: {last_error}")

        checks = {
            "/api/health": request_json("/api/health"),
            "/api/summary": request_json("/api/summary"),
            "/api/workspace": request_json("/api/workspace"),
            "/api/local-ai/status": request_json("/api/local-ai/status"),
            "/api/workspace/browse": request_json("/api/workspace/browse", {"path": ""}),
        }
        for path, (status, payload) in checks.items():
            if status != 200:
                raise RuntimeError(f"{path} returned HTTP {status}")
            if not isinstance(payload, dict):
                raise RuntimeError(f"{path} returned non-object JSON")

        created_status, created = request_json("/api/tasks/create", {
            "title": "Smoke task lifecycle",
            "description": "Create and cancel without starting a provider CLI.",
            "agent": "chatgpt_code",
            "project": "control_center",
            "send_now": False,
            "request_id": f"smoke-{os.getpid()}",
        })
        if created_status != 200 or not created.get("ok") or not created.get("tasks"):
            raise RuntimeError(f"task create failed: {created}")
        task_id = created["tasks"][0]["id"]
        cancelled_status, cancelled = request_json("/api/tasks/action", {
            "id": task_id,
            "action": "cancel",
        })
        if cancelled_status != 200 or not cancelled.get("ok"):
            raise RuntimeError(f"task cancel failed: {cancelled}")

        print("Smoke test PASS")
        for path in checks:
            print(f"  PASS {path}")
        print("  PASS task create/cancel lifecycle")
        return 0
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        for status in ("pending", "running", "paused", "waiting_credit", "completed", "failed", "cancelled"):
            folder = ROOT / "manager" / "tasks" / status
            if not folder.exists():
                continue
            for task_file in folder.glob("*.json"):
                try:
                    data = json.loads(task_file.read_text(encoding="utf-8-sig"))
                except Exception:
                    continue
                if str(data.get("request_id", "")).startswith("smoke-"):
                    task_file.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
