const API = "/api";

let currentRole = "student";

let currentMode = "nl";

let currentDatabase = "college";

let lastColumns = [];

let lastRows = [];

let sqlVisible = false;



document.addEventListener("DOMContentLoaded", () => {

    fetchSchema();

    setupEvents();

});



function setupEvents() {

    const form = document.getElementById("query-form");

    const input = document.getElementById("question-input");

    const btnStudent = document.getElementById("btn-role-student");

    const btnTeacher = document.getElementById("btn-role-teacher");

    const btnHod = document.getElementById("btn-role-hod");

    const modeSelector = document.getElementById("mode-selector");

    const modeNL = document.getElementById("mode-nl");

    const modeSQL = document.getElementById("mode-sql");

    const roleBadge = document.getElementById("role-badge");

    const roleSubtext = document.getElementById("role-subtext");

    const accessDot = document.getElementById("access-dot");

    const accessDesc = document.getElementById("access-desc");

    const toggleSqlBtn = document.getElementById("toggle-sql-btn");

    const dbSelector = document.getElementById("db-selector");

    const dbCard = document.getElementById("db-selector-card");

    const newDbBtn = document.getElementById("new-db-btn");



    function updateRoleUI(role) {

        currentRole = role;

        btnStudent.classList.remove("active");

        btnTeacher.classList.remove("active-teacher");

        btnHod.classList.remove("active-hod");



        if (role === "student") {

            btnStudent.classList.add("active");

            modeSelector.classList.add("hidden");

            dbCard.classList.remove("hidden");

            dbSelector.disabled = false;

            document.querySelectorAll(".write-only, .hod-only").forEach(el => el.classList.add("hidden"));

            roleBadge.textContent = "Student Mode";

            roleBadge.style.color = "#38bdf8";

            roleBadge.style.borderColor = "#38bdf8";

            roleSubtext.textContent = "Viewing as Student (Read-Only: SELECT queries only).";

            accessDot.className = "dot";

            accessDesc.textContent = "Read-Only Enforced";

            setMode("nl");

        } else if (role === "teacher") {

            btnTeacher.classList.add("active-teacher");

            modeSelector.classList.remove("hidden");

            currentDatabase = "college";

            dbSelector.value = "college";

            dbSelector.disabled = true;

            document.getElementById("active-db-pill").textContent = "DB: college";

            document.querySelectorAll(".write-only").forEach(el => el.classList.remove("hidden"));

            document.querySelectorAll(".hod-only").forEach(el => el.classList.add("hidden"));

            roleBadge.textContent = "Teacher Mode";

            roleBadge.style.color = "#34d399";

            roleBadge.style.borderColor = "#10b981";

            roleSubtext.textContent = "Teacher Access: Strictly 'students' table only (Read & Write).";

            accessDot.className = "dot teacher";

            accessDesc.textContent = "Students Table Only";

        } else {

            btnHod.classList.add("active-hod");

            modeSelector.classList.remove("hidden");

            dbCard.classList.remove("hidden");

            dbSelector.disabled = false;

            document.querySelectorAll(".write-only, .hod-only").forEach(el => el.classList.remove("hidden"));

            roleBadge.textContent = "HOD (Full Access)";

            roleBadge.style.color = "#f59e0b";

            roleBadge.style.borderColor = "#f59e0b";

            roleSubtext.textContent = "HOD Full Control: Create Databases, Tables, Insert, Update, Delete, Select & Direct SQL.";

            accessDot.className = "dot hod";

            accessDesc.textContent = "Full HOD Access";

        }

        fetchSchema();

    }



    btnStudent.addEventListener("click", () => updateRoleUI("student"));

    btnTeacher.addEventListener("click", () => updateRoleUI("teacher"));

    btnHod.addEventListener("click", () => updateRoleUI("hod"));



    dbSelector.addEventListener("change", () => {

        currentDatabase = dbSelector.value;

        document.getElementById("active-db-pill").textContent = `DB: ${currentDatabase}`;

        fetchSchema();

    });



    newDbBtn.addEventListener("click", async () => {

        const dbName = prompt("Naya database ka naam likhein (e.g. PassStudent):");

        if (!dbName || !dbName.trim()) return;

        await runQuery(`Create new database ${dbName.trim()}`);

    });



    modeNL.addEventListener("click", () => setMode("nl"));

    modeSQL.addEventListener("click", () => setMode("sql"));



    function setMode(mode) {

        currentMode = mode;

        if (mode === "nl") {

            modeNL.classList.add("active");

            modeSQL.classList.remove("active");

            input.placeholder = currentRole === "hod"

                ? "HOD Prompt: e.g., 'Create new database PassStudent', 'create table toppers with name, marks', or any query..."

                : (currentRole === "teacher"

                    ? "Teacher Prompt (Students only): e.g., 'show all students' or 'add student \"Rahul\" marks 90'..."

                    : "Student Prompt (Read-Only): e.g., 'show all students'...");

        } else {

            modeSQL.classList.add("active");

            modeNL.classList.remove("active");

            input.placeholder = "Direct SQL: e.g., CREATE DATABASE PassStudent; or CREATE TABLE ... or SELECT * FROM ...";

        }

    }



    toggleSqlBtn.addEventListener("click", () => {

        sqlVisible = !sqlVisible;

        const sqlPanel = document.getElementById("sql-panel");

        if (sqlVisible) {

            sqlPanel.classList.remove("hidden");

            toggleSqlBtn.textContent = "🙈 Hide SQL";

        } else {

            sqlPanel.classList.add("hidden");

            toggleSqlBtn.textContent = "👁️ View SQL";

        }

    });



    form.addEventListener("submit", (e) => {

        e.preventDefault();

        const q = input.value.trim();

        if (q) runQuery(q);

    });



    document.querySelectorAll(".chip").forEach(c => {

        c.addEventListener("click", () => {

            input.value = c.dataset.q;

            runQuery(c.dataset.q);

        });

    });



    document.getElementById("copy-btn").addEventListener("click", () => {

        navigator.clipboard.writeText(document.getElementById("sql-view").textContent);

        const b = document.getElementById("copy-btn");

        b.textContent = "Copied!";

        setTimeout(() => b.textContent = "Copy", 1500);

    });



    document.getElementById("export-csv-btn").addEventListener("click", exportCSV);

    document.getElementById("export-json-btn").addEventListener("click", exportJSON);

    document.getElementById("refresh-schema-btn").addEventListener("click", fetchSchema);

}



function updateDatabaseDropdown(databases, activeDb) {

    const dbSelector = document.getElementById("db-selector");

    currentDatabase = activeDb;

    dbSelector.innerHTML = "";

    databases.forEach(db => {

        const opt = document.createElement("option");

        opt.value = db;

        opt.textContent = `${db}.db`;

        if (db === activeDb) opt.selected = true;

        dbSelector.appendChild(opt);

    });

    document.getElementById("active-db-pill").textContent = `DB: ${activeDb}`;

    document.getElementById("schema-title").textContent = `Schema (${activeDb}.db)`;

}



async function fetchSchema() {

    try {

        const res = await fetch(`${API}/schema?database=${encodeURIComponent(currentDatabase)}&role=${encodeURIComponent(currentRole)}`);

        const data = await res.json();

        updateDatabaseDropdown(data.databases, data.database);



        const box = document.getElementById("schema-viewer");

        box.innerHTML = "";

        if (!data.tables || data.tables.length === 0) {

            box.innerHTML = `<p style="font-size:0.78rem; color:#94a3b8; padding:8px;">'${data.database}.db' mein abhi koi table nahi hai. HOD mode mein table create karein.</p>`;

            return;

        }

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

                mode: currentMode,

                database: currentDatabase

            })

        });



        const data = await res.json();

        if (!res.ok) throw new Error(data.detail || "Query rejected");



        if (data.active_database) {

            updateDatabaseDropdown(data.databases, data.active_database);

        }



        document.getElementById("t-role").textContent = currentRole.toUpperCase();

        document.getElementById("t-db").textContent = data.active_database;

        document.getElementById("t-action").textContent = data.action_type.toUpperCase();

        document.getElementById("t-src").textContent = data.classification_source.toUpperCase();

        document.getElementById("t-exec").textContent = `${data.execution_ms}ms`;

        document.getElementById("telemetry-box").classList.remove("hidden");



        document.getElementById("sql-view").textContent = data.sql;

        if (sqlVisible) {

            document.getElementById("sql-panel").classList.remove("hidden");

        } else {

            document.getElementById("sql-panel").classList.add("hidden");

        }



        if (data.message) {

            successBanner.textContent = data.message;

            successBanner.classList.remove("hidden");

        }



        if (data.action_type !== "select") {

            fetchSchema();

        }



        lastColumns = data.columns;

        lastRows = data.rows;

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

        body.innerHTML = `<tr><td colspan="${cols.length}" style="text-align:center; color:#9ca3af;">No records yet.</td></tr>`;

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



function downloadFile(content, filename, mimeType) {

    const blob = new Blob([content], { type: mimeType });

    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");

    a.href = url;

    a.download = filename;

    document.body.appendChild(a);

    a.click();

    document.body.removeChild(a);

    URL.revokeObjectURL(url);

}



function exportCSV() {

    if (!lastColumns.length) return;

    const escapeCSV = (val) => {

        if (val === null || val === undefined) return "";

        const s = String(val);

        return s.includes(",") || s.includes('"') || s.includes("\n")

            ? '"' + s.replace(/"/g, '""') + '"'

            : s;

    };

    const lines = [lastColumns.join(",")];

    lastRows.forEach(r => {

        lines.push(lastColumns.map(c => escapeCSV(r[c])).join(","));

    });

    downloadFile(lines.join("\n"), `${currentDatabase}_export_${Date.now()}.csv`, "text/csv;charset=utf-8;");

}



function exportJSON() {

    if (!lastColumns.length) return;

    downloadFile(JSON.stringify(lastRows, null, 2), `${currentDatabase}_export_${Date.now()}.json`, "application/json");

}
