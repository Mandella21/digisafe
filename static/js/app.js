// DigiSafe Client Application
function getToken() { return localStorage.getItem("digisafe_token"); }
function setToken(token) { localStorage.setItem("digisafe_token", token); }
function getUser() {
    try { return JSON.parse(localStorage.getItem("digisafe_user")); } catch { return null; }
}
function setUser(user) { localStorage.setItem("digisafe_user", JSON.stringify(user)); }
function logout() {
    localStorage.removeItem("digisafe_token");
    localStorage.removeItem("digisafe_user");
    showToast("Logged out successfully.", "info");
    setTimeout(() => { window.location.href = "/"; }, 500);
}
function showToast(message, type = "info") {
    const toastEl = document.getElementById("liveToast");
    if (!toastEl) return;
    document.getElementById("toastMessage").textContent = message;
    toastEl.className = `toast align-items-center border-0 text-white bg-${type === "error" ? "danger" : (type === "success" ? "success" : "primary")}`;
    const toast = new bootstrap.Toast(toastEl, { delay: 3500 });
    toast.show();
}
function checkAuthUI() {
    const token = getToken();
    const user = getUser();
    const authNav = document.getElementById("authNavContainer");
    const navAdmin = document.getElementById("navAdminItem");
    const navAudit = document.getElementById("navAuditItem");
    if (!authNav) return;
    if (token && user) {
        let roleBadge = "bg-primary";
        if (user.role === "admin") roleBadge = "bg-danger";
        if (user.role === "officer") roleBadge = "bg-warning text-dark";
        authNav.innerHTML = `
            <div class="dropdown">
                <button class="btn btn-outline-light btn-sm dropdown-toggle d-flex align-items-center gap-2" type="button" data-bs-toggle="dropdown">
                    <i class="bi bi-person-circle"></i>
                    <span>${user.full_name || user.email}</span>
                    <span class="badge ${roleBadge} text-uppercase" style="font-size: 0.65rem;">${user.role}</span>
                </button>
                <ul class="dropdown-menu dropdown-menu-end shadow border-0">
                    <li><h6 class="dropdown-header">${user.email}</h6></li>
                    <li><a class="dropdown-item" href="/track"><i class="bi bi-folder2 me-2"></i>My Submissions</a></li>
                    ${user.role !== "victim" ? '<li><a class="dropdown-item" href="/admin"><i class="bi bi-shield-lock me-2"></i>Officer Center</a></li>' : ''}
                    ${user.role === "admin" ? '<li><a class="dropdown-item" href="/audit"><i class="bi bi-journal-text me-2"></i>Audit Trail</a></li>' : ''}
                    <li><hr class="dropdown-divider"></li>
                    <li><button class="dropdown-item text-danger" onclick="logout()"><i class="bi bi-box-arrow-right me-2"></i>Sign Out</button></li>
                </ul>
            </div>
        `;
        if (navAdmin) navAdmin.style.display = (user.role === "admin" || user.role === "officer") ? "block" : "none";
        if (navAudit) navAudit.style.display = (user.role === "admin") ? "block" : "none";
    } else {
        authNav.innerHTML = `<a href="/auth" class="btn btn-outline-light btn-sm px-3"><i class="bi bi-person-plus me-1"></i> Register / Sign In</a>`;
        if (navAdmin) navAdmin.style.display = "none";
        if (navAudit) navAudit.style.display = "none";
    }
}
async function quickLogin(role) {
    let email = "victim@digisafe.org";
    let password = "Victim@123";
    if (role === "officer") { email = "officer@police.gov.gh"; password = "Officer@123"; }
    else if (role === "admin") { email = "admin@digisafe.org"; password = "Admin@123"; }

    try {
        const res = await fetch("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password, role })
        });
        const data = await res.json();
        if (res.ok) {
            setToken(data.access_token);
            setUser({ user_id: data.user_id, full_name: data.full_name, email: data.email, role: data.role });
            showToast(`Logged in as ${data.role.toUpperCase()}: ${data.full_name}`, "success");
            setTimeout(() => {
                window.location.href = (data.role === "admin" || data.role === "officer") ? "/admin" : "/track";
            }, 600);
        } else {
            showToast(data.detail || "Login failed.", "error");
        }
    } catch (err) { showToast("Connection error: " + err.message, "error"); }
}

const loginForm = document.getElementById("loginForm");
if (loginForm) {
    loginForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const email = document.getElementById("loginEmail").value.trim();
        const password = document.getElementById("loginPassword").value;
        // Optional: the account screens dropped this control. It never decided
        // anything - the server answers with the account's real role and the
        // redirect below uses that - so a page without it behaves identically.
        const roleField = document.getElementById("loginRole");
        const role = roleField ? roleField.value : "victim";
        try {
            const res = await fetch("/api/auth/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email, password, role })
            });
            const data = await res.json();
            if (res.ok) {
                setToken(data.access_token);
                setUser({ user_id: data.user_id, full_name: data.full_name, email: data.email, role: data.role });
                showToast("Signed in successfully!", "success");
                setTimeout(() => { window.location.href = (data.role === "admin" || data.role === "officer") ? "/admin" : "/track"; }, 500);
            } else if (res.status === 403 && res.headers.get("X-DigiSafe-Reason") === "email-unverified") {
                // The password was right; the address was simply never confirmed.
                // Carrying the email across means they land on the verification
                // page with the field already filled, rather than on a dead end.
                showToast("Please confirm your email address to finish signing in.", "info");
                sessionStorage.setItem("digisafe_pending_email", email);
                setTimeout(() => { window.location.href = "/verify"; }, 900);
            } else { showToast(data.detail || "Invalid credentials.", "error"); }
        } catch (err) { showToast("Network error: " + err.message, "error"); }
    });
}

const registerForm = document.getElementById("registerForm");
if (registerForm) {
    registerForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const full_name = document.getElementById("regName").value.trim();
        const email = document.getElementById("regEmail").value.trim();
        const password = document.getElementById("regPassword").value;
        const confirm = document.getElementById("regPasswordConfirm").value;
        const roleField = document.getElementById("regRole");
        const role = roleField ? roleField.value : "victim";

        if (password !== confirm) {
            showToast("Those two passwords are different. Please retype them.", "error");
            document.getElementById("regPasswordConfirm").focus();
            return;
        }
        if (password.length < 8) {
            showToast("Please choose a password of at least 8 characters.", "error");
            document.getElementById("regPassword").focus();
            return;
        }

        // Sending a real email takes a second or two. Without this the button
        // looks dead for that whole time and gets tapped again, which on a slow
        // phone connection fires a second registration.
        const regBtn = document.getElementById("regBtn");
        const regBtnLabel = regBtn ? regBtn.innerHTML : "";
        if (regBtn) {
            regBtn.disabled = true;
            regBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Creating your account...';
        }
        const restoreRegBtn = () => {
            if (regBtn) { regBtn.disabled = false; regBtn.innerHTML = regBtnLabel; }
        };

        try {
            const res = await fetch("/api/auth/register", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ full_name, email, password, confirm_password: confirm, role })
            });
            const data = await res.json();
            if (res.ok) {
                // Sign-up no longer signs anyone in. The account exists but is
                // inert until the code that just went to their inbox is entered,
                // so the next stop is the verification page - never a dashboard.
                if (data.verification_required === false) {
                    showToast("Account created. You can sign in now.", "success");
                    setTimeout(() => { window.location.href = "/auth"; }, 900);
                    return;
                }
                // Deliberately not re-enabled on success: the page is about to
                // navigate, and a button that springs back to life first invites
                // a second submission on the way out.
                sessionStorage.setItem("digisafe_pending_email", data.email);
                sessionStorage.setItem("digisafe_pending_message", data.message || "");
                sessionStorage.setItem("digisafe_pending_delivery", data.delivery || "smtp");
                showToast(data.email_sent ? "Account created - check your email for the code." : "Account created.", "success");
                setTimeout(() => { window.location.href = "/verify"; }, 700);
            } else {
                showToast(data.detail || "Registration failed.", "error");
                restoreRegBtn();
            }
        } catch (err) {
            showToast("Error: " + err.message, "error");
            restoreRegBtn();
        }
    });
}

async function handleEvidenceSubmission(e) {
    e.preventDefault();
    const token = getToken();
    if (!token) {
        showToast("Please sign in or use a demo account to submit evidence.", "error");
        setTimeout(() => { window.location.href = "/auth"; }, 1000);
        return;
    }
    const submitBtn = document.getElementById("submitBtn");
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Hashing & Encrypting...`;

    const formData = new FormData();
    formData.append("content_type", document.getElementById("contentType").value);
    formData.append("source_url", document.getElementById("sourceUrl").value.trim());
    formData.append("content", document.getElementById("content").value.trim());
    const fileInput = document.getElementById("attachment");
    if (fileInput && fileInput.files[0]) formData.append("file", fileInput.files[0]);

    try {
        const response = await fetch("/api/evidence/submit", {
            method: "POST",
            headers: { "Authorization": `Bearer ${token}` },
            body: formData
        });
        const result = await response.json();
        if (response.ok) {
            document.getElementById("modalHashValue").textContent = result.hash_value;
            const ml = result.ml_classification;
            document.getElementById("modalMlLabel").textContent = ml.label.toUpperCase();
            document.getElementById("modalMlLabel").className = `badge ${ml.label === "Abusive" ? "bg-danger" : "bg-success"}`;
            const tlEl = document.getElementById("modalThreatLevel");
            tlEl.textContent = `${ml.threat_level.toUpperCase()} (${(ml.confidence_score * 100).toFixed(0)}%)`;
            tlEl.className = `badge threat-badge-${ml.threat_level.toLowerCase()}`;
            document.getElementById("modalRiskSummary").textContent = ml.risk_summary;
            document.getElementById("modalStatus").textContent = result.status.toUpperCase();
            document.getElementById("modalDownloadPdfBtn").href = `/api/reports/download/${result.evidence_id}`;

            const modal = new bootstrap.Modal(document.getElementById("successModal"));
            modal.show();
            document.getElementById("evidenceForm").reset();
            document.getElementById("charCounter").textContent = "0 chars";
        } else { showToast(result.detail || "Submission failed.", "error"); }
    } catch (err) { showToast("Submission error: " + err.message, "error"); }
    finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = `<i class="bi bi-fingerprint me-2"></i> Submit & Cryptographically Seal Evidence`;
    }
}
async function loadMyEvidence() {
    const token = getToken();
    const container = document.getElementById("evidenceListContainer");
    const emptyAlert = document.getElementById("noEvidenceAlert");
    if (!container) return;
    if (!token) {
        container.innerHTML = `<div class="col-12 text-center py-5"><p class="text-muted">You are not signed in.</p><a class="btn btn-primary btn-sm" href="/auth">Sign in or create an account</a></div>`;
        return;
    }
    try {
        const res = await fetch("/api/evidence/my", { headers: { "Authorization": `Bearer ${token}` } });
        if (!res.ok) { container.innerHTML = `<div class="col-12 text-center text-danger py-4">Failed to load records.</div>`; return; }
        const items = await res.json();
        if (items.length === 0) {
            container.innerHTML = "";
            emptyAlert.classList.remove("d-none");
            return;
        }
        emptyAlert.classList.add("d-none");
        let html = "";
        items.forEach(r => {
            const tlClass = `threat-badge-${(r.threat_level || "none").toLowerCase()}`;
            const stClass = `status-badge-${(r.status || "pending").toLowerCase()}`;
            html += `
                <div class="col-md-6 col-lg-4">
                    <div class="card h-100 border-0 shadow-sm rounded-4 overflow-hidden">
                        <div class="card-header bg-white py-3 border-bottom d-flex justify-content-between align-items-center">
                            <span class="badge bg-light text-dark border font-monospace">#${r.evidence_id}</span>
                            <span class="badge ${stClass} text-uppercase">${r.status}</span>
                        </div>
                        <div class="card-body p-3">
                            <div class="d-flex justify-content-between align-items-center small text-muted mb-2">
                                <span><i class="bi bi-calendar3 me-1"></i>${r.submitted_at}</span>
                                <span class="badge bg-secondary-subtle text-dark">${r.content_type.toUpperCase()}</span>
                            </div>
                            <p class="card-text text-dark small bg-light p-2 rounded border font-monospace mb-3" style="min-height: 60px; max-height: 80px; overflow-y: auto;">
                                ${escapeHtml(r.content_decrypted)}
                            </p>
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <span class="small text-muted">ML Threat:</span>
                                <span class="badge ${tlClass}">${r.threat_level} (${(r.confidence_score * 100).toFixed(0)}%)</span>
                            </div>
                            <div class="small text-muted font-monospace text-truncate py-1 px-2 bg-light rounded border mb-3" title="${r.hash_value}">
                                <i class="bi bi-fingerprint text-primary me-1"></i>${r.hash_value}
                            </div>
                            <div class="d-flex gap-2">
                                <button class="btn btn-outline-secondary btn-sm flex-grow-1" onclick="openDetailModal(${r.evidence_id})"><i class="bi bi-eye me-1"></i> Details</button>
                                <button class="btn btn-outline-success btn-sm" title="Verify Checksum" onclick="verifyChecksum(${r.evidence_id})"><i class="bi bi-shield-check"></i></button>
                                <a href="/api/reports/download/${r.evidence_id}" class="btn btn-primary btn-sm" title="Download PDF Report" target="_blank"><i class="bi bi-file-earmark-pdf-fill"></i></a>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });
        container.innerHTML = html;
    } catch (err) { container.innerHTML = `<div class="col-12 text-center text-danger py-4">Error: ${err.message}</div>`; }
}

async function openDetailModal(evidenceId) {
    const token = getToken();
    try {
        const res = await fetch(`/api/evidence/${evidenceId}`, { headers: { "Authorization": `Bearer ${token}` } });
        const data = await res.json();
        if (res.ok) {
            document.getElementById("detailModalTitle").innerHTML = `<i class="bi bi-file-text me-2"></i> Case Dossier #${data.evidence_id}`;
            document.getElementById("detailModalHash").textContent = data.hash_record.hash_value;
            document.getElementById("detailModalContent").textContent = data.content_decrypted;
            document.getElementById("detailModalSource").textContent = data.source_url || "Direct Message";
            document.getElementById("detailModalFile").textContent = data.file_name || "None";
            const ml = data.classification;
            document.getElementById("detailModalMlLabel").textContent = ml.label.toUpperCase();
            document.getElementById("detailModalMlLabel").className = `badge ${ml.label === "Abusive" ? "bg-danger" : "bg-success"}`;
            const tl = document.getElementById("detailModalThreat");
            tl.textContent = ml.threat_level.toUpperCase();
            tl.className = `badge threat-badge-${ml.threat_level.toLowerCase()}`;
            document.getElementById("detailModalScore").textContent = `Score: ${(ml.confidence_score * 100).toFixed(1)}%`;
            document.getElementById("detailModalSummary").textContent = `Status: ${data.status.toUpperCase()} | Model: ${ml.model_version}`;
            document.getElementById("detailDownloadBtn").href = `/api/reports/download/${data.evidence_id}`;
            document.getElementById("detailVerifyBtn").onclick = () => verifyChecksum(data.evidence_id);
            const modal = new bootstrap.Modal(document.getElementById("detailModal"));
            modal.show();
        } else { showToast(data.detail || "Could not retrieve details", "error"); }
    } catch (err) { showToast("Error: " + err.message, "error"); }
}

async function verifyChecksum(evidenceId) {
    const token = getToken();
    try {
        const res = await fetch(`/api/evidence/${evidenceId}/verify`, {
            method: "POST",
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await res.json();
        if (res.ok) {
            if (data.tampered) {
                alert(`CRITICAL ALERT: Tampering Detected on Evidence #${evidenceId}!\n\nStored Checksum: ${data.original_hash}\nRecomputed Hash: ${data.recomputed_hash}\n\nThe record has been marked as COMPROMISED and an alert was dispatched.`);
                showToast("Tampering detected! Record marked COMPROMISED.", "error");
            } else {
                alert(`INTEGRITY CONFIRMED: Evidence #${evidenceId} is Authentic!\n\nSHA-256 Checksum: ${data.original_hash}\n\nMathematical match verified with zero divergence.`);
                showToast("Cryptographic checksum verified successfully!", "success");
            }
            if (document.getElementById("adminEvidenceBody")) { loadAdminData(); }
            else if (document.getElementById("evidenceListContainer")) { loadMyEvidence(); }
        } else { showToast(data.detail || "Verification failed.", "error"); }
    } catch (err) { showToast("Verification error: " + err.message, "error"); }
}
async function loadAdminData() {
    const token = getToken();
    if (!token) { showToast("Officer/Admin authentication required.", "error"); return; }
    try {
        const statsRes = await fetch("/api/admin/stats", { headers: { "Authorization": `Bearer ${token}` } });
        if (statsRes.ok) {
            const stats = await statsRes.json();
            document.getElementById("statTotalSubmissions").textContent = stats.total_submissions;
            document.getElementById("statFlaggedCases").textContent = stats.flagged_cases;
            document.getElementById("statVerifiedRecords").textContent = stats.verified_records;
            document.getElementById("statCompromisedRecords").textContent = stats.compromised_records;
            document.getElementById("statActiveUsers").textContent = stats.active_users;
        }
    } catch (err) { console.error("Stats error", err); }

    try {
        const alertsRes = await fetch("/api/admin/alerts", { headers: { "Authorization": `Bearer ${token}` } });
        const alertsContainer = document.getElementById("alertsContainer");
        if (alertsRes.ok && alertsContainer) {
            const alerts = await alertsRes.json();
            if (alerts.length > 0) {
                alertsContainer.innerHTML = alerts.map(a => `
                    <div class="alert alert-danger d-flex justify-content-between align-items-center shadow-sm py-2 px-3 mb-2 rounded-3">
                        <div><i class="bi bi-shield-slash-fill me-2 fs-5"></i><strong>[${a.severity.toUpperCase()} ALERT]:</strong> ${a.message} <span class="small text-muted ms-2">${a.created_at}</span></div>
                        <button class="btn btn-outline-danger btn-sm" onclick="acknowledgeAlert(${a.alert_id})">Dismiss</button>
                    </div>
                `).join("");
            } else { alertsContainer.innerHTML = ""; }
        }
    } catch (err) { console.error("Alerts error", err); }

    try {
        const statusFilter = document.getElementById("filterStatus")?.value || "all";
        const threatFilter = document.getElementById("filterThreat")?.value || "all";
        const res = await fetch(`/api/admin/evidence?status_filter=${statusFilter}&threat_filter=${threatFilter}`, { headers: { "Authorization": `Bearer ${token}` } });
        const tbody = document.getElementById("adminEvidenceBody");
        const urgentQueue = document.getElementById("urgentQueueContainer");
        if (res.ok && tbody) {
            const items = await res.json();
            if (items.length === 0) {
                tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-muted">No evidence records match filters.</td></tr>`;
                if (urgentQueue) urgentQueue.innerHTML = `<div class="text-muted small text-center py-3">No urgent flagged cases.</div>`;
                return;
            }
            let rows = "";
            let urgentItems = [];
            items.forEach(r => {
                const tlClass = `threat-badge-${(r.threat_level || "none").toLowerCase()}`;
                const stClass = `status-badge-${(r.status || "pending").toLowerCase()}`;
                if (r.status === "flagged" || r.threat_level === "Critical" || r.threat_level === "High") urgentItems.push(r);
                rows += `
                    <tr>
                        <td class="font-monospace fw-bold">#${r.evidence_id}</td>
                        <td><div class="fw-semibold text-dark">${escapeHtml(r.victim_name)}</div><small class="text-muted">${r.submitted_at}</small></td>
                        <td><div class="small text-truncate" style="max-width: 250px;" title="${escapeHtml(r.content_full)}">${escapeHtml(r.content_preview)}</div><small class="text-muted badge bg-light text-dark border">${r.content_type.toUpperCase()}</small></td>
                        <td><span class="font-monospace small text-primary" title="${r.hash_value}">${r.hash_value.substring(0, 14)}...</span></td>
                        <td><span class="badge ${tlClass}">${r.threat_level} (${(r.confidence_score * 100).toFixed(0)}%)</span></td>
                        <td><span class="badge ${stClass} text-uppercase">${r.status}</span></td>
                        <td class="text-end">
                            <div class="btn-group btn-group-sm">
                                <button class="btn btn-outline-success" title="Run Checksum Verification" onclick="verifyChecksum(${r.evidence_id})"><i class="bi bi-shield-check"></i></button>
                                <button class="btn btn-outline-primary" title="Update Status / Notes" onclick="openStatusModal(${r.evidence_id})"><i class="bi bi-pencil-square"></i></button>
                                <a href="/api/reports/download/${r.evidence_id}" class="btn btn-outline-dark" title="Download Official PDF Dossier" target="_blank"><i class="bi bi-file-earmark-pdf-fill"></i></a>
                            </div>
                        </td>
                    </tr>
                `;
            });
            tbody.innerHTML = rows;
            if (urgentQueue) {
                if (urgentItems.length === 0) urgentQueue.innerHTML = `<div class="text-muted small text-center py-3">No urgent flagged cases pending.</div>`;
                else {
                    urgentQueue.innerHTML = urgentItems.slice(0, 5).map(u => `
                        <div class="card border-warning mb-2 bg-warning-subtle p-2 rounded-3">
                            <div class="d-flex justify-content-between align-items-center mb-1">
                                <span class="fw-bold font-monospace small">Case #${u.evidence_id}</span>
                                <span class="badge bg-danger">${u.threat_level}</span>
                            </div>
                            <div class="small text-dark text-truncate mb-2">${escapeHtml(u.content_preview)}</div>
                            <div class="d-flex gap-1">
                                <button class="btn btn-xs btn-dark py-0 px-2" style="font-size: 0.75rem;" onclick="verifyChecksum(${u.evidence_id})">Verify</button>
                                <a href="/api/reports/download/${u.evidence_id}" class="btn btn-xs btn-primary py-0 px-2" style="font-size: 0.75rem;" target="_blank">PDF</a>
                            </div>
                        </div>
                    `).join("");
                }
            }
        }
    } catch (err) { console.error("Evidence list error", err); }
}

async function acknowledgeAlert(alertId) {
    const token = getToken();
    await fetch(`/api/admin/alerts/${alertId}/ack`, { method: "POST", headers: { "Authorization": `Bearer ${token}` } });
    loadAdminData();
}

function openStatusModal(evidenceId) {
    document.getElementById("statusModalEvidenceId").value = evidenceId;
    const modal = new bootstrap.Modal(document.getElementById("statusModal"));
    modal.show();
}

async function submitStatusUpdate() {
    const token = getToken();
    const evidenceId = document.getElementById("statusModalEvidenceId").value;
    const status = document.getElementById("modalStatusSelect").value;
    const notes = document.getElementById("modalStatusNotes").value;
    try {
        const res = await fetch(`/api/admin/evidence/${evidenceId}/status`, {
            method: "POST",
            headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
            body: JSON.stringify({ status, notes })
        });
        const data = await res.json();
        if (res.ok) {
            showToast(data.message, "success");
            const modalEl = document.getElementById("statusModal");
            const modal = bootstrap.Modal.getInstance(modalEl);
            if (modal) modal.hide();
            loadAdminData();
        } else { showToast(data.detail || "Update failed", "error"); }
    } catch (err) { showToast("Error: " + err.message, "error"); }
}

async function triggerTamperSimulation() {
    const token = getToken();
    const evidenceId = prompt("Enter Evidence ID to test tampering (or leave blank to target Case #1):", "1");
    if (evidenceId === null) return;
    try {
        const res = await fetch(`/api/admin/evidence/${evidenceId || 1}/simulate-tamper`, {
            method: "POST",
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await res.json();
        if (res.ok) {
            alert(`EXAMINER TEST RESULT:\n\n1. Ciphertext in database was deliberately altered.\n2. Checksum Data Recovery routine executed.\n3. Result: ${data.verification_result.message}\n4. Tampered Flag: ${data.verification_result.tampered}\n5. Status updated to 'compromised'.`);
            loadAdminData();
        } else { showToast(data.detail || "Tampering test failed.", "error"); }
    } catch (err) { showToast("Error: " + err.message, "error"); }
}

async function loadAuditLogs() {
    const token = getToken();
    const tbody = document.getElementById("auditLogsBody");
    const filter = document.getElementById("auditActionFilter")?.value || "all";
    if (!tbody) return;
    if (!token) { tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-danger">Administrator sign-in required.</td></tr>`; return; }
    try {
        const res = await fetch(`/api/admin/audit-logs?action_filter=${filter}`, { headers: { "Authorization": `Bearer ${token}` } });
        if (res.ok) {
            const logs = await res.json();
            if (logs.length === 0) { tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-muted">No audit records found.</td></tr>`; return; }
            tbody.innerHTML = logs.map(l => {
                let actionBadge = "bg-secondary";
                if (l.action.includes("CHECKSUM_MISMATCH")) actionBadge = "bg-danger";
                else if (l.action.includes("PASS") || l.action.includes("REGISTER")) actionBadge = "bg-success";
                else if (l.action.includes("EVIDENCE")) actionBadge = "bg-primary";
                else if (l.action.includes("REPORT")) actionBadge = "bg-info text-dark";
                return `
                    <tr>
                        <td class="text-muted">#${l.log_id}</td>
                        <td>${l.performed_at}</td>
                        <td class="fw-bold">${escapeHtml(l.user_name)}</td>
                        <td><span class="badge bg-light text-dark border text-uppercase">${l.role}</span></td>
                        <td><span class="badge ${actionBadge}">${l.action}</span></td>
                        <td>${l.entity_type || "-"} ${l.entity_id ? "#" + l.entity_id : ""}</td>
                        <td class="small text-muted">${escapeHtml(l.details || "")}</td>
                    </tr>
                `;
            }).join("");
        } else { tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-danger">Access denied. Only Administrators can view audit logs.</td></tr>`; }
    } catch (err) { tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-danger">Error: ${err.message}</td></tr>`; }
}

function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

// Live confirm-password feedback on the registration form.
const regPwd = document.getElementById("regPassword");
const regPwdConfirm = document.getElementById("regPasswordConfirm");
const regPwdMatch = document.getElementById("regPasswordMatch");
if (regPwd && regPwdConfirm && regPwdMatch) {
    // Whatever the markup started with is the resting state - so this works on
    // the account screens and would still work on a Bootstrap-styled form.
    const restingText = regPwdMatch.textContent;
    const setState = (text, state) => {
        regPwdMatch.textContent = text;
        regPwdMatch.classList.remove("is-valid", "is-invalid");
        if (state) regPwdMatch.classList.add(state);
    };
    const checkMatch = () => {
        if (!regPwdConfirm.value) {
            setState(restingText, null);
        } else if (regPwd.value === regPwdConfirm.value) {
            setState("Passwords match.", "is-valid");
        } else {
            setState("Passwords do not match yet.", "is-invalid");
        }
    };
    regPwd.addEventListener("input", checkMatch);
    regPwdConfirm.addEventListener("input", checkMatch);
}


/* ======================================================================
   EMAIL VERIFICATION  (/verify)
   ======================================================================
   Serves both arrivals: someone redirected here from sign-up who types the
   6-digit code, and someone who simply tapped the button in the email, whose
   URL carries ?token=... and who should not have to type anything at all.
   ====================================================================== */

function finishVerification(data) {
    setToken(data.access_token);
    setUser({ user_id: data.user_id, full_name: data.full_name, email: data.email, role: data.role });
    sessionStorage.removeItem("digisafe_pending_email");
    sessionStorage.removeItem("digisafe_pending_message");
    sessionStorage.removeItem("digisafe_pending_delivery");

    const codeState = document.getElementById("codeVerifyState");
    const tokenState = document.getElementById("tokenVerifyState");
    const doneState = document.getElementById("verifiedState");
    if (codeState) codeState.hidden = true;
    if (tokenState) tokenState.hidden = true;
    if (doneState) doneState.hidden = false;

    showToast("Email confirmed. Welcome to DigiSafe, " + (data.full_name || "") + "!", "success");
    setTimeout(() => {
        window.location.href = (data.role === "admin" || data.role === "officer") ? "/admin" : "/track";
    }, 1100);
}

const verifyForm = document.getElementById("verifyForm");
if (verifyForm) {
    const emailField = document.getElementById("verifyEmail");
    const codeField = document.getElementById("verifyCode");
    const introText = document.getElementById("verifyIntroText");
    const consoleNotice = document.getElementById("consoleCodeNotice");
    const verifyBtn = document.getElementById("verifyBtn");
    const resendBtn = document.getElementById("resendBtn");

    // Carried over from sign-up (or from a login blocked for being unverified)
    // so the address does not have to be retyped on a phone keyboard.
    const pendingEmail = sessionStorage.getItem("digisafe_pending_email");
    if (pendingEmail && emailField) emailField.value = pendingEmail;

    const pendingMessage = sessionStorage.getItem("digisafe_pending_message");
    if (pendingMessage && introText) introText.textContent = pendingMessage;

    const pendingDelivery = sessionStorage.getItem("digisafe_pending_delivery");
    if (consoleNotice && (pendingDelivery === "outbox" || pendingDelivery === "failed")) {
        consoleNotice.hidden = false;
    }

    // Digits only, and never more than six - so a code pasted with spaces or a
    // stray character still lands cleanly.
    if (codeField) {
        codeField.addEventListener("input", () => {
            codeField.value = codeField.value.replace(/\D/g, "").slice(0, 6);
        });
    }

    verifyForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const email = (emailField.value || "").trim();
        const code = (codeField.value || "").trim();
        if (!email) { showToast("Please enter the email address you registered with.", "error"); emailField.focus(); return; }
        if (code.length !== 6) { showToast("The code is 6 digits long.", "error"); codeField.focus(); return; }

        verifyBtn.disabled = true;
        const originalLabel = verifyBtn.innerHTML;
        verifyBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Verifying...';
        try {
            const res = await fetch("/api/auth/verify", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email, code })
            });
            const data = await res.json();
            if (res.ok) {
                finishVerification(data);
            } else {
                showToast(data.detail || "Verification failed.", "error");
                codeField.value = "";
                codeField.focus();
                verifyBtn.disabled = false;
                verifyBtn.innerHTML = originalLabel;
            }
        } catch (err) {
            showToast("Network error: " + err.message, "error");
            verifyBtn.disabled = false;
            verifyBtn.innerHTML = originalLabel;
        }
    });

    if (resendBtn) {
        const resendLabel = resendBtn.innerHTML;
        resendBtn.addEventListener("click", async () => {
            const email = (emailField.value || "").trim();
            if (!email) { showToast("Enter your email address first.", "error"); emailField.focus(); return; }

            resendBtn.disabled = true;
            try {
                const res = await fetch("/api/auth/resend-verification", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ email })
                });
                const data = await res.json();
                if (res.ok) {
                    showToast(data.message || "A new code is on its way.", "success");
                    if (introText && data.message) introText.textContent = data.message;
                    if (consoleNotice) {
                        consoleNotice.hidden = data.delivery === "smtp";
                    }
                    // Mirror the server cooldown, so the button cannot be tapped
                    // into a 429 the person did not cause.
                    let seconds = 60;
                    const paint = () => {
                        resendBtn.innerHTML = '<i class="bi bi-hourglass-split me-1"></i> You can resend in ' + seconds + 's';
                    };
                    paint();
                    const tick = setInterval(() => {
                        seconds -= 1;
                        if (seconds <= 0) {
                            clearInterval(tick);
                            resendBtn.innerHTML = resendLabel;
                            resendBtn.disabled = false;
                        } else {
                            paint();
                        }
                    }, 1000);
                } else {
                    showToast(data.detail || "Could not resend the code.", "error");
                    resendBtn.disabled = false;
                }
            } catch (err) {
                showToast("Network error: " + err.message, "error");
                resendBtn.disabled = false;
            }
        });
    }

    // Arrived from the emailed link: exchange the token without asking for
    // anything. The token is dropped from the address bar afterwards so it is
    // not left sitting in browser history or in a shared screenshot.
    const urlToken = new URLSearchParams(window.location.search).get("token");
    if (urlToken) {
        document.getElementById("codeVerifyState").hidden = true;
        document.getElementById("tokenVerifyState").hidden = false;
        (async () => {
            try {
                const res = await fetch("/api/auth/verify-token", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ token: urlToken })
                });
                const data = await res.json();
                window.history.replaceState({}, document.title, "/verify");
                if (res.ok) {
                    finishVerification(data);
                } else {
                    document.getElementById("tokenVerifyState").hidden = true;
                    document.getElementById("codeVerifyState").hidden = false;
                    if (introText) introText.textContent = data.detail || "That link did not work. Enter your code below instead.";
                    showToast(data.detail || "That verification link did not work.", "error");
                }
            } catch (err) {
                document.getElementById("tokenVerifyState").hidden = true;
                document.getElementById("codeVerifyState").hidden = false;
                showToast("Network error: " + err.message, "error");
            }
        })();
    }
}
