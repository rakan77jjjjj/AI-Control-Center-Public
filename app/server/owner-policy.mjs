import fs from "node:fs";
import path from "node:path";

function deepFreeze(value) {
    if (!value || typeof value !== "object" || Object.isFrozen(value)) {
        return value;
    }

    Object.freeze(value);

    for (const item of Object.values(value)) {
        deepFreeze(item);
    }

    return value;
}

function requireStringArray(policy, key) {
    if (!Array.isArray(policy[key]) || policy[key].some(item => typeof item !== "string")) {
        throw new Error(`Invalid owner policy: ${key} must be an array of strings.`);
    }
}

function validatePolicy(policy) {
    if (!policy || typeof policy !== "object") {
        throw new Error("Invalid owner policy: expected an object.");
    }

    if (policy.schemaVersion !== 1) {
        throw new Error("Invalid owner policy: unsupported schemaVersion.");
    }

    if (policy?.owner?.authority !== "FINAL") {
        throw new Error("Invalid owner policy: owner authority must be FINAL.");
    }

    if (policy?.defaults?.decision !== "DENY" || policy?.defaults?.failClosed !== true) {
        throw new Error("Invalid owner policy: deny-by-default and fail-closed are required.");
    }

    if (policy?.defaults?.agentMayModifyPolicy !== false || policy?.defaults?.agentMayGrantOwnApproval !== false) {
        throw new Error("Invalid owner policy: agents cannot modify policy or self-approve.");
    }

    for (const key of ["allowedWithoutApproval", "ownerApprovalRequired", "agentForbidden", "protectedBranches"]) {
        requireStringArray(policy, key);
    }

    if (policy?.projectDetach?.deletesProjectFiles !== false) {
        throw new Error("Invalid owner policy: detaching a project must not delete project files.");
    }

    return policy;
}

export function loadOwnerPolicy(root) {
    const policyPath = path.join(root, "config", "owner-rules.json");
    const raw = fs.readFileSync(policyPath, "utf8").replace(/^\uFEFF/, "");
    const policy = validatePolicy(JSON.parse(raw));
    return deepFreeze(policy);
}

export function authorizeOwnerAction(policy, request = {}) {
    const action = String(request.action ?? "");
    const actor = String(request.actor ?? "agent");
    const ownerApproved = request.ownerApproved === true;

    if (!action) {
        return { allowed: false, reason: "MISSING_ACTION" };
    }

    if (policy.agentForbidden.includes(action)) {
        return { allowed: false, reason: "AGENT_FORBIDDEN" };
    }

    if (actor !== "owner" && action === "ownerPolicy.modify") {
        return { allowed: false, reason: "OWNER_POLICY_IMMUTABLE_TO_AGENT" };
    }

    if (policy.allowedWithoutApproval.includes(action)) {
        return { allowed: true, reason: "READ_ONLY_ALLOWED" };
    }

    if (policy.ownerApprovalRequired.includes(action)) {
        if (actor === "owner" || ownerApproved) {
            return { allowed: true, reason: "OWNER_APPROVED" };
        }

        return { allowed: false, reason: "OWNER_APPROVAL_REQUIRED" };
    }

    return { allowed: false, reason: "DENY_BY_DEFAULT" };
}

export function publicOwnerPolicy(policy) {
    return {
        schemaVersion: policy.schemaVersion,
        ownerAuthority: policy.owner.authority,
        failClosed: policy.defaults.failClosed,
        linkedProjectsReadOnly: policy.defaults.linkedProjectsReadOnly,
        conflictRule: policy.conflictRule,
        protectedBranches: [...policy.protectedBranches],
        counts: {
            readOnlyAllowed: policy.allowedWithoutApproval.length,
            ownerApprovalRequired: policy.ownerApprovalRequired.length,
            agentForbidden: policy.agentForbidden.length
        }
    };
}
