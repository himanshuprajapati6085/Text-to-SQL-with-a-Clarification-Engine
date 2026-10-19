const API = "/api";
let currentRole = "student";
let currentMode = "nl";

document.addEventListener("DOMContentLoaded", () => {
    fetchSchema();
    setupEvents();
});

function setupEvents() {
    const form = document.getElementById("query-form");
    const input = document.getElementById("question-input");
    const btnStudent = document.getElementById("btn-role-student");
    const btnAssociate = document.getElementById("btn-role-associate");
    const modeSelector = document.getElementById("mode-selector");
    const modeNL = document.getElementById("mode-nl");
    const modeSQL = document.getElementById("mode-sql");
    const roleBadge = document.getElementById("role-badge");
    const roleSubtext = document.getElementById("role-subtext");
    const accessDot = document.getElementById("access-dot");
    const accessDesc = document.getElementById("access-desc");

    btnStudent.addEventListener("click", () => {
        currentRole = "student";
        btnStudent.classList.add("active");
        btnAssociate.classList.remove("active-admin");
        modeSelector.classList.add("hidden");
        document.querySelectorAll(".associate-only").forEach(el => el.classList.add("hidden"));
        roleBadge.textContent = "Student Mode";
        roleBadge.style.color = "#38bdf8";
        roleBadge.style.borderColor = "#38bdf8";
        roleSubtext.textContent = "Viewing as Student (Queries are constrained to SELECT only).";
        accessDot.className = "dot";
        accessDesc.textContent = "Read-Only Enforced";
        input.placeholder = "Ask questions about students, departments, or marks in plain English...";
        setMode("nl");
    });

    btnAssociate.addEventListener("click", () => {
        currentRole = "associate";
        btnAssociate.classList.add("active-admin");
        btnStudent.classList.remove("active");
        modeSelector.classList.remove("hidden");
        document.querySelectorAll(".associate-only").forEach(el => el.classList.remove("hidden"));
        roleBadge.textContent = "Associate (Full Access)";
        roleBadge.style.color = "#f59e0b";
        roleBadge.style.borderColor = "#f59e0b";
        roleSubtext.textContent = "Authorized: Can Insert, Update multiple records, Delete, or Alter Schema.";
        accessDot.className = "dot admin";
        accessDesc.textContent = "Read & Write Enabled";
    });

    modeNL.addEventListener("click", () => setMode("nl"));
    modeSQL.addEventListener("click", () => setMode("sql"));

    function setMode(mode) {
        currentMode = mode;
        if (mode === "nl") {
            modeNL.classList.add("active");
            modeSQL.classList.remove("active");
            input.placeholder = currentRole === "associate" 
                ? "Type update or query (e.g. 'replace 3rd student name to Himanshu and 4th student name to Himanshu Prajapati')..."
                : "Ask questions about students or marks...";
        } else {
            modeSQL.classList.add("active");
            modeNL.classList.remove("active");
            input.placeholder = "Enter raw SQL (e.g. ALTER TABLE students ADD COLUMN email VARCHAR(100);)...";
        }
    }

    form.addEventListener("submit", (e) => {
        e.preventDefault();
        const q = input.value.trim();
        if (q) runQuery(q);
    });

    document.querySelectorAll(".chip").forEach(c => {
        c.addEventListener("click", () => {
            input.value = c.dataset.q;
            if (c.dataset.q.toUpperCase().startsWith("ALTER") || c.dataset.q.toUpperCase().startsWith("INSERT")) {
                if (currentRole === "associate") setMode("sql");
            }
            runQuery(c.dataset.q);
        });
    });

    document.getElementById("copy-btn").addEventListener("click", () => {
        navigator.clipboard.writeText(document.getElementById("sql-view").textContent);
        const b = document.getElementById("copy-btn");
        b.textContent = "Copied!";
        setTimeout(() => b.textContent = "Copy", 1500);
    });

    document.getElementById("refresh-schema-btn").addEventListener("click", () => {
        fetchSchema();
    });
}

async function fetchSchema() {
    try {
        const res = await fetch(`${API}/schema`);
        const data = await res.json();
        const box = document.getElementById("schema-viewer");
        box.innerHTML = "";
        data.tables.forEach(t => {
            const card = document.createElement("div");
            card.className = "tbl-card";
            const cols = t.columns.map(c => `<li>${c.name} <span style="opacity:0.4">${c.type}</span></li>`).join("");
            card.innerHTML = `<h4>${t.table_name}</h4><ul>${cols}</ul>`;
            box.appendChild(card);
        });
    } catch (e) {
        document.getElementById("schema-viewer").innerHTML = "<p style='color:#f87171'>Schema load error</p>";
    }
}

async function runQuery(question) {
    const btn = document.getElementById("submit-btn");
    const txt = document.getElementById("btn-text");
    const spin = document.getElementById("btn-spinner");
    const err = document.getElementById("error-alert");
    const successBanner = document.getElementById("success-banner");

    btn.disabled = true;
    txt.classList.add("hidden");
    spin.classList.remove("hidden");
    err.classList.add("hidden");
    successBanner.classList.add("hidden");

    try {
        const res = await fetch(`${API}/query`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                question: question,
                role: currentRole,
                mode: currentMode
            })
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Query execution rejected");

        document.getElementById("t-role").textContent = currentRole.toUpperCase();
        document.getElementById("t-action").textContent = data.action_type.toUpperCase();
        document.getElementById("t-src").textContent = data.classification_source.toUpperCase();
        document.getElementById("t-gen").textContent = `${data.generation_ms}ms`;
        document.getElementById("t-exec").textContent = `${data.execution_ms}ms`;
        document.getElementById("telemetry-box").classList.remove("hidden");

        document.getElementById("sql-view").textContent = data.sql;
        document.getElementById("sql-panel").classList.remove("hidden");

        if (data.action_type !== "select" && data.message) {
            successBanner.textContent = data.message;
            successBanner.classList.remove("hidden");
            fetchSchema();
        }

        renderTable(data.columns, data.rows);
        document.getElementById("row-badge").textContent = `${data.row_count} rows`;
        document.getElementById("results-panel").classList.remove("hidden");

    } catch (e) {
        err.textContent = e.message;
        err.classList.remove("hidden");
        document.getElementById("telemetry-box").classList.add("hidden");
        document.getElementById("sql-panel").classList.add("hidden");
        document.getElementById("results-panel").classList.add("hidden");
    } finally {
        btn.disabled = false;
        txt.classList.remove("hidden");
        spin.classList.add("hidden");
    }
}

function renderTable(cols, rows) {
    const head = document.getElementById("tbl-head");
    const body = document.getElementById("tbl-body");
    head.innerHTML = "";
    body.innerHTML = "";

    if (!cols || cols.length === 0) {
        body.innerHTML = `<tr><td style="text-align:center; color:#9ca3af;">Operation completed.</td></tr>`;
        return;
    }

    const tr = document.createElement("tr");
    cols.forEach(c => {
        const th = document.createElement("th");
        th.textContent = c.toUpperCase();
        tr.appendChild(th);
    });
    head.appendChild(tr);

    if (rows.length === 0) {
        body.innerHTML = `<tr><td colspan="${cols.length}" style="text-align:center; color:#9ca3af;">0 rows matched</td></tr>`;
        return;
    }

    rows.forEach(r => {
        const row = document.createElement("tr");
        cols.forEach(c => {
            const td = document.createElement("td");
            td.textContent = r[c] !== null && r[c] !== undefined ? r[c] : "NULL";
            row.appendChild(td);
        });
        body.appendChild(row);
    });
}
