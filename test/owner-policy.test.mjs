import assert from "node:assert/strict";
import test from "node:test";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
    authorizeOwnerAction,
    loadOwnerPolicy,
    publicOwnerPolicy
} from "../app/server/owner-policy.mjs";

const __filename = fileURLToPath(import.meta.url);
const ROOT = path.resolve(path.dirname(__filename), "..");
const policy = loadOwnerPolicy(ROOT);

test("owner policy is deeply frozen", () => {
    assert.equal(Object.isFrozen(policy), true);
    assert.equal(Object.isFrozen(policy.defaults), true);
    assert.equal(Object.isFrozen(policy.agentForbidden), true);
});

test("read-only actions are allowed without approval", () => {
    assert.deepEqual(
        authorizeOwnerAction(policy, { actor: "agent", action: "git.status" }),
        { allowed: true, reason: "READ_ONLY_ALLOWED" }
    );
});

test("writes fail closed without owner approval", () => {
    assert.deepEqual(
        authorizeOwnerAction(policy, { actor: "agent", action: "filesystem.write" }),
        { allowed: false, reason: "OWNER_APPROVAL_REQUIRED" }
    );
});

test("owner approval unlocks approval-gated actions", () => {
    assert.deepEqual(
        authorizeOwnerAction(policy, {
            actor: "agent",
            action: "git.commit",
            ownerApproved: true
        }),
        { allowed: true, reason: "OWNER_APPROVED" }
    );
});

test("agent forbidden actions remain denied", () => {
    assert.deepEqual(
        authorizeOwnerAction(policy, {
            actor: "agent",
            action: "git.forcePush",
            ownerApproved: true
        }),
        { allowed: false, reason: "AGENT_FORBIDDEN" }
    );
});

test("unknown actions are denied by default", () => {
    assert.deepEqual(
        authorizeOwnerAction(policy, { actor: "agent", action: "unknown.action" }),
        { allowed: false, reason: "DENY_BY_DEFAULT" }
    );
});

test("public policy does not expose mutable internals", () => {
    const pub = publicOwnerPolicy(policy);
    assert.equal(pub.ownerAuthority, "FINAL");
    assert.equal(pub.failClosed, true);
    assert.equal(pub.linkedProjectsReadOnly, true);
    assert.ok(pub.counts.ownerApprovalRequired > 0);
});
