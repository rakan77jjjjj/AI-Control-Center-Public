from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SENSITIVE_PREFIXES = (
    "runtime/",
    "approvals/",
    "archive/",
    "backups/",
    "data/",
    "manager/logs/",
    "manager/tasks/",
    "manager/memory/",
    "tasks/",
    "datasets/",
    "dataset/",
    "models/",
    "checkpoints/",
    "adapters/",
    "training-env/",
    ".venv-training/",
    "credentials/",
    "secrets/",
)

SENSITIVE_SUFFIXES = (
    ".env",
    ".key",
    ".pem",
    ".p12",
    ".pfx",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".log",
)

PATTERNS = (
    ("Windows user path", re.compile(r"[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/][^\\/\r\n]+", re.I)),
    ("private key", re.compile(r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY", re.I)),
    ("OpenAI-style secret", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("Anthropic-style secret", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("email address", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
)

ALLOWED_EMAIL_DOMAINS = {"users.noreply.github.com"}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [
        ROOT / item.decode("utf-8", errors="strict")
        for item in result.stdout.split(b"\0")
        if item
    ]


def is_sensitive_path(relative: str) -> bool:
    normalized = relative.replace("\\", "/")
    lower = normalized.lower()

    if any(lower.startswith(prefix.lower()) for prefix in SENSITIVE_PREFIXES):
        return True

    name = Path(lower).name
    if name == ".env" or name.startswith(".env."):
        return True

    return any(lower.endswith(suffix) for suffix in SENSITIVE_SUFFIXES)


def commit_metadata_problems() -> list[str]:
    result = subprocess.run(
        ["git", "log", "--format=%H%x00%an%x00%ae%x00%cn%x00%ce"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    problems: list[str] = []

    for line in result.stdout.splitlines():
        parts = line.split("\x00")
        if len(parts) != 5:
            continue

        sha, author_name, author_email, committer_name, committer_email = parts

        for role, name, email in (
            ("author", author_name, author_email),
            ("committer", committer_name, committer_email),
        ):
            domain = email.rsplit("@", 1)[-1].lower() if "@" in email else ""
            if domain not in ALLOWED_EMAIL_DOMAINS:
                problems.append(
                    f"{sha[:12]}: {role} email is not privacy-safe"
                )

            if name.lower() not in {"rakan77jjjjj", "github-actions[bot]"}:
                problems.append(
                    f"{sha[:12]}: unexpected {role} name"
                )

    return problems


def main() -> int:
    problems: list[str] = []
    problems.extend(commit_metadata_problems())

    for path in tracked_files():
        relative = path.relative_to(ROOT).as_posix()

        if is_sensitive_path(relative):
            problems.append(f"{relative}: sensitive path/file must not be tracked")
            continue

        try:
            raw = path.read_bytes()
        except OSError as error:
            problems.append(f"{relative}: cannot read: {error}")
            continue

        if b"\x00" in raw[:8192]:
            continue

        text = raw.decode("utf-8", errors="ignore")

        for label, pattern in PATTERNS:
            for match in pattern.finditer(text):
                value = match.group(0)

                if label == "email address":
                    domain = value.rsplit("@", 1)[-1].lower()
                    if domain in ALLOWED_EMAIL_DOMAINS:
                        continue

                line = text.count("\n", 0, match.start()) + 1
                problems.append(f"{relative}:{line}: possible {label}")

    if problems:
        print("Security scan FAILED:")
        for problem in sorted(set(problems)):
            print(f" - {problem}")
        return 1

    print("Security scan passed: no tracked personal paths, secrets, or sensitive runtime files detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
