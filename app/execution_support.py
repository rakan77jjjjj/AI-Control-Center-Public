"""Local execution utilities. Artifact records reference originals, never copy media."""
import hashlib
import json
import os
import re
import subprocess
import threading
import uuid
from datetime import datetime
from pathlib import Path

TASK_LOCK = threading.RLock()
EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.mp4', '.webm', '.blend', '.glb', '.gltf', '.json', '.txt', '.md', '.log', '.pdf', '.csv'}
SKIP = {'.git', 'node_modules', '__pycache__', '.venv', 'backups', 'credentials', 'secrets'}

def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)

def redact(text):
    text = str(text)
    for key, value in os.environ.items():
        if re.search(r'(TOKEN|SECRET|PASSWORD|API_KEY|CREDENTIAL)', key, re.I) and len(value) >= 6:
            text = text.replace(value, '[REDACTED]')
    text = re.sub(r'(?i)(bearer\s+)[^\s"\']+', r'\1[REDACTED]', text)
    text = re.sub(r'(?i)((?:api[_-]?key|access[_-]?token|password|secret)["\']?\s*[:=]\s*["\']?)[^\s,"\'}]+', r'\1[REDACTED]', text)
    return re.sub(r'\bsk-[A-Za-z0-9_-]{12,}', '[REDACTED]', text)

def inventory(root):
    root = Path(root).resolve()
    result = {}
    for folder, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith('.') and not (Path(folder)/d).is_symlink()]
        for name in files:
            p = Path(folder)/name
            if p.suffix.lower() not in EXTENSIONS or name.startswith('.') or p.is_symlink():
                continue
            try:
                resolved = p.resolve()
                if not resolved.is_relative_to(root): continue
                stat = p.stat()
                result[str(resolved)] = (stat.st_size, stat.st_mtime_ns)
            except OSError:
                continue
    return result

def record_outputs(task, workspace, before, output_dir):
    after = inventory(workspace)
    changed = [Path(p) for p, signature in after.items() if before.get(p) != signature]
    changed += [p for p in output_dir.iterdir() if p.suffix in EXTENSIONS and p.name != 'artifacts.json']
    rows = []
    for path in dict.fromkeys(changed):
        stat = path.stat()
        rows.append(dict(id=hashlib.sha256((str(output_dir)+str(path)).encode()).hexdigest(),
            filename=path.name, path=str(path.resolve()), type=path.suffix.lower().lstrip('.'),
            size=stat.st_size, timestamp=datetime.fromtimestamp(stat.st_mtime).isoformat(),
            agent=task['agent'], task=task['id'], task_title=task['title'], project=task['project'],
            workspace=str(Path(workspace).resolve()), attribution='changed during task; external edits may overlap'))
    atomic_json(output_dir/'artifacts.json', rows)
    return rows

def gallery(root, project=None):
    rows = []
    for record in (root/'data/agent_outputs').glob('*/attempt-*/artifacts.json'):
        try: rows.extend(json.loads(record.read_text(encoding='utf-8')))
        except (OSError, ValueError): pass
    return sorted([r for r in rows if not project or r['project'] == project], key=lambda r: r['timestamp'], reverse=True)

def resolve_output(root, output_id):
    row = next((r for r in gallery(root) if r['id'] == output_id), None)
    if not row: raise ValueError('Output not found')
    path = Path(row['path']).resolve(strict=True)
    workspace = Path(row['workspace']).resolve()
    registry = json.loads((root/'config/projects.json').read_text(encoding='utf-8-sig'))
    project = registry.get('projects', {}).get(row['project'], {})
    def resolve_configured(value):
        p = Path(value).expanduser()
        if not p.is_absolute():
            p = root / p
        return p.resolve()

    allowed = [resolve_configured(project['path'])] if project.get('path') else []
    allowed += [resolve_configured(v['path']) for v in project.get('agent_workspaces', {}).values() if v.get('path')]
    trusted_workspace = any(workspace.is_relative_to(p) for p in allowed)
    if not (path.is_relative_to((root/'data/agent_outputs').resolve()) or (trusted_workspace and path.is_relative_to(workspace))):
        raise ValueError('Output path is outside its configured project')
    if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
        raise ValueError('Unsupported output file')
    return path

def kill_tree(process):
    if process.poll() is not None: return
    if os.name == 'nt':
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, timeout=15)
    else:
        process.kill()
