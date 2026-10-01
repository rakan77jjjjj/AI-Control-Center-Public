import json
import math
import shutil
import webbrowser
import os
import sys
import subprocess
import mimetypes
import functools
from execution_support import TASK_LOCK, atomic_json, gallery, resolve_output

from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from local_tools import (
    baseline as v32_baseline,
    scan as v32_scan,
    monitor_status as v32_monitor_status,
    recent_events as v32_recent_events,
    snapshot_create as v32_snapshot_create,
    snapshot_list as v32_snapshot_list,
    snapshot_restore as v32_snapshot_restore,
    snapshot_delete as v32_snapshot_delete
)


from workspace import (
    workspace_summary,
    select_project,
    browse_project,
    set_scope,
    add_project,
    update_project
)




from real_agents import (
    local_agent_status,
    start_local_task, stop_agent_task
)


ROOT = Path(__file__).resolve().parents[1]

CONFIG = ROOT / "config"
RUNTIME = ROOT / "runtime"
TASKS = ROOT / "manager" / "tasks"
ARCHIVE = ROOT / "archive"

STATE_FILE = RUNTIME / "system_state.json"
SETTINGS_FILE = CONFIG / "settings.json"
AGENTS_FILE = CONFIG / "agents.json"
PROJECTS_FILE = CONFIG / "projects.json"
CREDIT_FILE = CONFIG / "credit_budget.json"

EMERGENCY_LOCK = RUNTIME / "EMERGENCY_STOP.lock"

PENDING_APPROVALS = ROOT / "approvals" / "pending"
APPROVED_APPROVALS = ROOT / "approvals" / "approved"
REJECTED_APPROVALS = ROOT / "approvals" / "rejected"

INDEX_FILE = ROOT / "app" / "templates" / "index.html"
CSS_FILE = ROOT / "app" / "static" / "css" / "style.css"
JS_FILE = ROOT / "app" / "static" / "js" / "app.js"

APP_VERSION = "0.5.0-alpha.1"
MAX_BODY_BYTES = 1024 * 1024
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def request_is_local(handler, require_same_origin=False):
    host_header = handler.headers.get("Host", "")
    try:
        host_name = (urlparse("//" + host_header).hostname or "").lower()
    except ValueError:
        return False

    if host_name not in LOOPBACK_HOSTS:
        return False

    if require_same_origin:
        origin = handler.headers.get("Origin")
        if origin:
            try:
                parsed = urlparse(origin)
                origin_host = (parsed.hostname or "").lower()
            except ValueError:
                return False

            if origin_host not in LOOPBACK_HOSTS:
                return False

            if parsed.netloc.lower() != host_header.lower():
                return False

    return True


def open_local_path(path):
    target = str(path)
    if os.name == "nt":
        os.startfile(target)
        return
    command = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.Popen(
        [command, target],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


TASK_STATUSES = [
    "pending",
    "running",
    "paused",
    "waiting_credit",
    "completed",
    "failed",
    "cancelled"
]

ARCHIVE_STATUSES = [
    "completed",
    "failed",
    "cancelled"
]

PRIORITY_ORDER = {
    "critical": 4,
    "high": 3,
    "normal": 2,
    "low": 1
}


for status in TASK_STATUSES:
    (TASKS / status).mkdir(
        parents=True,
        exist_ok=True
    )

for status in ARCHIVE_STATUSES:
    (ARCHIVE / status).mkdir(
        parents=True,
        exist_ok=True
    )

for folder in [
    RUNTIME,
    PENDING_APPROVALS,
    APPROVED_APPROVALS,
    REJECTED_APPROVALS
]:
    folder.mkdir(
        parents=True,
        exist_ok=True
    )


def task_locked(fn):
    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        with TASK_LOCK:
            return fn(*args, **kwargs)
    return wrapped

def load_json(path, default=None):

    if default is None:
        default = {}

    try:

        if not path.exists():
            return default

        return json.loads(
            path.read_text(
                encoding="utf-8-sig"
            )
        )

    except Exception:
        return default


def save_json(path, data):
    atomic_json(path, data)


def normalize_state():

    state = load_json(
        STATE_FILE,
        {}
    )

    state.setdefault(
        "system_status",
        "offline"
    )

    state.setdefault(
        "emergency_stop",
        False
    )

    agents_config = load_json(
        AGENTS_FILE,
        {}
    ).get(
        "agents",
        {}
    )

    runtime_agents = state.setdefault(
        "agents",
        {}
    )

    for agent_id in agents_config:

        old = runtime_agents.get(
            agent_id,
            {}
        )

        if isinstance(old, str):

            old = {
                "connection_status": old
            }

        old.setdefault(
            "connection_status",
            "not_connected"
        )

        old.setdefault(
            "enabled",
            False
        )

        old.setdefault(
            "paused",
            False
        )

        old.setdefault(
            "accept_new_tasks",
            False
        )

        old.setdefault(
            "last_action",
            None
        )

        runtime_agents[
            agent_id
        ] = old

    try:

        runtime_status = (
            local_agent_status()
        )

        runtime_map = (
            runtime_status.get(
                "agents",
                {}
            )
        )

        for agent_id in agents_config:

            info = (
                runtime_map.get(
                    agent_id,
                    {}
                )
            )

            runtime_agents[
                agent_id
            ][
                "connection_status"
            ] = (
                "connected"
                if info.get(
                    "connected"
                )
                else "not_connected"
            )

            runtime_agents[
                agent_id
            ][
                "engine"
            ] = info.get(
                "engine"
            )

            runtime_agents[
                agent_id
            ][
                "provider"
            ] = info.get(
                "provider"
            )

    except Exception:
        pass


    save_json(
        STATE_FILE,
        state
    )

    return state


def estimate_tokens(
    title,
    description,
    agent
):

    budgets = load_json(
        CREDIT_FILE,
        {}
    )

    config = budgets.get(
        agent,
        {}
    )

    text = (
        str(title)
        + "\n"
        + str(description)
    )

    prompt_estimate = max(
        1,
        math.ceil(
            len(text) / 4
        )
    )

    context_reserve = int(
        config.get(
            "context_reserve",
            4000
        )
    )

    output_reserve = int(
        config.get(
            "output_reserve",
            1500
        )
    )

    return (
        prompt_estimate
        + context_reserve
        + output_reserve
    )


def task_counts():

    result = {}

    for status in TASK_STATUSES:

        result[status] = len(
            list(
                (TASKS / status).glob(
                    "*.json"
                )
            )
        )

    return result


def archive_counts():

    result = {}

    for status in ARCHIVE_STATUSES:

        result[status] = len(
            list(
                (ARCHIVE / status).glob(
                    "*.json"
                )
            )
        )

    return result


def load_all_tasks():

    items = []

    for status in TASK_STATUSES:

        for file in (
            TASKS / status
        ).glob("*.json"):

            data = load_json(
                file,
                {}
            )

            data["file_id"] = (
                file.name
            )

            data["status"] = (
                status
            )

            data['status_label'] = {'pending':'QUEUED','running':'RUNNING','paused':'WAITING','waiting_credit':'WAITING FOR CREDIT','completed':'COMPLETED','failed':'FAILED','cancelled':'CANCELLED'}[status]
            if data.get('started_at'):
                end = datetime.fromisoformat(data['finished_at']) if data.get('finished_at') else datetime.now()
                data['duration_seconds'] = max(0, round((end-datetime.fromisoformat(data['started_at'])).total_seconds(), 1))
            items.append(data)

    items.sort(
        key=lambda item: (
            -PRIORITY_ORDER.get(
                item.get(
                    "priority",
                    "normal"
                ),
                0
            ),
            item.get(
                "created_at",
                ""
            )
        )
    )

    return items


def archived_task_counts_by_agent():

    agents = load_json(
        AGENTS_FILE,
        {}
    ).get(
        "agents",
        {}
    )

    counts = {}

    for agent_id in agents:

        counts[agent_id] = {
            "completed": 0,
            "failed": 0,
            "cancelled": 0
        }

    for status in ARCHIVE_STATUSES:

        for file in (
            ARCHIVE / status
        ).glob("*.json"):

            data = load_json(
                file,
                {}
            )

            agent = data.get(
                "agent"
            )

            if agent not in counts:

                counts[agent] = {
                    "completed": 0,
                    "failed": 0,
                    "cancelled": 0
                }

            counts[
                agent
            ][status] += 1

    return counts


def task_counts_by_agent():

    agents = load_json(
        AGENTS_FILE,
        {}
    ).get(
        "agents",
        {}
    )

    archived = (
        archived_task_counts_by_agent()
    )

    counts = {}

    for agent_id in agents:

        counts[agent_id] = {
            "pending": 0,
            "running": 0,
            "paused": 0,
            "waiting_credit": 0,
            "completed": archived.get(
                agent_id,
                {}
            ).get(
                "completed",
                0
            ),
            "failed": archived.get(
                agent_id,
                {}
            ).get(
                "failed",
                0
            ),
            "cancelled": archived.get(
                agent_id,
                {}
            ).get(
                "cancelled",
                0
            )
        }

    for task in load_all_tasks():

        agent = task.get(
            "agent"
        )

        status = task.get(
            "status"
        )

        if agent not in counts:

            counts[agent] = {
                key: 0
                for key in TASK_STATUSES
            }

        if status in counts[agent]:

            counts[
                agent
            ][status] += 1

    return counts


def queued_estimate_for_agent(
    agent_id
):

    total = 0

    included = {
        "pending",
        "running",
        "paused",
        "waiting_credit"
    }

    for task in load_all_tasks():

        if (
            task.get("agent")
            == agent_id
            and task.get(
                "status"
            ) in included
        ):

            total += int(
                task.get(
                    "estimated_tokens",
                    0
                )
            )

    return total


def credit_summary():

    budget = load_json(
        CREDIT_FILE,
        {}
    )

    agents = load_json(
        AGENTS_FILE,
        {}
    ).get(
        "agents",
        {}
    )

    result = {}

    for agent_id in agents:

        info = budget.get(
            agent_id,
            {}
        )

        limit_value = int(
            info.get(
                "local_limit",
                0
            )
        )

        used = int(
            info.get(
                "used",
                0
            )
        )

        queued = (
            queued_estimate_for_agent(
                agent_id
            )
        )

        remaining = None
        percent = None

        if limit_value > 0:

            remaining = max(
                0,
                limit_value - used
            )

            percent = round(
                min(
                    100,
                    (
                        used /
                        limit_value
                    ) * 100
                ),
                1
            )

        result[agent_id] = {

            "local_limit":
                limit_value,

            "used":
                used,

            "remaining":
                remaining,

            "used_percent":
                percent,

            "queued_estimate":
                queued,

            "projected_after_queue":
                used + queued
        }

    return result


def find_task(task_id):

    safe_name = Path(
        task_id
    ).name

    for status in TASK_STATUSES:

        path = (
            TASKS /
            status /
            safe_name
        )

        if path.exists():

            return (
                path,
                status
            )

    return (
        None,
        None
    )


@task_locked
def create_task(data):
    project_id = data.get('project') or load_json(PROJECTS_FILE).get('active_project')
    if project_id not in load_json(PROJECTS_FILE).get('projects', {}): return None
    if data.get('agent') not in ('claude_design','chatgpt_code'): return None
    if data.get('smoke_test') and project_id != 'control_center': return None
    request_id = str(data.get('request_id',''))[:100]
    if request_id:
        for existing in load_all_tasks():
            if existing.get('request_id') == request_id and existing.get('agent') == data.get('agent'):
                return existing


    title = str(
        data.get(
            "title",
            ""
        )
    ).strip()

    description = str(
        data.get(
            "description",
            ""
        )
    ).strip()

    agent = str(
        data.get(
            "agent",
            ""
        )
    ).strip()

    priority = str(
        data.get(
            "priority",
            "normal"
        )
    )

    if (
        not title
        or not agent
    ):
        return None

    if priority not in PRIORITY_ORDER:

        priority = "normal"

    projects = load_json(
        PROJECTS_FILE,
        {}
    )

    project = data.get(
        "project"
    ) or projects.get(
        "active_project",
        ""
    )

    workspace = workspace_summary()

    project = (
        data.get("project")
        or workspace.get(
            "active_project"
        )
        or project
    )

    scope = (
        data.get("scope")
        or workspace.get(
            "scope",
            {
                "type": "project",
                "relative_path": ""
            }
        )
    )

    now = datetime.now()

    task_id = (
        now.strftime(
            "%Y%m%d_%H%M%S_%f"
        )
        + ".json"
    )

    estimate = estimate_tokens(
        title,
        description,
        agent
    )

    task = {

        "id": task_id,

        "title": title,

        "description":
            description,

        "agent":
            agent,

        "project":
            project,

        "scope":
            scope,

        "priority":
            priority,

        "status":
            "pending",

        "created_at":
            now.isoformat(),

        "updated_at":
            now.isoformat(),

        "started_at":
            None,

        "finished_at":
            None,

        "estimated_tokens":
            estimate,

        "actual_usage":
            0,

        "credit_saver":
            True
    }

    task['request_id'] = request_id
    task['smoke_test'] = bool(data.get('smoke_test', False))
    task['last_progress'] = 'Queued; manual start required'
    save_json(
        TASKS /
        "pending" /
        task_id,
        task
    )

    return task


@task_locked
def move_task(
    task_id,
    target_status
):

    source, old_status = (
        find_task(
            task_id
        )
    )

    if not source:

        return (
            False,
            "Task not found"
        )

    if (
        target_status
        not in TASK_STATUSES
    ):

        return (
            False,
            "Invalid status"
        )

    if old_status == 'running' and target_status != 'running':
        if target_status != 'cancelled': return False, 'Running tasks must be cancelled, not moved or paused'
        if stop_agent_task(task_id): return True, 'Cancellation requested; waiting for process exit'
        return False, 'Running process is not owned by this server; inspect before recovery'
    if target_status == 'pending' and old_status not in ('paused','waiting_credit','failed','cancelled'):
        return False, 'Task cannot be requeued'
    if old_status == 'completed': return False, 'Completed tasks cannot be rerun; create a new task explicitly'

    data = load_json(
        source,
        {}
    )

    if target_status == 'pending':
        data.update(started_at=None, finished_at=None, duration_seconds=0, error=None,
                    last_progress='Explicit retry queued; manual start required')

    data[
        "status"
    ] = target_status

    data[
        "updated_at"
    ] = datetime.now().isoformat()

    if (
        target_status
        == "running"
        and not data.get(
            "started_at"
        )
    ):

        data[
            "started_at"
        ] = datetime.now().isoformat()

    if target_status in {
        "completed",
        "failed",
        "cancelled"
    }:

        data[
            "finished_at"
        ] = datetime.now().isoformat()

    target = (
        TASKS /
        target_status /
        source.name
    )

    save_json(
        target,
        data
    )

    if source != target:
        source.unlink()

    return (
        True,
        data
    )


def agent_credit_available(
    agent_id,
    estimated
):

    budgets = load_json(
        CREDIT_FILE,
        {}
    )

    info = budgets.get(
        agent_id,
        {}
    )

    limit_value = int(
        info.get(
            "local_limit",
            0
        )
    )

    used = int(
        info.get(
            "used",
            0
        )
    )

    if limit_value <= 0:
        return True

    return (
        used + estimated
        <= limit_value
    )


@task_locked
def dispatch_task(task_id):
    state = load_json(STATE_FILE)
    if EMERGENCY_LOCK.exists() or state.get('emergency_stop'):
        return False, 'Emergency stop active'
    if state.get('system_status') != 'online':
        return False, 'Start the system before dispatch'


    source, status = find_task(
        task_id
    )

    if not source:

        return (
            False,
            "Task not found"
        )

    if status not in {
        "pending",
        "paused"
    }:

        return (
            False,
            "Task cannot start"
        )

    task = load_json(
        source,
        {}
    )

    agent_id = task.get(
        "agent"
    )

    estimated = int(
        task.get(
            "estimated_tokens",
            0
        )
    )

    if not agent_credit_available(
        agent_id,
        estimated
    ):

        move_task(
            task_id,
            "waiting_credit"
        )

        return (
            False,
            "waiting_credit"
        )

    state = normalize_state()

    agent = state.get(
        "agents",
        {}
    ).get(
        agent_id,
        {}
    )

    if not agent.get(
        "enabled",
        False
    ):

        return (
            False,
            "Agent is disabled"
        )

    if agent.get(
        "paused",
        False
    ):

        return (
            False,
            "Agent is paused"
        )

    if not agent.get(
        "accept_new_tasks",
        False
    ):

        return (
            False,
            "Agent is not accepting tasks"
        )

    if (
        agent.get(
            "connection_status"
        )
        == "not_connected"
    ):

        return (
            False,
            "Agent is not connected yet"
        )

    ok, moved = move_task(
        task_id,
        "running"
    )

    if not ok:
        return (
            False,
            moved
        )

    started, worker_result = (
        start_local_task(
            task_id
        )
    )

    if not started:
        # No process started: return to queue without automatic retry or spending.
        path, _ = find_task(task_id)
        queued = load_json(path)
        queued.update(status='pending', started_at=None, last_progress=str(worker_result))
        save_json(TASKS/'pending'/path.name, queued)
        path.unlink(missing_ok=True)

        return (
            False,
            worker_result
        )

    return (
        True,
        {
            "task":
                moved,
            "worker":
                worker_result
        }
    )


def change_agent(
    agent_id,
    action
):

    state = normalize_state()

    agent = state.get(
        "agents",
        {}
    ).get(
        agent_id
    )

    if not agent:

        return (
            False,
            "Unknown agent"
        )

    if action == "start":

        agent[
            "enabled"
        ] = True

        agent[
            "paused"
        ] = False

        agent[
            "accept_new_tasks"
        ] = True

    elif action == "pause":

        agent[
            "paused"
        ] = True

        agent[
            "accept_new_tasks"
        ] = False

    elif action == "stop":

        for item in load_all_tasks():
            if item.get("agent") == agent_id and item["status"] == "running": stop_agent_task(item["file_id"])

        agent[
            "enabled"
        ] = False

        agent[
            "paused"
        ] = False

        agent[
            "accept_new_tasks"
        ] = False

    elif action == "restart":

        agent[
            "enabled"
        ] = True

        agent[
            "paused"
        ] = False

        agent[
            "accept_new_tasks"
        ] = True

    elif action == "block_tasks":

        agent[
            "accept_new_tasks"
        ] = False

    elif action == "allow_tasks":

        if not agent.get(
            "enabled"
        ):

            return (
                False,
                "Agent disabled"
            )

        agent[
            "accept_new_tasks"
        ] = True

    else:

        return (
            False,
            "Invalid action"
        )

    agent[
        "last_action"
    ] = datetime.now().isoformat()

    save_json(
        STATE_FILE,
        state
    )

    return (
        True,
        agent
    )


def change_all_agents(action):

    configs = load_json(
        AGENTS_FILE,
        {}
    ).get(
        "agents",
        {}
    )

    changed = 0

    for agent_id in configs:

        ok, _ = change_agent(
            agent_id,
            action
        )

        if ok:
            changed += 1

    return changed


def archive_status(status):

    if (
        status
        not in ARCHIVE_STATUSES
    ):

        return 0

    source = TASKS / status
    destination = ARCHIVE / status

    count = 0

    for file in list(
        source.glob(
            "*.json"
        )
    ):

        shutil.move(
            str(file),
            str(
                destination /
                file.name
            )
        )

        count += 1

    return count


def credit_returned(
    agent_id=None
):

    budget = load_json(
        CREDIT_FILE,
        {}
    )

    if agent_id:

        ids = [
            agent_id
        ]

    else:

        ids = list(
            budget.keys()
        )

    resumed = 0

    for current_agent in ids:

        if current_agent in budget:

            budget[
                current_agent
            ][
                "used"
            ] = 0

        for file in list(
            (
                TASKS /
                "waiting_credit"
            ).glob(
                "*.json"
            )
        ):

            data = load_json(
                file,
                {}
            )

            if (
                data.get(
                    "agent"
                )
                != current_agent
            ):
                continue

            data[
                "status"
            ] = "pending"

            data[
                "updated_at"
            ] = datetime.now().isoformat()

            target = (
                TASKS /
                "pending" /
                file.name
            )

            save_json(
                target,
                data
            )

            file.unlink()

            resumed += 1

    save_json(
        CREDIT_FILE,
        budget
    )

    return resumed


def set_credit_limit(
    agent_id,
    value
):

    try:
        value = max(
            0,
            int(value)
        )

    except Exception:
        return False

    budgets = load_json(
        CREDIT_FILE,
        {}
    )

    config = budgets.setdefault(
        agent_id,
        {}
    )

    config[
        "local_limit"
    ] = value

    config.setdefault(
        "used",
        0
    )

    config.setdefault(
        "context_reserve",
        4000
    )

    config.setdefault(
        "output_reserve",
        1500
    )

    save_json(
        CREDIT_FILE,
        budgets
    )

    return True


def toggle_setting(setting):

    settings = load_json(
        SETTINGS_FILE,
        {}
    )

    credit = settings.setdefault(
        "credit_saver",
        {}
    )

    local = settings.setdefault(
        "local_first",
        {}
    )

    if setting == "ai_translation":

        value = not credit.get(
            "ai_translation",
            False
        )

        credit[
            "ai_translation"
        ] = value

    elif setting == "ai_screenshot_analysis":

        value = not credit.get(
            "ai_screenshot_analysis",
            False
        )

        credit[
            "ai_screenshot_analysis"
        ] = value

    elif setting == "remote_git_push":

        value = not local.get(
            "remote_git_push",
            False
        )

        local[
            "remote_git_push"
        ] = value

    elif setting == "local_first":

        value = not local.get(
            "enabled",
            True
        )

        local[
            "enabled"
        ] = value

    else:

        return (
            False,
            None
        )

    save_json(
        SETTINGS_FILE,
        settings
    )

    return (
        True,
        value
    )


def approval_list():

    result = []

    for file in sorted(
        PENDING_APPROVALS.glob(
            "*.json"
        )
    ):

        data = load_json(
            file,
            {}
        )

        result.append({
            "id":
                file.name,

            "title":
                data.get(
                    "title",
                    file.stem
                ),

            "agent":
                data.get(
                    "agent",
                    "Unknown"
                ),

            "details":
                data.get(
                    "details",
                    ""
                )
        })

    return result


def move_approval(
    filename,
    approved
):

    safe_name = Path(
        filename
    ).name

    source = (
        PENDING_APPROVALS /
        safe_name
    )

    if not source.exists():
        return False

    destination = (
        APPROVED_APPROVALS
        if approved
        else REJECTED_APPROVALS
    )

    destination.mkdir(
        parents=True,
        exist_ok=True
    )

    shutil.move(
        str(source),
        str(
            destination /
            safe_name
        )
    )

    return True


def move_all_approvals(
    approved
):

    count = 0

    for file in list(
        PENDING_APPROVALS.glob(
            "*.json"
        )
    ):

        if move_approval(
            file.name,
            approved
        ):
            count += 1

    return count


def summary():

    state = normalize_state()

    if EMERGENCY_LOCK.exists():

        state[
            "emergency_stop"
        ] = True

        state[
            "system_status"
        ] = "emergency_stop"

    state[
        "tasks"
    ] = task_counts()

    return {

        "state":
            state,

        "settings":
            load_json(
                SETTINGS_FILE,
                {}
            ),

        "agents":
            load_json(
                AGENTS_FILE,
                {}
            ),

        "projects":
            load_json(
                PROJECTS_FILE,
                {}
            ),

        "tasks":
            load_all_tasks(),

        "task_counts_by_agent":
            task_counts_by_agent(),

        "archive_counts":
            archive_counts(),

        "credits":
            credit_summary(),

        "approvals":
            approval_list(),

        "local_ai":
            local_agent_status(),

        "timestamp":
            datetime.now().isoformat()
    }


class Handler(
    BaseHTTPRequestHandler
):

    def log_message(
        self,
        format,
        *args
    ):
        return


    def send_bytes(
        self,
        data,
        content_type,
        status=200
    ):

        self.send_response(
            status
        )

        self.send_header(
            "Content-Type",
            content_type
        )

        self.send_header(
            "Cache-Control",
            "no-store"
        )

        self.send_header(
            "X-Content-Type-Options",
            "nosniff"
        )

        self.send_header(
            "X-Frame-Options",
            "DENY"
        )

        self.send_header(
            "Referrer-Policy",
            "no-referrer"
        )

        self.send_header(
            "Cross-Origin-Resource-Policy",
            "same-origin"
        )

        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )

        self.end_headers()

        self.wfile.write(
            data
        )


    def send_json(
        self,
        data,
        status=200
    ):

        payload = json.dumps(
            data,
            ensure_ascii=False
        ).encode(
            "utf-8"
        )

        self.send_bytes(
            payload,
            "application/json; charset=utf-8",
            status
        )


    def serve_file(
        self,
        path,
        content_type
    ):

        if not path.exists():

            self.send_json(
                {
                    "error":
                        "Not found"
                },
                404
            )

            return

        self.send_bytes(
            path.read_bytes(),
            content_type
        )


    def body(self):

        length = int(
            self.headers.get(
                "Content-Length",
                "0"
            )
        )

        if length <= 0:
            return {}

        if length > MAX_BODY_BYTES:
            raise ValueError(
                "Request body exceeds 1 MiB limit"
            )

        try:

            return json.loads(
                self.rfile.read(
                    length
                ).decode(
                    "utf-8"
                )
            )

        except Exception:
            return {}


    def do_GET(self):

        if not request_is_local(self):
            self.send_json({"error": "Local access only"}, 403)
            return

        path = urlparse(
            self.path
        ).path

        if path == "/":

            self.serve_file(
                INDEX_FILE,
                "text/html; charset=utf-8"
            )

        elif path == "/static/css/style.css":

            self.serve_file(
                CSS_FILE,
                "text/css; charset=utf-8"
            )

        elif path == "/static/js/app.js":

            self.serve_file(
                JS_FILE,
                "application/javascript; charset=utf-8"
            )

        elif path == '/api/outputs':
            project = parse_qs(urlparse(self.path).query).get('project', [None])[0]
            self.send_json({'outputs': gallery(ROOT, project)})

        elif path.startswith('/api/outputs/file/'):
            try:
                output = resolve_output(ROOT, path.rsplit('/',1)[-1])
                size = output.stat().st_size
                start, end = 0, size-1
                range_header = self.headers.get('Range')
                if range_header:
                    import re
                    match = re.fullmatch(r'bytes=(\d+)-(\d*)', range_header)
                    if not match: raise ValueError('Unsupported range')
                    start = int(match[1]); end = min(int(match[2]) if match[2] else end,end)
                    if start > end: raise ValueError('Range outside file')
                self.send_response(206 if range_header else 200)
                kind = mimetypes.guess_type(output.name)[0] or 'application/octet-stream'
                self.send_header('Content-Type', kind if output.suffix.lower() in ('.png','.jpg','.jpeg','.webp','.mp4','.webm') else 'text/plain; charset=utf-8' if output.suffix.lower() in ('.json','.txt','.md','.log','.csv') else 'application/octet-stream')
                self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Accept-Ranges','bytes')
                self.send_header('Content-Length',str(max(0,end-start+1)))
                if range_header: self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
                self.end_headers()
                with output.open('rb') as stream:
                    stream.seek(start); remaining=end-start+1
                    while remaining>0:
                        chunk=stream.read(min(1024*1024,remaining))
                        if not chunk: break
                        self.wfile.write(chunk); remaining-=len(chunk)
            except (OSError,ValueError) as error:
                self.send_json({'error':str(error)},400)

        elif path == "/api/health":

            self.send_json({
                "ok": True,
                "name": "AI-Control-Center",
                "version": APP_VERSION,
                "local_only": True,
                "timestamp": datetime.now().isoformat()
            })

        elif path == "/api/summary":

            self.send_json(
                summary()
            )

        elif path == "/api/workspace":

            try:
                self.send_json(
                    workspace_summary()
                )

            except Exception as error:

                self.send_json(
                    {
                        "error":
                            str(error)
                    },
                    400
                )


        elif path == "/api/v32/status":

            try:

                self.send_json({
                    "ok":
                        True,

                    "monitor":
                        v32_monitor_status(),

                    "events":
                        v32_recent_events(),

                    "snapshots":
                        v32_snapshot_list()
                })

            except Exception as error:

                self.send_json(
                    {
                        "ok": False,
                        "error": str(error)
                    },
                    400
                )



        elif path == "/api/local-ai/status":

            try:
                self.send_json(
                    local_agent_status(
                        force=True
                    )
                )

            except Exception as error:
                self.send_json(
                    {
                        "connected": False,
                        "model_ready": False,
                        "error": str(error)
                    },
                    500
                )


        else:

            self.send_json(
                {
                    "error":
                        "Not found"
                },
                404
            )


    def do_POST(self):

        path = urlparse(
            self.path
        ).path

        if not request_is_local(self, require_same_origin=True):
            self.send_json({"error": "Local same-origin access only"}, 403)
            return
        try:
            body = self.body()
        except ValueError as error:
            self.send_json({"error": str(error)}, 413)
            return

        if path == '/api/outputs/open':
            try:
                output = resolve_output(ROOT, body.get('id',''))
                if body.get('action') == 'folder': open_local_path(output.parent)
                elif body.get('action') == 'file': open_local_path(output)
                else: raise ValueError('Choose file or folder')
                self.send_json({'ok':True})
            except (OSError, ValueError, AttributeError) as error: self.send_json({'error':str(error)},400)
            return



        # SYSTEM

        if path == "/api/system/start":

            if EMERGENCY_LOCK.exists():

                self.send_json(
                    {
                        "ok": False,
                        "error":
                            "Emergency stop active"
                    },
                    409
                )

                return

            state = normalize_state()

            state[
                "system_status"
            ] = "online"

            save_json(
                STATE_FILE,
                state
            )

            self.send_json(
                {"ok": True}
            )


        elif path == "/api/system/pause":

            state = normalize_state()

            state[
                "system_status"
            ] = "paused"

            save_json(
                STATE_FILE,
                state
            )

            self.send_json(
                {"ok": True}
            )


        elif path == "/api/system/stop":

            stop_agent_task()

            state = normalize_state()

            state[
                "system_status"
            ] = "offline"

            save_json(
                STATE_FILE,
                state
            )

            self.send_json(
                {"ok": True}
            )


        elif path == "/api/system/emergency-stop":

            EMERGENCY_LOCK.write_text(
                datetime.now().isoformat(),
                encoding="utf-8"
            )

            state = normalize_state()

            state[
                "system_status"
            ] = "emergency_stop"

            state[
                "emergency_stop"
            ] = True

            save_json(
                STATE_FILE,
                state
            )

            change_all_agents(
                "stop"
            )

            self.send_json(
                {"ok": True}
            )


        elif path == "/api/system/reset-emergency":

            if EMERGENCY_LOCK.exists():
                EMERGENCY_LOCK.unlink()

            state = normalize_state()

            state[
                "system_status"
            ] = "offline"

            state[
                "emergency_stop"
            ] = False

            save_json(
                STATE_FILE,
                state
            )

            self.send_json(
                {"ok": True}
            )


        # WORKSPACE

        elif path == "/api/workspace/select-project":

            try:

                result = select_project(
                    body.get(
                        "project_id",
                        ""
                    )
                )

                self.send_json({
                    "ok": True,
                    "workspace": result
                })

            except Exception as error:

                self.send_json(
                    {
                        "ok": False,
                        "error": str(error)
                    },
                    400
                )


        elif path == "/api/workspace/browse":

            try:

                result = browse_project(
                    body.get(
                        "path",
                        ""
                    )
                )

                self.send_json({
                    "ok": True,
                    "browser": result
                })

            except Exception as error:

                self.send_json(
                    {
                        "ok": False,
                        "error": str(error)
                    },
                    400
                )


        elif path == "/api/workspace/set-scope":

            try:

                result = set_scope(
                    body.get(
                        "type",
                        "project"
                    ),
                    body.get(
                        "path",
                        ""
                    )
                )

                self.send_json({
                    "ok": True,
                    "scope": result
                })

            except Exception as error:

                self.send_json(
                    {
                        "ok": False,
                        "error": str(error)
                    },
                    400
                )


        elif path == "/api/workspace/add-project":

            try:

                project_id = add_project(
                    body.get(
                        "name",
                        ""
                    ),
                    body.get(
                        "path",
                        ""
                    ),
                    body.get(
                        "main_goal",
                        ""
                    ),
                    body.get(
                        "claude_role",
                        ""
                    ),
                    body.get(
                        "chatgpt_role",
                        ""
                    )
                )

                result = select_project(
                    project_id
                )

                self.send_json({
                    "ok": True,
                    "project_id": project_id,
                    "workspace": result
                })

            except Exception as error:

                self.send_json(
                    {
                        "ok": False,
                        "error": str(error)
                    },
                    400
                )


        elif path == "/api/workspace/update-project":

            try:

                result = update_project(
                    body.get(
                        "main_goal",
                        ""
                    ),
                    body.get(
                        "claude_role",
                        ""
                    ),
                    body.get(
                        "chatgpt_role",
                        ""
                    )
                )

                self.send_json({
                    "ok": True,
                    "project": result
                })

            except Exception as error:

                self.send_json(
                    {
                        "ok": False,
                        "error": str(error)
                    },
                    400
                )


        # SETTINGS

        elif path == "/api/settings/toggle":

            ok, value = toggle_setting(
                body.get(
                    "setting",
                    ""
                )
            )

            self.send_json(
                {
                    "ok": ok,
                    "value": value
                },
                200 if ok else 400
            )


        # CREDIT

        elif path == "/api/credits/set-limit":

            ok = set_credit_limit(
                body.get(
                    "agent",
                    ""
                ),
                body.get(
                    "limit",
                    0
                )
            )

            self.send_json(
                {"ok": ok},
                200 if ok else 400
            )


        elif path == "/api/credits/returned":

            count = credit_returned(
                body.get(
                    "agent"
                )
            )

            self.send_json({
                "ok": True,
                "resumed": count
            })


        # AGENTS

        elif path == "/api/agents/action":

            ok, result = change_agent(
                body.get(
                    "agent"
                ),
                body.get(
                    "action"
                )
            )

            self.send_json(
                {
                    "ok": ok,
                    "result": result
                },
                200 if ok else 400
            )


        elif path == "/api/agents/all":

            count = change_all_agents(
                body.get(
                    "action"
                )
            )

            self.send_json({
                "ok": True,
                "changed": count
            })


        # TASKS

        elif path == "/api/tasks/create":

            selected_agent = body.get(
                "agent",
                ""
            )

            if selected_agent == "both":

                target_agents = [
                    "claude_design",
                    "chatgpt_code"
                ]

            else:

                target_agents = [
                    selected_agent
                ]


            tasks_created = []
            dispatch_results = []


            for agent_id in target_agents:

                task_body = dict(
                    body
                )

                task_body[
                    "agent"
                ] = agent_id


                task = create_task(
                    task_body
                )

                if not task:
                    continue


                tasks_created.append(
                    task
                )


                if body.get(
                    "send_now",
                    False
                ):

                    sent, result = (
                        dispatch_task(
                            task["id"]
                        )
                    )

                    dispatch_results.append({
                        "agent":
                            agent_id,

                        "sent":
                            sent,

                        "result":
                            result
                    })


            if not tasks_created:

                self.send_json(
                    {
                        "ok": False,
                        "error":
                            "Title and agent required"
                    },
                    400
                )

                return


            self.send_json({
                "ok": True,
                "tasks": tasks_created,
                "sent":
                    any(
                        item.get(
                            "sent"
                        )
                        for item
                        in dispatch_results
                    ),
                "dispatch":
                    dispatch_results
            })


        elif path == "/api/tasks/action":

            task_id = body.get(
                "id",
                ""
            )

            action = body.get(
                "action",
                ""
            )

            if action == "start":

                ok, result = dispatch_task(
                    task_id
                )

            elif action == "pause":

                ok, result = move_task(
                    task_id,
                    "paused"
                )

            elif action in ("resume", "retry"):

                ok, result = move_task(
                    task_id,
                    "pending"
                )

            elif action == "wait_credit":

                ok, result = move_task(
                    task_id,
                    "waiting_credit"
                )

            elif action == "cancel":

                ok, result = move_task(
                    task_id,
                    "cancelled"
                )

            else:

                ok = False
                result = (
                    "Invalid action"
                )

            self.send_json(
                {
                    "ok": ok,
                    "result": result
                },
                200 if ok else 409
            )


        # ARCHIVE

        elif path == "/api/archive/status":

            status = body.get(
                "status",
                ""
            )

            count = archive_status(
                status
            )

            self.send_json({
                "ok": True,
                "archived": count
            })


        elif path == "/api/archive/all":

            total = 0

            for status in ARCHIVE_STATUSES:

                total += archive_status(
                    status
                )

            self.send_json({
                "ok": True,
                "archived": total
            })


        # APPROVALS

        elif path == "/api/approvals/approve-all":

            self.send_json({
                "ok": True,
                "moved":
                    move_all_approvals(
                        True
                    )
            })


        elif path == "/api/approvals/reject-all":

            self.send_json({
                "ok": True,
                "moved":
                    move_all_approvals(
                        False
                    )
            })


        elif path == "/api/approvals/approve":

            self.send_json({
                "ok":
                    move_approval(
                        body.get(
                            "id",
                            ""
                        ),
                        True
                    )
            })


        elif path == "/api/approvals/reject":

            self.send_json({
                "ok":
                    move_approval(
                        body.get(
                            "id",
                            ""
                        ),
                        False
                    )
            })



        elif path == "/api/v32/baseline":

            try:

                self.send_json(
                    v32_baseline()
                )

            except Exception as error:

                self.send_json(
                    {
                        "ok": False,
                        "error": str(error)
                    },
                    400
                )


        elif path == "/api/v32/scan":

            try:

                self.send_json(
                    v32_scan()
                )

            except Exception as error:

                self.send_json(
                    {
                        "ok": False,
                        "error": str(error)
                    },
                    400
                )


        elif path == "/api/v32/snapshot/create":

            try:

                result = v32_snapshot_create(
                    body.get(
                        "label",
                        ""
                    )
                )

                self.send_json({
                    "ok": True,
                    "snapshot": result
                })

            except Exception as error:

                self.send_json(
                    {
                        "ok": False,
                        "error": str(error)
                    },
                    400
                )


        elif path == "/api/v32/snapshot/restore":

            try:

                self.send_json(
                    v32_snapshot_restore(
                        body.get(
                            "snapshot_id",
                            ""
                        )
                    )
                )

            except Exception as error:

                self.send_json(
                    {
                        "ok": False,
                        "error": str(error)
                    },
                    400
                )


        elif path == "/api/v32/snapshot/delete":

            try:

                self.send_json(
                    v32_snapshot_delete(
                        body.get(
                            "snapshot_id",
                            ""
                        )
                    )
                )

            except Exception as error:

                self.send_json(
                    {
                        "ok": False,
                        "error": str(error)
                    },
                    400
                )


        else:

            self.send_json(
                {
                    "error":
                        "Not found"
                },
                404
            )


def main():

    settings = load_json(
        SETTINGS_FILE,
        {}
    )

    server_config = settings.get(
        "server",
        {}
    )

    host = os.environ.get(
        "ACC_HOST",
        server_config.get(
            "host",
            "127.0.0.1"
        )
    )

    port = int(
        os.environ.get(
            "ACC_PORT",
            server_config.get(
                "port",
                4177
            )
        )
    )

    if host not in LOOPBACK_HOSTS:
        raise RuntimeError(
            "Refusing non-loopback bind. This public release is localhost-only."
        )

    normalize_state()

    server = ThreadingHTTPServer(
        (
            host,
            port
        ),
        Handler
    )

    url = (
        f"http://{host}:{port}"
    )

    print()
    print("==============================")
    print(f" AI CONTROL CENTER {APP_VERSION}")
    print("==============================")
    print()
    print(f"Dashboard: {url}")
    print("Local Monitoring: ON")
    print("AI Monitoring Calls: 0")
    print("Automatic Reports: OFF")
    print()

    if os.environ.get("ACC_NO_BROWSER") != "1":
        try:
            webbrowser.open(
                url
            )
        except Exception:
            pass

    try:
        server.serve_forever()

    except KeyboardInterrupt:
        print(
            "\nServer stopped."
        )

    finally:
        server.server_close()


if __name__ == "__main__":
    main()

