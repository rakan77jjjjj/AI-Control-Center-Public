let dashboardData = null;


const T = {

    online: "قيد التشغيل",
    offline: "متوقف",
    paused: "متوقف مؤقتًا",
    emergency_stop: "إيقاف طوارئ",

    safe: "آمن",
    balanced: "متوازن",
    autonomous: "ذاتي",

    not_connected: "غير متصل",

    pending: "بانتظار",
    running: "تعمل",
    waiting_credit: "بانتظار الكريدت",
    completed: "مكتملة",
    failed: "فشلت",
    cancelled: "ملغاة",

    design_manager: "مدير التصميم",
    coding_agent: "وكيل البرمجة",

    critical: "حرجة",
    high: "عالية",
    normal: "عادية",
    low: "منخفضة"
};


function tr(value) {
    return T[value] || value || "غير معروف";
}


function escapeHtml(value) {

    const div =
        document.createElement("div");

    div.textContent =
        value || "";

    return div.innerHTML;
}


function inlineArg(value) {
    return encodeURIComponent(
        String(value ?? "")
    ).replace(/'/g, "%27");
}


async function api(
    url,
    options = {}
) {

    const response =
        await fetch(
            url,
            options
        );

    const data =
        await response.json();

    if (!response.ok) {

        throw new Error(
            data.error ||
            data.result ||
            "Request failed"
        );
    }

    return data;
}


function toast(message) {

    const element =
        document.getElementById(
            "toast"
        );

    element.textContent =
        message;

    element.classList.add(
        "show"
    );

    setTimeout(
        () => {
            element.classList.remove(
                "show"
            );
        },
        2600
    );
}


async function loadDashboard() {

    try {

        dashboardData =
            await api(
                "/api/summary"
            );

        renderSummary();
        renderProtection();
        renderAgents();
        renderTasks();
        renderExecutionProjects();
        await loadOutputs();
        renderApprovals();
        updateTaskEstimate();
        await loadWorkspace();

    }
    catch (error) {

        console.error(error);

        document.getElementById(
            "systemStatus"
        ).textContent =
            "تعذر الاتصال";
    }
}


function renderSummary() {

    const state =
        dashboardData.state || {};

    const settings =
        dashboardData.settings || {};

    const projects =
        dashboardData.projects || {};

    const projectId =
        projects.active_project;

    const project =
        (
            projects.projects || {}
        )[projectId] || {};


    document.getElementById(
        "projectName"
    ).textContent =
        project.name ||
        projectId ||
        "-";


    const status =
        state.system_status ||
        "offline";


    document.getElementById(
        "systemStatus"
    ).textContent =
        tr(status);


    const dot =
        document.getElementById(
            "systemDot"
        );

    dot.className = "dot";

    if (status === "online") {
        dot.classList.add("online");
    }

    if (status === "paused") {
        dot.classList.add("paused");
    }

    if (
        status ===
        "emergency_stop"
    ) {
        dot.classList.add(
            "emergency"
        );
    }


    document.getElementById(
        "operationMode"
    ).textContent =
        tr(
            settings.operation_mode ||
            "safe"
        );


    const tasks =
        state.tasks || {};

    document.getElementById(
        "pendingTasks"
    ).textContent =
        tasks.pending || 0;

    document.getElementById(
        "runningTasks"
    ).textContent =
        tasks.running || 0;

    document.getElementById(
        "pausedTasks"
    ).textContent =
        tasks.paused || 0;

    document.getElementById(
        "creditTasks"
    ).textContent =
        tasks.waiting_credit || 0;

    document.getElementById(
        "failedTasks"
    ).textContent =
        tasks.failed || 0;


    const archive =
        dashboardData.archive_counts ||
        {};

    document.getElementById(
        "archiveCompleted"
    ).textContent =
        archive.completed || 0;

    document.getElementById(
        "archiveFailed"
    ).textContent =
        archive.failed || 0;

    document.getElementById(
        "archiveCancelled"
    ).textContent =
        archive.cancelled || 0;
}


function setToggleButton(
    id,
    enabled,
    onText,
    offText
) {

    const button =
        document.getElementById(id);

    if (!button) {
        return;
    }

    button.textContent =
        enabled
            ? onText
            : offText;

    button.className =
        enabled
            ? "toggle-button toggle-on"
            : "toggle-button toggle-off";
}


function renderProtection() {

    const settings =
        dashboardData.settings || {};

    const credit =
        settings.credit_saver || {};

    const local =
        settings.local_first || {};


    setToggleButton(
        "aiTranslationButton",
        credit.ai_translation === true,
        "مفعلة",
        "مغلقة"
    );

    setToggleButton(
        "imageAnalysisButton",
        credit.ai_screenshot_analysis === true,
        "مفعل",
        "مغلق"
    );

    setToggleButton(
        "remotePushButton",
        local.remote_git_push === true,
        "مفعل",
        "مغلق"
    );

    setToggleButton(
        "localFirstButton",
        local.enabled !== false,
        "مفعل",
        "مغلق"
    );
}


function renderAgents() {

    const configs =
        (
            dashboardData.agents || {}
        ).agents || {};

    const runtime =
        (
            dashboardData.state || {}
        ).agents || {};

    const counts =
        dashboardData.task_counts_by_agent ||
        {};

    const credits =
        dashboardData.credits ||
        {};

    const container =
        document.getElementById(
            "agentsContainer"
        );

    const selector =
        document.getElementById(
            "taskAgent"
        );

    const currentSelection =
        selector.value;

    container.innerHTML = "";
    selector.innerHTML = "";


    for (
        const [id, config]
        of Object.entries(configs)
    ) {

        const state =
            runtime[id] || {};

        const taskCounts =
            counts[id] || {};

        const credit =
            credits[id] || {};

        const option =
            document.createElement(
                "option"
            );

        option.value = id;

        option.textContent =
            `${config.display_name} — ${tr(config.role)}`;

        selector.appendChild(
            option
        );


        const limit =
            credit.local_limit || 0;

        const used =
            credit.used || 0;

        const remaining =
            credit.remaining;

        const percent =
            credit.used_percent;

        const queued =
            credit.queued_estimate || 0;


        const percentText =
            percent === null ||
            percent === undefined
                ? "غير محدد"
                : `${percent}%`;


        const remainingText =
            remaining === null ||
            remaining === undefined
                ? "غير محدد"
                : remaining.toLocaleString();


        const card =
            document.createElement(
                "div"
            );

        card.className =
            "agent-card";


        card.innerHTML = `

            <div class="agent-head">

                <div>

                    <div class="agent-name">
                        ${escapeHtml(config.display_name)}
                    </div>

                    <div class="agent-role">
                        ${tr(config.role)}
                    </div>

                </div>

                <span class="badge">
                    ${tr(
                        state.connection_status ||
                        "not_connected"
                    )}
                </span>

            </div>


            <div class="agent-task-stats">

                <div>
                    <strong>${taskCounts.pending || 0}</strong>
                    <span>بانتظار</span>
                </div>

                <div>
                    <strong>${taskCounts.running || 0}</strong>
                    <span>تعمل</span>
                </div>

                <div>
                    <strong>${taskCounts.paused || 0}</strong>
                    <span>متوقفة</span>
                </div>

                <div>
                    <strong>${taskCounts.waiting_credit || 0}</strong>
                    <span>تنتظر كريدت</span>
                </div>

                <div>
                    <strong>${taskCounts.completed || 0}</strong>
                    <span>مكتملة</span>
                </div>

                <div>
                    <strong>${taskCounts.failed || 0}</strong>
                    <span>فشلت</span>
                </div>

            </div>


            <div class="credit-box">

                <div class="credit-row">

                    <span>
                        العداد المحلي
                    </span>

                    <strong>
                        ${percentText}
                    </strong>

                </div>


                <div class="progress">

                    <div
                        class="progress-bar"
                        style="width:${percent || 0}%"
                    ></div>

                </div>


                <div class="credit-row">

                    <span>
                        المستخدم المسجل
                    </span>

                    <strong>
                        ${used.toLocaleString()}
                    </strong>

                </div>


                <div class="credit-row">

                    <span>
                        المتبقي
                    </span>

                    <strong>
                        ${remainingText}
                    </strong>

                </div>


                <div class="credit-row">

                    <span>
                        تقدير المهام الموجودة
                    </span>

                    <strong>
                        ~${queued.toLocaleString()}
                    </strong>

                </div>


                <div class="limit-row">

                    <input
                        id="limit-${id}"
                        type="number"
                        min="0"
                        value="${limit}"
                        placeholder="الحد المحلي"
                    >

                    <button
                        class="btn secondary small"
                        onclick="setCreditLimit('${id}')"
                    >
                        حفظ الحد
                    </button>

                </div>

                <div class="task-meta">
                    هذا عداد محلي تقديري وليس رصيد المزود الحقيقي.
                </div>

            </div>


            <div class="actions">

                <button
                    class="btn success small"
                    onclick="agentAction('${id}', 'start')"
                >
                    تشغيل
                </button>

                <button
                    class="btn warning small"
                    onclick="agentAction('${id}', 'pause')"
                >
                    مؤقت
                </button>

                <button
                    class="btn danger small"
                    onclick="agentAction('${id}', 'stop')"
                >
                    إيقاف
                </button>

                <button
                    class="btn outline small"
                    onclick="agentAction(
                        '${id}',
                        '${state.accept_new_tasks ? "block_tasks" : "allow_tasks"}'
                    )"
                >
                    ${
                        state.accept_new_tasks
                            ? "منع مهام جديدة"
                            : "السماح بالمهام"
                    }
                </button>

                <button
                    class="btn credit small"
                    onclick="creditReturned('${id}')"
                >
                    ⚠ الكريدت رجع — استكمال
                </button>

            </div>
        `;

        container.appendChild(
            card
        );
    }


    if (
        [...selector.options].some(
            option =>
                option.value ===
                currentSelection
        )
    ) {

        selector.value =
            currentSelection;
    }
}


function renderTasks() {

    const tasks =
        dashboardData.tasks || [];

    const agents =
        (
            dashboardData.agents || {}
        ).agents || {};

    const container =
        document.getElementById(
            "tasksContainer"
        );

    container.innerHTML = "";


    if (!tasks.length) {

        container.innerHTML = `
            <div class="empty">
                لا توجد مهام حاليًا
            </div>
        `;

        return;
    }


    for (const task of tasks) {

        const agent =
            agents[task.agent];

        const agentName =
            agent
                ? agent.display_name
                : task.agent;


        const row =
            document.createElement(
                "div"
            );

        row.className =
            `task task-${task.priority}`;


        let controls = "";


        if (task.status === "pending") {

            controls = `

                <button
                    class="btn credit small"
                    onclick="taskAction('${task.file_id}', 'start')"
                >
                    ⚠ إرسال / تشغيل
                </button>

                <button
                    class="btn warning small"
                    onclick="taskAction('${task.file_id}', 'pause')"
                >
                    إيقاف مؤقت
                </button>

                <button
                    class="btn secondary small"
                    onclick="taskAction('${task.file_id}', 'wait_credit')"
                >
                    انتظار الكريدت
                </button>

                <button
                    class="btn danger small"
                    onclick="taskAction('${task.file_id}', 'cancel')"
                >
                    إلغاء
                </button>
            `;
        }


        if (task.status === "paused") {

            controls = `

                <button
                    class="btn success small"
                    onclick="taskAction('${task.file_id}', 'resume')"
                >
                    استكمال للصف
                </button>

                <button
                    class="btn danger small"
                    onclick="taskAction('${task.file_id}', 'cancel')"
                >
                    إلغاء
                </button>
            `;
        }


        if (
            task.status ===
            "waiting_credit"
        ) {

            controls = `
                <span class="warn">
                    محفوظة حتى عودة الكريدت
                </span>
            `;
        }


        if (task.status === 'running') controls = `<button class="btn danger small" onclick="taskAction('${task.file_id}', 'cancel')">Cancel execution</button>`;
        if (['failed','cancelled','waiting_credit'].includes(task.status)) controls += `<button class="btn secondary small" onclick="taskAction('${task.file_id}', 'retry')">Retry: queue only</button>`;
        row.innerHTML = `

            <div class="task-top">

                <div>

                    <div class="task-title">
                        ${escapeHtml(task.title)}
                    </div>

                    <div class="task-meta">

                        الوكيل:
                        ${escapeHtml(agentName)}

                        &nbsp; | &nbsp;

                        الحالة:
                        ${escapeHtml(task.status_label || tr(task.status))}

                        &nbsp; | &nbsp;

                        الأولوية:
                        ${tr(task.priority)}

                    </div>

                    <div class="task-meta">

                        الاستهلاك المتوقع:
                        ~${Number(
                            task.estimated_tokens || 0
                        ).toLocaleString()}

                    </div>

                </div>


                <div class="actions">
                    ${controls}
                </div>

            </div>


            <div class="task-meta" dir="ltr">Project: ${escapeHtml(task.project)} · Start: ${escapeHtml(task.started_at || '—')} · Duration: ${Number(task.duration_seconds || 0).toFixed(1)}s · Exit: ${task.exit_code ?? '—'}</div>
            <div class="task-meta" dir="ltr">${escapeHtml(task.last_progress || task.error || 'Queued')}</div>
            ${task.result_preview ? `<details><summary>Completed output</summary><pre class="output-text">${escapeHtml(task.result_preview)}</pre></details>` : ''}
            ${
                task.description
                    ? `
                        <div class="task-meta">
                            ${escapeHtml(task.description)}
                        </div>
                    `
                    : ""
            }
        `;

        container.appendChild(
            row
        );
    }
}


function renderApprovals() {

    const items =
        dashboardData.approvals || [];

    const container =
        document.getElementById(
            "approvalsContainer"
        );

    container.innerHTML = "";


    if (!items.length) {

        container.innerHTML = `
            <div class="empty">
                لا توجد موافقات معلقة حاليًا
            </div>
        `;

        return;
    }


    for (const item of items) {

        const row =
            document.createElement(
                "div"
            );

        row.className =
            "approval";


        row.innerHTML = `

            <div>

                <strong>
                    ${escapeHtml(item.title)}
                </strong>

                <div class="task-meta">
                    ${escapeHtml(item.agent)}
                </div>

            </div>


            <div class="actions">

                <button
                    class="btn success small"
                    onclick="approvalOne(
                        '${inlineArg(item.id)}',
                        true
                    )"
                >
                    قبول
                </button>

                <button
                    class="btn danger small"
                    onclick="approvalOne(
                        '${inlineArg(item.id)}',
                        false
                    )"
                >
                    رفض
                </button>

            </div>
        `;

        container.appendChild(
            row
        );
    }
}


function updateTaskEstimate() {

    if (!dashboardData) {
        return;
    }

    const title =
        document.getElementById(
            "taskTitle"
        )?.value || "";

    const description =
        document.getElementById(
            "taskDescription"
        )?.value || "";

    const agent =
        document.getElementById(
            "taskAgent"
        )?.value;

    const output =
        document.getElementById(
            "taskEstimate"
        );

    if (
        !output ||
        !agent
    ) {
        return;
    }


    const credits =
        dashboardData.credits || {};

    const agentCredit =
        credits[agent] || {};

    const textTokens =
        Math.max(
            1,
            Math.ceil(
                (
                    title.length +
                    description.length
                ) / 4
            )
        );


    const currentQueued =
        Number(
            agentCredit.queued_estimate ||
            0
        );


    const approximate =
        textTokens + 6500;


    let extra = "";

    if (
        agentCredit.local_limit > 0
    ) {

        const limit =
            agentCredit.local_limit;

        const percent =
            (
                approximate /
                limit
            ) * 100;

        extra =
            ` — تقريبًا ${percent.toFixed(1)}% من الحد المحلي`;
    }


    output.textContent =
        `استهلاك المهمة المتوقع: ~${approximate.toLocaleString()} وحدة${extra}. ` +
        `هذا تقدير محلي وليس فاتورة فعلية.`;
}


function toggleTaskForm() {

    document.getElementById(
        "taskForm"
    ).classList.toggle(
        "hidden"
    );

    updateTaskEstimate();
}


let creatingTask = false;
let requestId = null;
async function createTask(sendNow) {
    if (creatingTask) return;
    const title = document.getElementById('taskTitle').value.trim();
    if (!title) return toast('اكتب اسم المهمة');
    if (sendNow && !confirm('Send one task to the selected agent? This may use credit. No automatic retry.')) return;
    creatingTask = true;
    requestId ||= crypto.randomUUID();
    try {
        const result = await api('/api/tasks/create', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({
            title, description:document.getElementById('taskDescription').value.trim(),
            agent:document.getElementById('taskAgent').value, project:document.getElementById('taskProject').value,
            priority:document.getElementById('taskPriority').value, send_now:sendNow, request_id:requestId
        }) });
        requestId = null;
        document.getElementById('taskTitle').value=''; document.getElementById('taskDescription').value='';
        toggleTaskForm();
        toast(result.sent ? 'Task dispatched once' : 'Task queued. Start explicitly when ready.');
        await loadDashboard();
    } catch (error) { toast(error.message); }
    finally { creatingTask = false; }
}


async function setCreditLimit(
    agent
) {

    const value =
        document.getElementById(
            `limit-${agent}`
        ).value;


    await api(
        "/api/credits/set-limit",
        {
            method: "POST",

            headers: {
                "Content-Type":
                    "application/json"
            },

            body:
                JSON.stringify({
                    agent,
                    limit: value
                })
        }
    );


    toast(
        "تم حفظ الحد المحلي"
    );

    await loadDashboard();
}


async function creditReturned(
    agent
) {

    const name =
        agent
            ? (
                (
                    dashboardData.agents ||
                    {}
                ).agents?.[agent]
                    ?.display_name ||
                agent
            )
            : "جميع الوكلاء";


    const confirmed =
        confirm(
            `تأكيد أن الكريدت عاد لـ ${name}؟\n\n` +
            "سيتم تصفير العداد المحلي للدورة السابقة، " +
            "وإعادة المهام المنتظرة إلى قائمة التنفيذ."
        );


    if (!confirmed) {
        return;
    }


    const result =
        await api(
            "/api/credits/returned",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body:
                    JSON.stringify({
                        agent
                    })
            }
        );


    toast(
        `تمت إعادة ${result.resumed || 0} مهمة للصف`
    );

    await loadDashboard();
}


async function toggleProtection(
    setting
) {

    if (
        setting ===
        "remote_git_push"
    ) {

        const current =
            (
                dashboardData.settings
                    .local_first ||
                {}
            ).remote_git_push === true;


        if (!current) {

            if (
                !confirm(
                    "تشغيل السماح بالرفع البعيد؟\n\nلن يتم رفع شيء الآن."
                )
            ) {
                return;
            }
        }
    }


    await api(
        "/api/settings/toggle",
        {
            method: "POST",

            headers: {
                "Content-Type":
                    "application/json"
            },

            body:
                JSON.stringify({
                    setting
                })
        }
    );


    toast(
        "تم حفظ الإعداد محليًا"
    );

    await loadDashboard();
}


async function agentAction(
    agent,
    action
) {

    try {

        await api(
            "/api/agents/action",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body:
                    JSON.stringify({
                        agent,
                        action
                    })
            }
        );

        toast(
            "تم تنفيذ أمر الوكيل"
        );

        await loadDashboard();

    }
    catch (error) {

        toast(
            error.message
        );
    }
}


async function allAgents(
    action
) {

    await api(
        "/api/agents/all",
        {
            method: "POST",

            headers: {
                "Content-Type":
                    "application/json"
            },

            body:
                JSON.stringify({
                    action
                })
        }
    );


    toast(
        "تم تنفيذ الأمر على الجميع"
    );

    await loadDashboard();
}


async function taskAction(
    id,
    action
) {

    if (action === "start") {

        const confirmed =
            confirm(
                "تشغيل هذه المهمة قد يستهلك كريدت بعد ربط الوكيل.\n\nمتابعة؟"
            );

        if (!confirmed) {
            return;
        }
    }


    try {

        const result =
            await api(
                "/api/tasks/action",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify({
                            id,
                            action
                        })
                }
            );


        toast(
            "تم تحديث المهمة"
        );

        await loadDashboard();

    }
    catch (error) {

        if (
            error.message ===
            "waiting_credit"
        ) {

            toast(
                "تم حفظ المهمة بانتظار عودة الكريدت"
            );

            await loadDashboard();

            return;
        }


        if (
            error.message.includes(
                "not connected"
            )
        ) {

            toast(
                "المهمة محفوظة — الوكيل غير مربوط بعد"
            );

            return;
        }


        toast(
            error.message
        );
    }
}


async function archiveStatus(
    status
) {

    const result =
        await api(
            "/api/archive/status",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body:
                    JSON.stringify({
                        status
                    })
            }
        );


    toast(
        `تمت أرشفة ${result.archived || 0} مهمة`
    );

    await loadDashboard();
}


async function archiveAll() {

    const result =
        await api(
            "/api/archive/all",
            {
                method: "POST"
            }
        );


    toast(
        `تمت أرشفة ${result.archived || 0} مهمة`
    );

    await loadDashboard();
}


async function systemAction(
    action
) {

    try {

        await api(
            `/api/system/${action}`,
            {
                method: "POST"
            }
        );

        toast(
            "تم تنفيذ الأمر"
        );

        await loadDashboard();

    }
    catch (error) {

        toast(
            error.message
        );
    }
}


async function emergencyStop() {

    if (
        !confirm(
            "إيقاف كل النظام والوكلاء فورًا؟"
        )
    ) {
        return;
    }

    await api(
        "/api/system/emergency-stop",
        {
            method: "POST"
        }
    );

    toast(
        "تم تفعيل إيقاف الطوارئ"
    );

    await loadDashboard();
}


async function resetEmergency() {

    await api(
        "/api/system/reset-emergency",
        {
            method: "POST"
        }
    );

    toast(
        "تم فك قفل الطوارئ"
    );

    await loadDashboard();
}


async function approvalAll(
    approved
) {

    const endpoint =
        approved
            ? "approve-all"
            : "reject-all";


    await api(
        `/api/approvals/${endpoint}`,
        {
            method: "POST"
        }
    );

    await loadDashboard();
}


async function approvalOne(
    encodedId,
    approved
) {

    const endpoint =
        approved
            ? "approve"
            : "reject";


    await api(
        `/api/approvals/${endpoint}`,
        {
            method: "POST",

            headers: {
                "Content-Type":
                    "application/json"
            },

            body:
                JSON.stringify({
                    id:
                        decodeURIComponent(
                            encodedId
                        )
                })
        }
    );

    await loadDashboard();
}


document.addEventListener(
    "input",
    event => {

        if (
            event.target.id === "taskTitle" ||
            event.target.id === "taskDescription" ||
            event.target.id === "taskAgent"
        ) {

            updateTaskEstimate();
        }
    }
);




let currentWorkspace = null;
let workspaceBrowser = null;
let selectedWorkspacePath = "";


async function loadWorkspace() {

    try {

        currentWorkspace =
            await api(
                "/api/workspace"
            );

        renderWorkspace();

        await browseWorkspace(
            currentWorkspace.browse_path || ""
        );

        ensureBothAgentOption();

    }
    catch (error) {

        console.error(
            "Workspace:",
            error
        );
    }
}


function renderWorkspace() {

    if (!currentWorkspace) {
        return;
    }

    const selector =
        document.getElementById(
            "workspaceProject"
        );

    if (!selector) {
        return;
    }

    const oldValue =
        selector.value;

    selector.innerHTML = "";


    for (
        const project
        of currentWorkspace.projects
    ) {

        const option =
            document.createElement(
                "option"
            );

        option.value =
            project.id;

        option.textContent =
            project.name;

        selector.appendChild(
            option
        );
    }


    selector.value =
        currentWorkspace.active_project;


    const project =
        currentWorkspace.project || {};


    document.getElementById(
        "workspaceRoot"
    ).textContent =
        project.path || "-";


    document.getElementById(
        "workspaceGoal"
    ).value =
        project.main_goal || "";


    const roles =
        project.roles || {};


    document.getElementById(
        "workspaceClaudeRole"
    ).value =
        roles.claude_design || "";


    document.getElementById(
        "workspaceChatGPTRole"
    ).value =
        roles.chatgpt_code || "";


    const scope =
        currentWorkspace.scope || {
            type: "project",
            relative_path: ""
        };


    const scopeText =
        scope.type === "project"
            ? "المشروع كامل"
            : scope.relative_path;


    document.getElementById(
        "workspaceCurrentScope"
    ).textContent =
        scopeText || "المشروع كامل";


    document.getElementById(
        "workspaceScopeType"
    ).value =
        scope.type || "project";


    selectedWorkspacePath =
        scope.relative_path || "";


    document.getElementById(
        "workspaceSelectedPath"
    ).textContent =
        selectedWorkspacePath ||
        "المشروع كامل";
}


function ensureBothAgentOption() {

    const selector =
        document.getElementById(
            "taskAgent"
        );

    if (!selector) {
        return;
    }

    if (
        ![...selector.options]
            .some(
                option =>
                    option.value === "both"
            )
    ) {

        const option =
            document.createElement(
                "option"
            );

        option.value = "both";

        option.textContent =
            "Claude + ChatGPT — كلاهما";

        selector.appendChild(
            option
        );
    }
}


async function selectWorkspaceProject() {

    const projectId =
        document.getElementById(
            "workspaceProject"
        ).value;


    await api(
        "/api/workspace/select-project",
        {
            method: "POST",

            headers: {
                "Content-Type":
                    "application/json"
            },

            body:
                JSON.stringify({
                    project_id:
                        projectId
                })
        }
    );


    selectedWorkspacePath = "";

    toast(
        "تم تغيير المشروع"
    );

    await loadWorkspace();
    await loadDashboard();
}


async function browseWorkspace(path="") {

    try {

        const result =
            await api(
                "/api/workspace/browse",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify({
                            path
                        })
                }
            );


        workspaceBrowser =
            result.browser;


        document.getElementById(
            "workspaceBrowsePath"
        ).textContent =
            workspaceBrowser.current ||
            "/";


        const parentButton =
            document.getElementById(
                "workspaceParentButton"
            );


        parentButton.disabled =
            workspaceBrowser.parent === null;


        renderWorkspaceItems();

    }
    catch (error) {

        toast(
            error.message
        );
    }
}


function renderWorkspaceItems() {

    const container =
        document.getElementById(
            "workspaceItems"
        );

    container.innerHTML = "";


    const items =
        workspaceBrowser?.items || [];


    if (!items.length) {

        container.innerHTML = `
            <div class="empty">
                هذا المجلد فارغ
            </div>
        `;

        return;
    }


    for (const item of items) {

        const row =
            document.createElement(
                "div"
            );

        row.className =
            "file-row";


        const icon =
            item.type === "folder"
                ? "📁"
                : "📄";


        let buttons = "";


        if (item.type === "folder") {

            buttons += `
                <button
                    class="btn secondary small"
                    onclick="browseWorkspace(
                        '${inlineArg(item.relative_path)}'
                    )"
                >
                    فتح
                </button>
            `;
        }


        buttons += `
            <button
                class="btn outline small"
                onclick="chooseWorkspaceItem(
                    '${inlineArg(item.relative_path)}',
                    '${item.type}'
                )"
            >
                اختيار
            </button>
        `;


        row.innerHTML = `

            <div class="file-name">

                <span>
                    ${icon}
                </span>

                <span>
                    ${escapeHtml(item.name)}
                </span>

            </div>


            <div class="actions">
                ${buttons}
            </div>
        `;


        container.appendChild(
            row
        );
    }
}


async function browseWorkspaceParent() {

    if (
        !workspaceBrowser ||
        workspaceBrowser.parent === null
    ) {
        return;
    }

    await browseWorkspace(
        workspaceBrowser.parent
    );
}


function chooseWorkspaceItem(
    encodedPath,
    type
) {

    selectedWorkspacePath =
        decodeURIComponent(
            encodedPath
        );


    document.getElementById(
        "workspaceSelectedPath"
    ).textContent =
        selectedWorkspacePath;


    document.getElementById(
        "workspaceScopeType"
    ).value =
        type === "folder"
            ? "folder"
            : "file";


    toast(
        "تم اختيار النطاق — اضغط اعتماد"
    );
}


async function applyWorkspaceScope() {

    const type =
        document.getElementById(
            "workspaceScopeType"
        ).value;


    let path =
        selectedWorkspacePath;


    if (type === "project") {
        path = "";
    }


    try {

        await api(
            "/api/workspace/set-scope",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body:
                    JSON.stringify({
                        type,
                        path
                    })
            }
        );


        toast(
            "تم اعتماد نطاق العمل"
        );

        await loadWorkspace();

    }
    catch (error) {

        toast(
            error.message
        );
    }
}


function toggleAddProject() {

    document.getElementById(
        "addProjectForm"
    ).classList.toggle(
        "hidden"
    );
}


async function addWorkspaceProject() {

    const body = {

        name:
            document.getElementById(
                "newProjectName"
            ).value.trim(),

        path:
            document.getElementById(
                "newProjectPath"
            ).value.trim(),

        main_goal:
            document.getElementById(
                "newProjectGoal"
            ).value.trim(),

        claude_role:
            document.getElementById(
                "newClaudeRole"
            ).value.trim(),

        chatgpt_role:
            document.getElementById(
                "newChatGPTRole"
            ).value.trim()
    };


    if (!body.name || !body.path) {

        toast(
            "اسم المشروع والمسار مطلوبان"
        );

        return;
    }


    try {

        await api(
            "/api/workspace/add-project",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body:
                    JSON.stringify(body)
            }
        );


        toggleAddProject();

        toast(
            "تمت إضافة المشروع"
        );

        await loadDashboard();

    }
    catch (error) {

        toast(
            error.message
        );
    }
}


async function saveWorkspaceProject() {

    try {

        await api(
            "/api/workspace/update-project",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body:
                    JSON.stringify({

                        main_goal:
                            document.getElementById(
                                "workspaceGoal"
                            ).value.trim(),

                        claude_role:
                            document.getElementById(
                                "workspaceClaudeRole"
                            ).value.trim(),

                        chatgpt_role:
                            document.getElementById(
                                "workspaceChatGPTRole"
                            ).value.trim()
                    })
            }
        );


        toast(
            "تم حفظ هدف المشروع والأدوار"
        );

        await loadWorkspace();

    }
    catch (error) {

        toast(
            error.message
        );
    }
}



loadDashboard();

setInterval(
    loadDashboard,
    2500
);

// =========================================================
// V3.2 LOCAL MONITOR + SNAPSHOTS
// =========================================================

let v32Data = null;
let v32AutoEnabled = false;
let v32AutoTimer = null;

function v32Escape(value) {
    const div = document.createElement("div");
    div.textContent = value ?? "";
    return div.innerHTML;
}

function v32FormatBytes(bytes) {
    const value = Number(bytes || 0);

    if (value < 1024) {
        return `${value} B`;
    }

    if (value < 1024 * 1024) {
        return (value / 1024).toFixed(1) + " KB";
    }

    if (value < 1024 * 1024 * 1024) {
        return (value / (1024 * 1024)).toFixed(1) + " MB";
    }

    return (
        value /
        (1024 * 1024 * 1024)
    ).toFixed(2) + " GB";
}

function v32FormatTime(value) {
    if (!value) {
        return "لم يبدأ";
    }

    try {
        return new Date(value).toLocaleString("ar-SA");
    }
    catch {
        return value;
    }
}

async function v32Load() {
    try {
        v32Data = await api("/api/v32/status");
        v32RenderMonitor();
        v32RenderEvents();
        v32RenderSnapshots();
    }
    catch (error) {
        console.error("V3.2:", error);
    }
}

function v32RenderMonitor() {
    const monitor = v32Data?.monitor || {};
    const counts = monitor.last_change_counts || {};

    document.getElementById("v32WatchedFiles").textContent =
        monitor.watched_files || 0;

    document.getElementById("v32Created").textContent =
        counts.created || 0;

    document.getElementById("v32Modified").textContent =
        counts.modified || 0;

    document.getElementById("v32Deleted").textContent =
        counts.deleted || 0;

    document.getElementById("v32LastScan").textContent =
        v32FormatTime(monitor.last_scan);

    document.getElementById("v32ScanDuration").textContent =
        monitor.last_scan_duration_ms
            ? `${monitor.last_scan_duration_ms} ms`
            : "-";

    const scope = monitor.current_scope || {};
    let scopeText = "-";

    if (scope.error) {
        scopeText = scope.error;
    }
    else {
        scopeText =
            scope.relative_path ||
            "المشروع كامل";
    }

    if (monitor.truncated) {
        scopeText += " — تم الوصول لحد الملفات";
    }

    document.getElementById("v32Scope").textContent =
        scopeText;
}

function v32RenderEvents() {
    const container = document.getElementById("v32Events");
    const events = v32Data?.events || [];

    if (!events.length) {
        container.innerHTML = `
            <div class="empty">
                لا يوجد سجل حتى الآن
            </div>
        `;
        return;
    }

    const labels = {
        created: "جديد",
        modified: "تعديل",
        deleted: "حذف"
    };

    container.innerHTML = "";

    for (const event of events.slice(0, 50)) {
        const row = document.createElement("div");
        row.className = `v32-row v32-${event.type}`;

        const agent =
            event.agent &&
            event.agent !== "local"
                ? event.agent
                : "محلي";

        row.innerHTML = `
            <div>
                <strong>
                    ${labels[event.type] || event.type}
                </strong>

                <div class="v32-path">
                    ${v32Escape(event.path)}
                </div>
            </div>

            <div class="v32-event-meta">
                <span>${v32Escape(agent)}</span>
                <span>${v32FormatTime(event.timestamp)}</span>
            </div>
        `;

        container.appendChild(row);
    }
}

function v32RenderSnapshots() {
    const container = document.getElementById("v32Snapshots");
    const snapshots = v32Data?.snapshots || [];

    document.getElementById("v32SnapshotCount").textContent =
        snapshots.length;

    if (!snapshots.length) {
        container.innerHTML = `
            <div class="empty">
                لا توجد نسخ بعد
            </div>
        `;
        return;
    }

    container.innerHTML = "";

    for (const snapshot of snapshots) {
        const row = document.createElement("div");
        row.className = "v32-row v32-snapshot";

        const label =
            snapshot.label ||
            snapshot.snapshot_id;

        const scope =
            snapshot.relative_path ||
            "المشروع كامل";

        row.innerHTML = `
            <div>
                <strong>
                    ${v32Escape(label)}
                </strong>

                <div class="v32-path">
                    ${v32Escape(scope)}
                </div>

                <div class="task-meta">
                    ${snapshot.file_count || 0}
                    ملف
                    —
                    ${v32FormatBytes(snapshot.total_size)}
                </div>
            </div>

            <div class="actions">
                <button
                    class="btn warning small"
                    onclick="v32RestoreSnapshot(
                        '${inlineArg(snapshot.snapshot_id)}'
                    )"
                >
                    استعادة
                </button>

                <button
                    class="btn danger small"
                    onclick="v32DeleteSnapshot(
                        '${inlineArg(snapshot.snapshot_id)}'
                    )"
                >
                    حذف النسخة
                </button>
            </div>
        `;

        container.appendChild(row);
    }
}

async function v32CreateBaseline() {
    try {
        const result =
            await api(
                "/api/v32/baseline",
                {
                    method: "POST"
                }
            );

        toast(
            `تم بناء خط الأساس لـ ${result.watched_files || 0} ملف`
        );

        await v32Load();
    }
    catch (error) {
        toast(error.message);
    }
}

async function v32ScanNow(silent=false) {
    try {
        const result =
            await api(
                "/api/v32/scan",
                {
                    method: "POST"
                }
            );

        if (!silent) {
            if (result.baseline_reset) {
                toast(
                    "تغير نطاق العمل؛ تم بناء خط أساس جديد"
                );
            }
            else {
                const counts =
                    result.change_counts || {};

                toast(
                    `جديد ${counts.created || 0} | ` +
                    `معدل ${counts.modified || 0} | ` +
                    `محذوف ${counts.deleted || 0}`
                );
            }
        }

        await v32Load();
    }
    catch (error) {
        if (!silent) {
            toast(error.message);
        }
    }
}

function v32ToggleAuto() {
    const button =
        document.getElementById(
            "v32AutoButton"
        );

    if (v32AutoEnabled) {
        clearInterval(v32AutoTimer);

        v32AutoTimer = null;
        v32AutoEnabled = false;

        button.textContent =
            "تشغيل المراقبة التلقائية";

        button.className =
            "btn secondary small";

        toast(
            "تم إيقاف المراقبة التلقائية"
        );

        return;
    }

    const seconds =
        Math.max(
            10,
            Number(
                v32Data?.monitor?.config
                    ?.recommended_scan_interval_seconds
                || 15
            )
        );

    v32AutoEnabled = true;

    button.textContent =
        "إيقاف المراقبة التلقائية";

    button.className =
        "btn success small";

    v32ScanNow(true);

    v32AutoTimer =
        setInterval(
            () => {
                v32ScanNow(true);
            },
            seconds * 1000
        );

    toast(
        `المراقبة المحلية كل ${seconds} ثانية`
    );
}

async function v32CreateSnapshot() {
    const label =
        document.getElementById(
            "v32SnapshotLabel"
        ).value.trim();

    if (
        !confirm(
            "إنشاء Snapshot محلي للنطاق الحالي؟\n\n" +
            "لا يستهلك كريدت، لكنه قد يستهلك مساحة تخزين إذا كان النطاق كبيرًا."
        )
    ) {
        return;
    }

    try {
        toast(
            "جاري إنشاء Snapshot..."
        );

        const result =
            await api(
                "/api/v32/snapshot/create",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify({
                            label
                        })
                }
            );

        document.getElementById(
            "v32SnapshotLabel"
        ).value = "";

        const snapshot =
            result.snapshot || {};

        toast(
            `تم حفظ ${snapshot.file_count || 0} ملف محليًا`
        );

        await v32Load();
    }
    catch (error) {
        toast(error.message);
    }
}

async function v32RestoreSnapshot(encodedId) {
    const id =
        decodeURIComponent(
            encodedId
        );

    if (
        !confirm(
            "استعادة هذه النسخة؟\n\n" +
            "سيتم إنشاء Snapshot أمان للحالة الحالية قبل الكتابة عندما يكون النطاق موجودًا.\n" +
            "لن يتم حذف الملفات الزائدة تلقائيًا."
        )
    ) {
        return;
    }

    try {
        toast(
            "جاري إنشاء نسخة أمان ثم الاستعادة..."
        );

        const result =
            await api(
                "/api/v32/snapshot/restore",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify({
                            snapshot_id:
                                id
                        })
                }
            );

        toast(
            `تمت استعادة ${result.restored_files || 0} ملف`
        );

        await v32CreateBaseline();
        await v32Load();
    }
    catch (error) {
        toast(error.message);
    }
}

async function v32DeleteSnapshot(encodedId) {
    const id =
        decodeURIComponent(
            encodedId
        );

    if (
        !confirm(
            "حذف Snapshot المحلي نهائيًا؟\n\n" +
            "هذا لا يحذف أي ملف من المشروع."
        )
    ) {
        return;
    }

    try {
        await api(
            "/api/v32/snapshot/delete",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body:
                    JSON.stringify({
                        snapshot_id:
                            id
                    })
            }
        );

        toast(
            "تم حذف Snapshot"
        );

        await v32Load();
    }
    catch (error) {
        toast(error.message);
    }
}

setTimeout(
    v32Load,
    800
);

// Execution UX and output gallery. No automatic paid launches or retries.
function renderExecutionProjects() {
    const select = document.getElementById('taskProject');
    const outputSelect = document.getElementById('outputProject');
    const projects = dashboardData.projects.projects || {};
    for (const element of [select, outputSelect]) {
        const previous = element.value;
        element.replaceChildren();
        for (const [id, project] of Object.entries(projects)) element.add(new Option(project.name, id));
        element.value = projects[previous] ? previous : projects.control_center ? 'control_center' : dashboardData.projects.active_project;
    }
}
const smokeBusy = new Set();
async function smokeAgent(agent) {
    if (smokeBusy.size) return;
    smokeBusy.add(agent);
    const buttons = document.querySelectorAll('[data-smoke]'); buttons.forEach(b => b.disabled=true);
    try {
        const result = await api('/api/tasks/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
            title:`Stdin smoke: ${agent}`, description:'Reply CONTROL_CENTER_SMOKE_OK only; no tools or file changes.',
            agent, project:'control_center', smoke_test:true, priority:'low', send_now:true, request_id:crypto.randomUUID()
        })});
        toast(result.sent ? 'Minimal smoke dispatched once' : 'Smoke queued; inspect dispatch status');
        await loadDashboard();
    } catch(error) { toast(error.message); }
    finally { smokeBusy.delete(agent); buttons.forEach(b => b.disabled=false); }
}
async function loadOutputs() {
    const select=document.getElementById('outputProject'), container=document.getElementById('outputGallery');
    if (!select || !container) return;
    const {outputs}=await api('/api/outputs?project='+encodeURIComponent(select.value || 'control_center'));
    container.replaceChildren();
    if (!outputs.length) { container.textContent='No task outputs recorded for this project yet.'; return; }
    for (const output of outputs) {
        const card=document.createElement('article'); card.className='output-card';
        const url='/api/outputs/file/'+encodeURIComponent(output.id);
        if (['png','jpg','jpeg','webp'].includes(output.type)) {
            const img=document.createElement('img'); img.src=url; img.loading='lazy'; img.alt=output.filename; card.append(img);
        } else if (['mp4','webm'].includes(output.type)) {
            const video=document.createElement('video'); video.src=url; video.controls=true; video.preload='metadata'; card.append(video);
        }
        const title=document.createElement('strong'); title.textContent=output.filename; card.append(title);
        const meta=document.createElement('p'); meta.textContent=`${output.agent} · ${output.task_title} · ${output.type.toUpperCase()} · ${output.size.toLocaleString()} bytes · ${output.timestamp}`; card.append(meta);
        const path=document.createElement('code'); path.textContent=output.path; card.append(path);
        const link=document.createElement('a'); link.href=url; link.target='_blank'; link.rel='noopener'; link.textContent='View / download'; card.append(link);
        for (const action of ['file','folder']) {
            const button=document.createElement('button'); button.className='btn secondary small'; button.textContent=action==='file'?'Open File':'Open Folder';
            button.onclick=async()=>{ try {await api('/api/outputs/open',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:output.id,action})});} catch(error){toast(error.message);} };
            card.append(button);
        }
        container.append(card);
    }
}
