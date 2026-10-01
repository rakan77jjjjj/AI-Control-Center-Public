"""Supervised bridge from AI Control Center tasks to provider CLIs."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from execution_support import TASK_LOCK, atomic_json, inventory, kill_tree, record_outputs, redact

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
TASKS = ROOT / "manager" / "tasks"
OUTPUTS = ROOT / "data" / "agent_outputs"
RUNTIME = ROOT / "runtime"
AGENTS_FILE = CONFIG / "agents.json"
WORKSPACES_FILE = CONFIG / "agent_workspaces.json"
RUNTIME_CONFIG_FILE = CONFIG / "agent_runtime.json"
ACTIVE_CONTEXT = RUNTIME / "active_task_context.json"
STATUSES = ("pending", "running", "paused", "waiting_credit", "completed", "failed", "cancelled")

_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="real-agent")
_ACTIVE: dict[str, dict] = {}
_ACTIVE_LOCK = threading.Lock()
_STATUS_CACHE = {"time": 0.0, "value": None}
_STATUS_LOCK = threading.Lock()


def _load(path: Path, default=None):
    if default is None:
        default = {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default
    except (OSError, ValueError):
        return default


def _save(path: Path, data):
    atomic_json(path, data)


def _resolve(value):
    if not value:
        return None
    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def _find_task(task_id):
    safe = Path(str(task_id)).name
    for status in STATUSES:
        path = TASKS / status / safe
        if path.exists():
            return path, status
    return None, None


def _probe(command):
    executable = shutil.which(command)
    if not executable:
        return {"connected": False, "executable": None, "version": None, "error": f"Command not found: {command}"}
    try:
        done = subprocess.run([executable, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=8)
        output = (done.stdout or done.stderr or "").strip()
        return {"connected": done.returncode == 0, "executable": executable, "version": output[:500], "error": None if done.returncode == 0 else output[:1000]}
    except Exception as error:
        return {"connected": False, "executable": executable, "version": None, "error": str(error)}


def _workspace_for(agent_id, task=None):
    if task:
        project = _load(CONFIG / "projects.json").get("projects", {}).get(task.get("project"), {})
        if not project.get("enabled", False):
            raise RuntimeError("Project is missing or disabled")
        if task.get("smoke_test"):
            if task.get("project") != "control_center":
                raise RuntimeError("Smoke tests must use Control Center")
            path = RUNTIME / "smoke-workspace"
            path.mkdir(parents=True, exist_ok=True)
            return {"allow_write": False}, path
        entry = project.get("agent_workspaces", {}).get(agent_id)
        if entry and entry.get("path"):
            return entry, _resolve(entry["path"])
        if project.get("path"):
            return {"allow_write": not project.get("readOnly", False)}, _resolve(project["path"])
    entry = _load(WORKSPACES_FILE).get(agent_id, {})
    return entry, _resolve(entry.get("path"))


def agent_runtime_status(force=False):
    now = time.monotonic()
    with _STATUS_LOCK:
        cached = _STATUS_CACHE["value"]
        if cached is not None and not force and now - _STATUS_CACHE["time"] < 5:
            value = dict(cached)
        else:
            agents = {}
            for agent_id, cfg in _load(AGENTS_FILE).get("agents", {}).items():
                command = cfg.get("command") or ("claude" if agent_id == "claude_design" else "codex")
                probe = _probe(command)
                _, workspace = _workspace_for(agent_id)
                workspace_ready = bool(workspace and workspace.exists())
                agents[agent_id] = {
                    "display_name": cfg.get("display_name", agent_id),
                    "provider": cfg.get("provider", "unknown"),
                    "engine": probe.get("version") or command,
                    "connected": bool(probe.get("connected")),
                    "command_ready": bool(probe.get("connected")),
                    "workspace_ready": workspace_ready,
                    "workspace": str(workspace) if workspace else None,
                    "executable": probe.get("executable"),
                    "error": probe.get("error") or (None if workspace_ready else "Workspace path does not exist"),
                }
            runtime = _load(RUNTIME_CONFIG_FILE)
            value = {
                "connected": bool(agents) and all(item["connected"] for item in agents.values()),
                "model_ready": bool(agents) and all(item["connected"] for item in agents.values()),
                "model": "real-cli-agents",
                "local_only": False,
                "cloud_fallback": False,
                "max_concurrent_agents": int(runtime.get("max_concurrent_agents", 1)),
                "agents": agents,
            }
            _STATUS_CACHE.update(time=now, value=dict(value))
    with _ACTIVE_LOCK:
        value["active_tasks"] = len(_ACTIVE)
        value["active_task_ids"] = list(_ACTIVE)
    return value


def local_agent_status(force=False):
    return agent_runtime_status(force=force)


def _prompt(agent_id, task):
    role = "Design and content agent" if agent_id == "claude_design" else "Coding and testing agent"
    return f"""You are the {role} running under AI Control Center.
The human owner is the final authority. Work only inside the assigned workspace.
Never expose credentials. Never bypass sandbox or OS security. Never push or merge Git unless the task explicitly authorizes that exact action.
When the requested action needs a permission you do not have, stop safely and report the blocker.

TASK
Title: {task.get('title', '')}
Priority: {task.get('priority', 'normal')}
Instructions:
{task.get('description', '')}

At completion report exact files changed, validation performed, blockers, and next action."""


def _child_env(agent_id):
    safe_names = {
        "PATH",
        "HOME",
        "USERPROFILE",
        "LOCALAPPDATA",
        "APPDATA",
        "TEMP",
        "TMP",
        "SYSTEMROOT",
        "COMSPEC",
        "PATHEXT",
        "WINDIR",
        "LANG",
        "LC_ALL",
    }

    provider_names = {
        "claude_design": {
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_BASE_URL",
        },
        "chatgpt_code": {
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
        },
    }

    allowed = safe_names | provider_names.get(agent_id, set())

    return {
        key: value
        for key, value in os.environ.items()
        if key.upper() in allowed
    }


def _build_command(agent_id, cfg):
    agent_cfg = _load(AGENTS_FILE).get("agents", {}).get(agent_id, {})
    command_name = agent_cfg.get("command") or ("claude" if agent_id == "claude_design" else "codex")
    executable = shutil.which(command_name)
    if not executable:
        raise RuntimeError(f"Command not found: {command_name}")
    if agent_id == "claude_design":
        ccfg = cfg.get("claude", {})
        return [executable, "-p", "--output-format", "json", "--permission-mode", str(ccfg.get("permission_mode", "default")), "--max-turns", str(int(ccfg.get("max_turns", 40)))]
    ccfg = cfg.get("codex", {})
    command = [executable, "--ask-for-approval", str(ccfg.get("approval_policy", "never")), "--sandbox", str(ccfg.get("sandbox", "workspace-write")), "exec", "--json"]
    if ccfg.get("ephemeral"):
        command.append("--ephemeral")
    command.append("-")
    return command


def _extract_result(agent_id, stdout):
    text = stdout.strip()
    if not text:
        return ""
    if agent_id == "claude_design":
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                for key in ("result", "content", "message"):
                    if isinstance(data.get(key), str) and data[key].strip():
                        return data[key].strip()
        except ValueError:
            pass
        return text
    messages = []
    for line in text.splitlines():
        try:
            event = json.loads(line)
            item = event.get("item", {})
            candidate = item.get("text") or event.get("result") or event.get("message")
            if isinstance(candidate, str) and candidate.strip():
                messages.append(candidate.strip())
        except ValueError:
            continue
    return messages[-1] if messages else text


def _finish(task_id, details, *, status="completed", error=None):
    with TASK_LOCK:
        path, _ = _find_task(task_id)
        if not path:
            return
        task = _load(path)
        task.update(details)
        task["status"] = status
        task["finished_at"] = datetime.now().isoformat()
        if error:
            task["error"] = redact(error)
        target = TASKS / status / path.name
        _save(target, task)
        if target.resolve() != path.resolve():
            path.unlink(missing_ok=True)


def _worker(task_id):
    with _ACTIVE_LOCK:
        entry = _ACTIVE.get(task_id)
    if not entry:
        return
    cancel = entry["cancel"]
    started = time.monotonic()
    process = None
    output_dir = None
    workspace = None
    before = {}
    details = {}
    try:
        path, status = _find_task(task_id)
        if not path or status != "running":
            raise RuntimeError("Task is no longer running")
        task = _load(path)
        agent_id = task.get("agent")
        workspace_cfg, workspace = _workspace_for(agent_id, task)
        if not workspace or not workspace.exists():
            raise RuntimeError("Configured workspace does not exist")
        cfg = _load(RUNTIME_CONFIG_FILE)
        if not workspace_cfg.get("allow_write", True):
            cfg = dict(cfg, codex=dict(cfg.get("codex", {}), sandbox="read-only"))
        command = _build_command(agent_id, cfg)
        if task.get("smoke_test") and agent_id == "claude_design":
            command += ["--tools", "", "--no-session-persistence"]
        if task.get("smoke_test") and agent_id == "chatgpt_code":
            command[-1:-1] = ["--skip-git-repo-check"]
        output_dir = OUTPUTS / agent_id / f"attempt-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{task_id.replace('.json','')}"
        output_dir.mkdir(parents=True, exist_ok=True)
        before = inventory(workspace)
        process = subprocess.Popen(command, cwd=str(workspace), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", shell=False, env=_child_env(agent_id), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        with _ACTIVE_LOCK:
            entry["process"] = process
        _save(ACTIVE_CONTEXT, {"task_id": task_id, "agent": agent_id, "workspace": str(workspace), "pid": process.pid})
        prompt = _prompt(agent_id, task)
        def capture(stream, filename):
            with (output_dir / filename).open("w", encoding="utf-8") as log:
                for line in stream:
                    log.write(redact(line)); log.flush()
        readers = [threading.Thread(target=capture, args=(process.stdout, "stdout.log"), daemon=True), threading.Thread(target=capture, args=(process.stderr, "stderr.log"), daemon=True)]
        for thread in readers:
            thread.start()
        def deliver():
            try:
                process.stdin.write(prompt); process.stdin.close()
            except (OSError, ValueError):
                pass
        threading.Thread(target=deliver, daemon=True).start()
        timeout = min(int(cfg.get("task_timeout_seconds", 7200)), 90) if task.get("smoke_test") else int(cfg.get("task_timeout_seconds", 7200))
        reason = None
        while process.poll() is None:
            if cancel.wait(0.1):
                reason = "cancelled"; break
            if time.monotonic() - started >= max(1, timeout):
                reason = "timeout"; break
        if reason:
            kill_tree(process)
        process.wait(timeout=20)
        for thread in readers:
            thread.join(timeout=10)
        stdout = (output_dir / "stdout.log").read_text(encoding="utf-8")
        stderr = (output_dir / "stderr.log").read_text(encoding="utf-8")
        result = _extract_result(agent_id, stdout)
        (output_dir / "result.md").write_text(redact(result or "(No final text returned)"), encoding="utf-8")
        details = {"exit_code": process.returncode, "duration_seconds": round(time.monotonic()-started, 2), "result_file": str((output_dir/"result.md").relative_to(ROOT)), "result_preview": redact(result)[:5000], "provider": "claude_cli" if agent_id == "claude_design" else "codex_cli"}
        record_outputs(task, workspace, before, output_dir)
        if reason == "cancelled" or cancel.is_set():
            _finish(task_id, details, status="cancelled")
        elif reason == "timeout":
            _finish(task_id, details, status="failed", error=f"Agent timed out after {timeout}s")
        elif process.returncode:
            message = str(stderr or stdout or "No error details")[-5000:]
            credit = any(term in message.lower() for term in ("usage limit", "rate limit", "credit balance", "out of credits", "quota exceeded"))
            _finish(task_id, details, status="waiting_credit" if credit else "failed", error=message)
        else:
            _finish(task_id, details)
    except Exception as error:
        if process and process.poll() is None:
            kill_tree(process)
        _finish(task_id, details, status="cancelled" if cancel.is_set() else "failed", error=str(error))
    finally:
        with _ACTIVE_LOCK:
            _ACTIVE.pop(task_id, None)
        try:
            entry["lock"].close(); entry["lock_path"].unlink(missing_ok=True)
        except Exception:
            pass
        try:
            if ACTIVE_CONTEXT.exists() and _load(ACTIVE_CONTEXT).get("task_id") == task_id:
                ACTIVE_CONTEXT.unlink(missing_ok=True)
        except OSError:
            pass


def start_agent_task(task_id):
    with TASK_LOCK, _ACTIVE_LOCK:
        path, status = _find_task(task_id)
        if not path or status != "running":
            return False, "Task must be running before execution"
        if _ACTIVE:
            return False, "Another agent is active; task remains queued"
        RUNTIME.mkdir(parents=True, exist_ok=True)
        lease = RUNTIME / "agent-execution.lock"
        try:
            lock = lease.open("x", encoding="utf-8")
        except FileExistsError:
            return False, "Execution lock exists; inspect before retrying"
        lock.write(json.dumps({"server_pid": os.getpid(), "task_id": task_id})); lock.flush()
        _ACTIVE[task_id] = {"process": None, "cancel": threading.Event(), "lock": lock, "lock_path": lease}
        try:
            _EXECUTOR.submit(_worker, task_id)
        except Exception:
            _ACTIVE.pop(task_id); lock.close(); lease.unlink(missing_ok=True); raise
        return True, "Agent scheduled once; automatic retry disabled"


def start_local_task(task_id):
    return start_agent_task(task_id)


def stop_agent_task(task_id=None):
    with _ACTIVE_LOCK:
        entries = [value for key, value in _ACTIVE.items() if task_id is None or key == task_id]
        for entry in entries:
            entry["cancel"].set()
    return len(entries)


def _print_doctor():
    status = agent_runtime_status(force=True)
    print("\nAI-Control-Center Agent Doctor\n")
    for agent_id, info in status.get("agents", {}).items():
        print(("OK " if info.get("connected") else "ERR") + f"  {agent_id}")
        print(f"     provider:  {info.get('provider')}")
        print(f"     engine:    {info.get('engine')}")
        print(f"     workspace: {info.get('workspace')}")
        if info.get("error"):
            print(f"     error:     {info.get('error')}")
        print()
    print(f"Max concurrent write agents: {status.get('max_concurrent_agents')}\n")


if __name__ == "__main__":
    _print_doctor()
