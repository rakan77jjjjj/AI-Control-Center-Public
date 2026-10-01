# Architecture

## Components

### `app/server.py`
Primary local HTTP server and dashboard API. It owns system state, task queue transitions, approvals and the user-facing dashboard.

### `app/real_agents.py`
Supervised bridge to provider CLIs. It resolves an agent workspace, constructs a restricted command, launches one task at a time, captures output and records task results.

### `app/workspace.py`
Project registry, project selection, path-boundary validation and file browsing.

### `app/local_tools.py`
Local monitoring, baselines, snapshots and recovery helpers.

### `app/execution_support.py`
Atomic file writes, output inventory, redaction and process-tree termination helpers.

### `app/provider_connections.py`
Optional provider connectivity checks using environment variables. Credentials are never written to repository files.

### `app/server/owner-policy.mjs`
Fail-closed owner policy used by the JavaScript compatibility layer and policy tests.

## Execution flow

1. Owner creates a task in the dashboard.
2. Task remains queued until explicitly started.
3. System and emergency-stop state are checked.
4. Agent workspace and provider CLI are resolved.
5. A global execution lease prevents concurrent write agents.
6. Prompt is delivered through stdin.
7. Stdout/stderr are captured and redacted.
8. Output files are inventoried.
9. Task ends as completed, failed, cancelled or waiting for credit.
10. Automatic retry is disabled.
