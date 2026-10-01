import json
import os
import re
import shutil
import time
from collections import deque
from datetime import datetime
from pathlib import Path

from workspace import workspace_summary

ROOT = Path(__file__).resolve().parents[1]

CONFIG_FILE = ROOT / "config" / "monitor.json"
MONITOR_STATE = ROOT / "runtime" / "v32_monitor_state.json"
ACTIVITY_FILE = ROOT / "data" / "v32_activity.jsonl"
ACTIVE_CONTEXT = ROOT / "runtime" / "active_task_context.json"
SNAPSHOT_ROOT = ROOT / "backups" / "snapshots"

DEFAULT_CONFIG = {
    "recommended_scan_interval_seconds": 15,
    "max_files_per_scan": 20000,
    "recent_events_limit": 60,
    "excluded_directories": [
        ".git",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        "env",
        "backups",
        "archive",
        "DerivedDataCache",
        "Intermediate",
        "Temp"
    ],
    "excluded_files": [
        ".DS_Store",
        "Thumbs.db"
    ]
}


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


def cfg():
    data = dict(DEFAULT_CONFIG)
    data.update(
        load_json(
            CONFIG_FILE,
            {}
        )
    )
    return data


def active_scope():
    ws = workspace_summary()

    project_id = ws.get(
        "active_project"
    )

    project = ws.get(
        "project",
        {}
    )

    project_root = Path(
        project.get(
            "path",
            ""
        )
    ).expanduser().resolve()

    if not project_root.exists():
        raise ValueError(
            "Active project path does not exist"
        )

    scope = ws.get(
        "scope",
        {
            "type": "project",
            "relative_path": ""
        }
    )

    scope_type = scope.get(
        "type",
        "project"
    )

    relative_path = (
        scope.get(
            "relative_path",
            ""
        )
        or ""
    )

    if scope_type == "project":
        target = project_root
        relative_path = ""
    else:
        target = (
            project_root /
            relative_path
        ).resolve()

    try:
        target.relative_to(
            project_root
        )
    except ValueError:
        raise ValueError(
            "Workspace scope escaped project root"
        )

    if not target.exists():
        raise ValueError(
            "Workspace scope does not exist"
        )

    scope_key = (
        str(project_id)
        + "|"
        + str(scope_type)
        + "|"
        + str(relative_path)
    )

    return {
        "project_id":
            project_id,

        "project_name":
            project.get(
                "name",
                project_id
            ),

        "project_root":
            project_root,

        "scope_type":
            scope_type,

        "relative_path":
            relative_path,

        "target":
            target,

        "scope_key":
            scope_key
    }


def file_iterator(
    project_root,
    target
):
    config = cfg()

    excluded_dirs = set(
        config.get(
            "excluded_directories",
            []
        )
    )

    excluded_files = set(
        config.get(
            "excluded_files",
            []
        )
    )

    if target.is_file():

        if target.name not in excluded_files:
            yield target

        return

    for current_root, dirs, files in os.walk(
        target
    ):
        dirs[:] = [
            d
            for d in dirs
            if d not in excluded_dirs
        ]

        current = Path(
            current_root
        )

        for filename in files:

            if filename in excluded_files:
                continue

            path = current / filename

            try:
                path.relative_to(
                    project_root
                )
            except ValueError:
                continue

            yield path


def build_manifest():
    info = active_scope()
    config = cfg()

    max_files = int(
        config.get(
            "max_files_per_scan",
            20000
        )
    )

    records = {}
    truncated = False

    for path in file_iterator(
        info["project_root"],
        info["target"]
    ):
        try:
            stat = path.stat()

            relative = path.relative_to(
                info["project_root"]
            ).as_posix()

            records[
                relative
            ] = {
                "size":
                    stat.st_size,

                "mtime_ns":
                    stat.st_mtime_ns
            }

        except (
            OSError,
            PermissionError
        ):
            continue

        if len(records) >= max_files:
            truncated = True
            break

    return (
        info,
        records,
        truncated
    )


def current_context():
    data = load_json(
        ACTIVE_CONTEXT,
        {}
    )

    return {
        "agent":
            data.get(
                "agent",
                "local"
            ),

        "task_id":
            data.get(
                "task_id"
            ),

        "task_title":
            data.get(
                "task_title"
            )
    }


def append_events(events):
    if not events:
        return

    ACTIVITY_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with ACTIVITY_FILE.open(
        "a",
        encoding="utf-8"
    ) as file:

        for event in events:

            file.write(
                json.dumps(
                    event,
                    ensure_ascii=False
                )
                + "\n"
            )


def baseline():
    started = time.perf_counter()

    info, records, truncated = (
        build_manifest()
    )

    duration_ms = round(
        (
            time.perf_counter()
            - started
        ) * 1000,
        2
    )

    state = {
        "scope_key":
            info["scope_key"],

        "project_id":
            info["project_id"],

        "scope_type":
            info["scope_type"],

        "relative_path":
            info["relative_path"],

        "files":
            records,

        "watched_files":
            len(records),

        "truncated":
            truncated,

        "last_scan":
            datetime.now().isoformat(),

        "last_scan_duration_ms":
            duration_ms,

        "last_change_counts": {
            "created": 0,
            "modified": 0,
            "deleted": 0
        }
    }

    save_json(
        MONITOR_STATE,
        state
    )

    return {
        "ok":
            True,

        "baseline_created":
            True,

        "watched_files":
            len(records),

        "truncated":
            truncated,

        "duration_ms":
            duration_ms
    }


def scan():
    started = time.perf_counter()

    info, current, truncated = (
        build_manifest()
    )

    old_state = load_json(
        MONITOR_STATE,
        {}
    )

    if (
        not old_state
        or old_state.get(
            "scope_key"
        ) != info["scope_key"]
    ):
        result = baseline()
        result[
            "baseline_reset"
        ] = True
        result[
            "reason"
        ] = "Workspace scope changed"
        return result

    previous = old_state.get(
        "files",
        {}
    )

    previous_keys = set(
        previous.keys()
    )

    current_keys = set(
        current.keys()
    )

    created = sorted(
        current_keys
        - previous_keys
    )

    deleted = sorted(
        previous_keys
        - current_keys
    )

    modified = []

    for path in sorted(
        current_keys
        & previous_keys
    ):
        before = previous[
            path
        ]

        after = current[
            path
        ]

        if (
            before.get(
                "size"
            )
            != after.get(
                "size"
            )
            or before.get(
                "mtime_ns"
            )
            != after.get(
                "mtime_ns"
            )
        ):
            modified.append(
                path
            )

    now = datetime.now().isoformat()
    context = current_context()
    events = []

    for kind, paths in [
        (
            "created",
            created
        ),
        (
            "modified",
            modified
        ),
        (
            "deleted",
            deleted
        )
    ]:
        for path in paths:
            events.append(
                {
                    "timestamp":
                        now,

                    "type":
                        kind,

                    "path":
                        path,

                    "project_id":
                        info[
                            "project_id"
                        ],

                    "agent":
                        context.get(
                            "agent",
                            "local"
                        ),

                    "task_id":
                        context.get(
                            "task_id"
                        ),

                    "task_title":
                        context.get(
                            "task_title"
                        )
                }
            )

    append_events(
        events
    )

    duration_ms = round(
        (
            time.perf_counter()
            - started
        ) * 1000,
        2
    )

    state = {
        "scope_key":
            info["scope_key"],

        "project_id":
            info["project_id"],

        "scope_type":
            info["scope_type"],

        "relative_path":
            info["relative_path"],

        "files":
            current,

        "watched_files":
            len(current),

        "truncated":
            truncated,

        "last_scan":
            now,

        "last_scan_duration_ms":
            duration_ms,

        "last_change_counts": {
            "created":
                len(created),

            "modified":
                len(modified),

            "deleted":
                len(deleted)
        }
    }

    save_json(
        MONITOR_STATE,
        state
    )

    return {
        "ok":
            True,

        "baseline_reset":
            False,

        "watched_files":
            len(current),

        "truncated":
            truncated,

        "created":
            created,

        "modified":
            modified,

        "deleted":
            deleted,

        "change_counts":
            state[
                "last_change_counts"
            ],

        "duration_ms":
            duration_ms
    }


def recent_events(limit=None):
    if limit is None:
        limit = int(
            cfg().get(
                "recent_events_limit",
                60
            )
        )

    if not ACTIVITY_FILE.exists():
        return []

    lines = deque(
        maxlen=max(
            1,
            int(limit)
        )
    )

    try:
        with ACTIVITY_FILE.open(
            "r",
            encoding="utf-8"
        ) as file:

            for line in file:
                line = line.strip()

                if line:
                    lines.append(
                        line
                    )
    except Exception:
        return []

    result = []

    for line in reversed(
        lines
    ):
        try:
            result.append(
                json.loads(
                    line
                )
            )
        except Exception:
            continue

    return result


def monitor_status():
    state = load_json(
        MONITOR_STATE,
        {}
    )

    try:
        info = active_scope()

        scope = {
            "project_id":
                info[
                    "project_id"
                ],

            "project_name":
                info[
                    "project_name"
                ],

            "scope_type":
                info[
                    "scope_type"
                ],

            "relative_path":
                info[
                    "relative_path"
                ],

            "target":
                str(
                    info[
                        "target"
                    ]
                )
        }

    except Exception as error:
        scope = {
            "error":
                str(error)
        }

    config = cfg()

    return {
        "initialized":
            bool(state),

        "watched_files":
            state.get(
                "watched_files",
                0
            ),

        "truncated":
            state.get(
                "truncated",
                False
            ),

        "last_scan":
            state.get(
                "last_scan"
            ),

        "last_scan_duration_ms":
            state.get(
                "last_scan_duration_ms"
            ),

        "last_change_counts":
            state.get(
                "last_change_counts",
                {
                    "created": 0,
                    "modified": 0,
                    "deleted": 0
                }
            ),

        "current_scope":
            scope,

        "config": {
            "recommended_scan_interval_seconds":
                config.get(
                    "recommended_scan_interval_seconds",
                    15
                ),

            "max_files_per_scan":
                config.get(
                    "max_files_per_scan",
                    20000
                )
        }
    }


def sanitize(text):
    value = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "_",
        str(text)
    ).strip("_")

    return value[:50]


def snapshot_create_for(
    project_id,
    project_name,
    project_root,
    scope_type,
    relative_path,
    target,
    label=""
):
    SNAPSHOT_ROOT.mkdir(
        parents=True,
        exist_ok=True
    )

    now = datetime.now()

    snapshot_id = now.strftime(
        "%Y%m%d_%H%M%S"
    )

    clean_label = sanitize(
        label
    )

    if clean_label:
        snapshot_id += (
            "_"
            + clean_label
        )

    base_id = snapshot_id
    counter = 2

    while (
        SNAPSHOT_ROOT /
        snapshot_id
    ).exists():

        snapshot_id = (
            base_id
            + "_"
            + str(counter)
        )

        counter += 1

    folder = (
        SNAPSHOT_ROOT /
        snapshot_id
    )

    content = (
        folder /
        "content"
    )

    content.mkdir(
        parents=True,
        exist_ok=False
    )

    file_count = 0
    total_size = 0
    files = []

    try:
        for source in file_iterator(
            project_root,
            target
        ):
            try:
                relative = (
                    source.relative_to(
                        project_root
                    )
                )

                destination = (
                    content /
                    relative
                )

                destination.parent.mkdir(
                    parents=True,
                    exist_ok=True
                )

                shutil.copy2(
                    source,
                    destination
                )

                size = (
                    source.stat().st_size
                )

                file_count += 1
                total_size += size

                files.append(
                    relative.as_posix()
                )

            except (
                OSError,
                PermissionError
            ):
                continue

        manifest = {
            "snapshot_id":
                snapshot_id,

            "created_at":
                now.isoformat(),

            "label":
                label,

            "project_id":
                project_id,

            "project_name":
                project_name,

            "project_path":
                str(
                    project_root
                ),

            "scope_type":
                scope_type,

            "relative_path":
                relative_path,

            "file_count":
                file_count,

            "total_size":
                total_size,

            "files":
                files,

            "restore_mode":
                "safe_overlay"
        }

        save_json(
            folder /
            "manifest.json",
            manifest
        )

        return manifest

    except Exception:
        shutil.rmtree(
            folder,
            ignore_errors=True
        )
        raise


def snapshot_create(label=""):
    info = active_scope()

    return snapshot_create_for(
        info[
            "project_id"
        ],
        info[
            "project_name"
        ],
        info[
            "project_root"
        ],
        info[
            "scope_type"
        ],
        info[
            "relative_path"
        ],
        info[
            "target"
        ],
        label
    )


def snapshot_list():
    SNAPSHOT_ROOT.mkdir(
        parents=True,
        exist_ok=True
    )

    result = []

    for folder in sorted(
        SNAPSHOT_ROOT.iterdir(),
        key=lambda p: p.name,
        reverse=True
    ):
        if not folder.is_dir():
            continue

        manifest = load_json(
            folder /
            "manifest.json",
            {}
        )

        if manifest:
            result.append(
                manifest
            )

    return result


def snapshot_info(snapshot_id):
    safe_id = Path(
        snapshot_id
    ).name

    folder = (
        SNAPSHOT_ROOT /
        safe_id
    )

    manifest = load_json(
        folder /
        "manifest.json",
        {}
    )

    if not manifest:
        raise ValueError(
            "Snapshot not found"
        )

    content = (
        folder /
        "content"
    )

    if not content.exists():
        raise ValueError(
            "Snapshot content missing"
        )

    return (
        folder,
        content,
        manifest
    )


def snapshot_restore(snapshot_id):
    folder, content, manifest = (
        snapshot_info(
            snapshot_id
        )
    )

    project_root = Path(
        manifest.get(
            "project_path",
            ""
        )
    ).expanduser().resolve()

    if not project_root.exists():
        raise ValueError(
            "Original project path no longer exists"
        )

    relative_path = (
        manifest.get(
            "relative_path",
            ""
        )
        or ""
    )

    scope_type = manifest.get(
        "scope_type",
        "project"
    )

    if scope_type == "project":
        current_target = project_root
    else:
        current_target = (
            project_root /
            relative_path
        ).resolve()

    try:
        current_target.relative_to(
            project_root
        )
    except ValueError:
        raise ValueError(
            "Restore target escaped project root"
        )

    safety_snapshot = None

    if current_target.exists():
        safety = snapshot_create_for(
            manifest.get(
                "project_id"
            ),
            manifest.get(
                "project_name"
            ),
            project_root,
            scope_type,
            relative_path,
            current_target,
            (
                "auto_before_restore_"
                + snapshot_id
            )
        )

        safety_snapshot = safety.get(
            "snapshot_id"
        )

    restored = 0

    content_root = content.resolve()

    for relative_text in manifest.get(
        "files",
        []
    ):
        relative = Path(
            relative_text
        )

        source = (
            content /
            relative
        ).resolve()

        destination = (
            project_root /
            relative
        ).resolve()

        try:
            source.relative_to(
                content_root
            )

            destination.relative_to(
                project_root
            )
        except ValueError:
            continue

        if not source.is_file():
            continue

        destination.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        shutil.copy2(
            source,
            destination
        )

        restored += 1

    return {
        "ok":
            True,

        "snapshot_id":
            snapshot_id,

        "restored_files":
            restored,

        "safety_snapshot":
            safety_snapshot,

        "restore_mode":
            "safe_overlay"
    }


def snapshot_delete(snapshot_id):
    folder, content, manifest = (
        snapshot_info(
            snapshot_id
        )
    )

    shutil.rmtree(
        folder
    )

    return {
        "ok":
            True,

        "deleted":
            snapshot_id
    }
