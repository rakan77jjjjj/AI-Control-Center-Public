import json
import os
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROJECTS_FILE = ROOT / "config" / "projects.json"
WORKSPACE_FILE = ROOT / "runtime" / "workspace_state.json"


def resolve_config_path(value):
    raw = Path(str(value or "")).expanduser()
    if not raw.is_absolute():
        raw = ROOT / raw
    return raw.resolve()


def load_json(path, default=None):
    if default is None:
        default = {}

    try:
        if not path.exists():
            return default

        return json.loads(
            path.read_text(encoding="utf-8-sig")
        )
    except Exception:
        return default


def save_json(path, data):
    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=4
        ),
        encoding="utf-8"
    )


def normalize_registry():
    registry = load_json(
        PROJECTS_FILE,
        {}
    )

    registry.setdefault(
        "active_project",
        "control_center"
    )

    projects = registry.setdefault(
        "projects",
        {}
    )

    if not projects:
        projects["control_center"] = {
            "name": "AI Control Center",
            "path": ".",
            "enabled": True
        }

    for project_id, project in projects.items():

        project.setdefault(
            "enabled",
            True
        )

        project.setdefault(
            "main_goal",
            ""
        )

        project.setdefault(
            "roles",
            {
                "claude_design":
                    "Design, Blender, art and level design",

                "chatgpt_code":
                    "Code, systems, debugging and testing"
            }
        )

        project.setdefault(
            "agents",
            [
                "claude_design",
                "chatgpt_code"
            ]
        )

        project.setdefault(
            "remote_push",
            False
        )

        project.setdefault(
            "backup_enabled",
            True
        )

    save_json(
        PROJECTS_FILE,
        registry
    )

    return registry


def normalize_workspace():
    registry = normalize_registry()

    state = load_json(
        WORKSPACE_FILE,
        {}
    )

    active = state.get(
        "active_project"
    )

    if active not in registry["projects"]:

        active = registry.get(
            "active_project",
            next(iter(registry["projects"]), "control_center")
        )

    state["active_project"] = active

    state.setdefault(
        "scope",
        {
            "type": "project",
            "relative_path": ""
        }
    )

    state.setdefault(
        "browse_path",
        ""
    )

    registry["active_project"] = active

    save_json(
        PROJECTS_FILE,
        registry
    )

    save_json(
        WORKSPACE_FILE,
        state
    )

    return state


def project_root(project_id=None):
    registry = normalize_registry()
    state = normalize_workspace()

    project_id = (
        project_id
        or state["active_project"]
    )

    project = registry["projects"].get(
        project_id
    )

    if not project:
        raise ValueError(
            "Project not found"
        )

    root = resolve_config_path(
        project["path"]
    )

    return (
        project_id,
        project,
        root
    )


def safe_path(relative_path=""):
    project_id, project, root = (
        project_root()
    )

    relative_path = (
        relative_path
        or ""
    ).replace("\\", "/")

    candidate = (
        root / relative_path
    ).resolve()

    try:
        candidate.relative_to(root)
    except ValueError:
        raise ValueError(
            "Path outside project is blocked"
        )

    return (
        project_id,
        project,
        root,
        candidate
    )


def workspace_summary():
    registry = normalize_registry()
    state = normalize_workspace()

    project_id = state[
        "active_project"
    ]

    project = registry[
        "projects"
    ][project_id]

    root = resolve_config_path(
        project["path"]
    )

    return {
        "active_project": project_id,

        "project": project,

        "projects": [
            {
                "id": pid,
                "name": pdata.get(
                    "name",
                    pid
                ),
                "path": pdata.get(
                    "path",
                    ""
                )
            }

            for pid, pdata
            in registry[
                "projects"
            ].items()
        ],

        "root_exists":
            root.exists(),

        "scope":
            state.get(
                "scope",
                {
                    "type": "project",
                    "relative_path": ""
                }
            ),

        "browse_path":
            state.get(
                "browse_path",
                ""
            )
    }


def select_project(project_id):
    registry = normalize_registry()

    if (
        project_id
        not in registry["projects"]
    ):
        raise ValueError(
            "Unknown project"
        )

    registry[
        "active_project"
    ] = project_id

    save_json(
        PROJECTS_FILE,
        registry
    )

    state = {
        "active_project":
            project_id,

        "scope": {
            "type":
                "project",

            "relative_path":
                ""
        },

        "browse_path":
            ""
    }

    save_json(
        WORKSPACE_FILE,
        state
    )

    return workspace_summary()


def browse_project(relative_path=""):
    project_id, project, root, current = (
        safe_path(relative_path)
    )

    if not current.exists():

        raise ValueError(
            "Path does not exist"
        )

    if not current.is_dir():

        current = current.parent

    relative_current = (
        current.relative_to(root)
    )

    relative_current = (
        ""
        if str(relative_current) == "."
        else relative_current.as_posix()
    )

    items = []

    blocked_names = {
        ".git",
        "__pycache__"
    }

    try:

        children = sorted(
            current.iterdir(),
            key=lambda p: (
                not p.is_dir(),
                p.name.lower()
            )
        )

    except PermissionError:

        children = []

    for child in children[:300]:

        if child.name in blocked_names:
            continue

        try:

            rel = child.relative_to(
                root
            ).as_posix()

            item_type = (
                "folder"
                if child.is_dir()
                else "file"
            )

            size = (
                0
                if child.is_dir()
                else child.stat().st_size
            )

            items.append({
                "name":
                    child.name,

                "type":
                    item_type,

                "relative_path":
                    rel,

                "size":
                    size
            })

        except Exception:
            continue

    parent = None

    if current != root:

        parent_path = current.parent

        parent = (
            parent_path
            .relative_to(root)
            .as_posix()
        )

        if parent == ".":
            parent = ""

    state = normalize_workspace()

    state[
        "browse_path"
    ] = relative_current

    save_json(
        WORKSPACE_FILE,
        state
    )

    return {
        "project_id":
            project_id,

        "root":
            str(root),

        "current":
            relative_current,

        "parent":
            parent,

        "items":
            items
    }


def set_scope(
    scope_type,
    relative_path=""
):
    if scope_type not in {
        "project",
        "folder",
        "file"
    }:
        raise ValueError(
            "Invalid scope type"
        )

    state = normalize_workspace()

    if scope_type == "project":

        relative_path = ""

    else:

        _, _, _, target = safe_path(
            relative_path
        )

        if not target.exists():

            raise ValueError(
                "Selected path does not exist"
            )

        if (
            scope_type == "folder"
            and not target.is_dir()
        ):

            raise ValueError(
                "Selected path is not a folder"
            )

        if (
            scope_type == "file"
            and not target.is_file()
        ):

            raise ValueError(
                "Selected path is not a file"
            )

    state["scope"] = {
        "type":
            scope_type,

        "relative_path":
            relative_path
    }

    save_json(
        WORKSPACE_FILE,
        state
    )

    return state["scope"]


def make_project_id(name):
    base = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "_",
        name.strip().lower()
    ).strip("_")

    if not base:

        base = (
            "project_"
            + datetime.now().strftime(
                "%Y%m%d_%H%M%S"
            )
        )

    return base


def add_project(
    name,
    path,
    main_goal="",
    claude_role="",
    chatgpt_role=""
):
    name = str(name).strip()
    path = str(path).strip()

    if not name or not path:

        raise ValueError(
            "Name and path are required"
        )

    root = Path(
        path
    ).expanduser()

    if not root.exists():

        raise ValueError(
            "Project path does not exist"
        )

    if not root.is_dir():

        raise ValueError(
            "Project path must be a folder"
        )

    registry = normalize_registry()

    project_id = make_project_id(
        name
    )

    original = project_id
    counter = 2

    while (
        project_id
        in registry["projects"]
    ):

        project_id = (
            f"{original}_{counter}"
        )

        counter += 1

    registry["projects"][
        project_id
    ] = {

        "name":
            name,

        "path":
            str(root.resolve()),

        "enabled":
            True,

        "main_goal":
            main_goal,

        "roles": {
            "claude_design":
                claude_role
                or "Design and content",

            "chatgpt_code":
                chatgpt_role
                or "Code and testing"
        },

        "agents": [
            "claude_design",
            "chatgpt_code"
        ],

        "remote_push":
            False,

        "backup_enabled":
            True
    }

    save_json(
        PROJECTS_FILE,
        registry
    )

    return project_id


def update_project(
    main_goal,
    claude_role,
    chatgpt_role
):
    registry = normalize_registry()
    state = normalize_workspace()

    project = registry[
        "projects"
    ][state["active_project"]]

    project[
        "main_goal"
    ] = str(
        main_goal
    ).strip()

    project.setdefault(
        "roles",
        {}
    )

    project["roles"][
        "claude_design"
    ] = str(
        claude_role
    ).strip()

    project["roles"][
        "chatgpt_code"
    ] = str(
        chatgpt_role
    ).strip()

    save_json(
        PROJECTS_FILE,
        registry
    )

    return project
