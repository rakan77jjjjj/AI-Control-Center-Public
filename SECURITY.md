# Security

AI Control Center is designed as a **local-first supervised tool**.

## Public release security defaults

- The HTTP server is restricted to loopback only: `127.0.0.1`, `localhost`, or `::1`.
- The public release does not provide a bypass for remote binding.
- HTTP Host and state-changing request Origin values are restricted to loopback to reduce browser/DNS-rebinding exposure.
- Agent subprocesses receive an allowlisted environment instead of inheriting unrelated credentials such as GitHub or cloud-provider tokens.
- CI scans tracked files and Git commit metadata for personal paths, secrets, sensitive runtime files, and non-private commit email addresses.
- Unknown policy actions are denied.
- Automatic Git push and automatic merge are disabled.
- Agent workspaces are explicit and project-scoped.
- Runtime state, logs, outputs, approvals, backups, personal memory, datasets, models, checkpoints, and local databases must not be committed.
- Agent command execution uses argument lists rather than shell command strings where supported.
- Project path handling is expected to remain within configured workspace roots.

## Secrets

Never commit API keys, tokens, cookies, CLI session files, private keys, `.env` files, personal memory, or local databases.

Provider authentication should stay in the provider's normal local credential store or environment variables. Public source files must contain placeholders or non-secret defaults only.

## Network exposure

Do **not** expose the dashboard directly to the public internet.

The current public release intentionally refuses non-loopback binding. Remote access, if added in a future version, must have authentication, authorization, encrypted transport, revocation, auditing, rate limits, and explicit owner opt-in before it is considered safe for release.

## Security review before releases

Before publishing an installer or release asset:

1. Scan the full source and Git history for secrets and personal paths.
2. Verify the installer contains no user memory, logs, datasets, models, credentials, or private project files.
3. Test workspace/path traversal boundaries.
4. Test approval enforcement and action routing.
5. Test that network listeners remain local-only.
6. Verify downloads and update artifacts before execution.
7. Re-test on a clean Windows machine.

## Reporting a problem

Do not post secrets, exploit details, private logs, or personal data in a public issue. Contact the repository owner privately for sensitive security reports.
