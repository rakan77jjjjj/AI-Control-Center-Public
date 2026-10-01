import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { loadOwnerPolicy, publicOwnerPolicy } from "./owner-policy.mjs";

const execFileAsync = promisify(execFile);

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const ROOT = path.resolve(__dirname, "../..");
const UI_DIR = path.join(ROOT, "app", "ui");
const OWNER_POLICY = loadOwnerPolicy(ROOT);

const PORT = 4177;
const HOST = "127.0.0.1";

const activity = [];
const clients = new Set();
const recentEvents = new Map();


function readText(relativePath) {
    try {
        return fs
            .readFileSync(path.join(ROOT, relativePath), "utf8")
            .replace(/^\uFEFF/, "");
    } catch {
        return "";
    }
}


function readJson(relativePath, fallback = {}) {
    try {
        return JSON.parse(readText(relativePath));
    } catch {
        return fallback;
    }
}


function shouldIgnoreFile(filename) {
    const normalized = filename
        .replaceAll("\\", "/")
        .toLowerCase();

    if (
        normalized === ".git" ||
        normalized.startsWith(".git/") ||
        normalized.includes("/.git/")
    ) {
        return true;
    }

    if (
        normalized === "node_modules" ||
        normalized.startsWith("node_modules/") ||
        normalized.includes("/node_modules/")
    ) {
        return true;
    }

    if (
        normalized.endsWith(".tmp") ||
        normalized.endsWith("~")
    ) {
        return true;
    }

    return false;
}


function isDuplicateEvent(type, message) {
    const key = `${type}:${message}`;
    const now = Date.now();

    const previous = recentEvents.get(key);

    if (previous && now - previous < 1000) {
        return true;
    }

    recentEvents.set(key, now);

    for (const [eventKey, timestamp] of recentEvents) {
        if (now - timestamp > 5000) {
            recentEvents.delete(eventKey);
        }
    }

    return false;
}


function addActivity(type, message) {
    if (isDuplicateEvent(type, message)) {
        return;
    }

    const item = {
        time: new Date().toISOString(),
        type,
        message
    };

    activity.unshift(item);

    if (activity.length > 100) {
        activity.length = 100;
    }

    const payload = `data: ${JSON.stringify(item)}\n\n`;

    for (const client of clients) {
        client.write(payload);
    }
}


async function gitInfo(projectPath) {
    if (!projectPath || !fs.existsSync(projectPath)) {
        return {
            available: false,
            branch: "—",
            clean: false,
            output: "Project path not found."
        };
    }

    try {
        const branchResult = await execFileAsync(
            "git",
            [
                "-C",
                projectPath,
                "branch",
                "--show-current"
            ],
            {
                windowsHide: true
            }
        );

        const statusResult = await execFileAsync(
            "git",
            [
                "-C",
                projectPath,
                "status",
                "--short",
                "--branch"
            ],
            {
                windowsHide: true
            }
        );

        const porcelainResult = await execFileAsync(
            "git",
            [
                "-C",
                projectPath,
                "status",
                "--porcelain"
            ],
            {
                windowsHide: true
            }
        );

        return {
            available: true,
            branch: branchResult.stdout.trim() || "unknown",
            clean: porcelainResult.stdout.trim().length === 0,
            output: statusResult.stdout.trim()
        };
    } catch (error) {
        return {
            available: false,
            branch: "—",
            clean: false,
            output: error.message
        };
    }
}


async function buildState() {
    const project = readJson(
        "config/project.json",
        {}
    );

    const tasks = readJson(
        "tasks/tasks.json",
        []
    );

    const projectExists =
        Boolean(project.path) &&
        fs.existsSync(project.path);

    const git = await gitInfo(project.path);

    return {
        controlCenter: {
            version: "0.2.0-owner-security",
            mode: "LOCAL",
            agentAutomation: false
        },

        ownerPolicy: publicOwnerPolicy(OWNER_POLICY),

        project: {
            ...project,
            exists: projectExists
        },

        git,

        currentSession: tasks[0] ?? null,

        tasks,

        reports: {
            claude: readText(
                "reports/claude/CLAUDE_REPORT.md"
            ),

            code: readText(
                "reports/code/CODE_REPORT.md"
            )
        },

        docs: {
            projectControl: readText(
                "project/PROJECT_CONTROL.md"
            ),

            milestones: readText(
                "project/MILESTONES.md"
            ),

            roadmap: readText(
                "project/ROADMAP.md"
            )
        },

        activity
    };
}


function json(res, data, status = 200) {
    const body = JSON.stringify(
        data,
        null,
        2
    );

    res.writeHead(status, {
        "Content-Type":
            "application/json; charset=utf-8",

        "Cache-Control":
            "no-store"
    });

    res.end(body);
}


function staticFile(
    res,
    filename,
    contentType
) {
    const target = path.join(
        UI_DIR,
        filename
    );

    if (!fs.existsSync(target)) {
        res.writeHead(404);
        res.end("Not found");
        return;
    }

    res.writeHead(200, {
        "Content-Type": contentType,
        "Cache-Control": "no-store"
    });

    fs.createReadStream(target).pipe(res);
}


const server = http.createServer(
    async (req, res) => {
        const url = new URL(
            req.url,
            `http://${req.headers.host}`
        );

        if (url.pathname === "/api/state") {
            return json(
                res,
                await buildState()
            );
        }

        if (url.pathname === "/events") {
            res.writeHead(200, {
                "Content-Type":
                    "text/event-stream",

                "Cache-Control":
                    "no-cache",

                "Connection":
                    "keep-alive"
            });

            res.write(": connected\n\n");

            clients.add(res);

            req.on("close", () => {
                clients.delete(res);
            });

            return;
        }

        if (url.pathname === "/") {
            return staticFile(
                res,
                "index.html",
                "text/html; charset=utf-8"
            );
        }

        if (url.pathname === "/app.js") {
            return staticFile(
                res,
                "app.js",
                "text/javascript; charset=utf-8"
            );
        }

        if (url.pathname === "/styles.css") {
            return staticFile(
                res,
                "styles.css",
                "text/css; charset=utf-8"
            );
        }

        res.writeHead(404);
        res.end("Not found");
    }
);


function startProjectWatcher() {
    const project = readJson(
        "config/project.json",
        {}
    );

    if (
        !project.path ||
        !fs.existsSync(project.path)
    ) {
        addActivity(
            "ERROR",
            `Linked project path not found: ${
                project.path ?? "undefined"
            }`
        );

        return;
    }

    try {
        const watcher = fs.watch(
            project.path,
            {
                recursive: true
            },

            (eventType, filename) => {
                if (!filename) {
                    return;
                }

                const file = String(filename);

                if (shouldIgnoreFile(file)) {
                    return;
                }

                addActivity(
                    "FILE_CHANGED",
                    `${eventType}: ${file}`
                );
            }
        );

        watcher.on(
            "error",
            error => {
                addActivity(
                    "ERROR",
                    `Watcher error: ${error.message}`
                );
            }
        );

        addActivity(
            "WATCHING",
            `Read-only monitoring started: ${project.path}`
        );
    } catch (error) {
        addActivity(
            "ERROR",
            `Could not start watcher: ${error.message}`
        );
    }
}


server.listen(
    PORT,
    HOST,
    () => {
        addActivity(
            "SERVER_STARTED",
            `Control Center v0.1 running at http://${HOST}:${PORT}`
        );

        startProjectWatcher();

        console.log("");
        console.log("AI Control Center v0.1");
        console.log("----------------------");
        console.log(
            `Dashboard: http://${HOST}:${PORT}`
        );
        console.log("Mode: LOCAL");
        console.log("Agent automation: OFF");
        console.log("Linked project writes: OFF");
        console.log("Owner authority: FINAL / fail-closed");
        console.log("");
    }
);