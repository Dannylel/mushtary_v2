// Mushtary demo UI — vanilla JS, no build step. Talks to the FastAPI layer in api.py.

const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const DOC_TYPES = [
  ["commercial_registration", "Commercial Registration"],
  ["vat_certificate", "VAT Certificate"],
  ["brand_registration", "Brand Registration"],
  ["saudization_certificate", "Saudization Certificate"],
  ["iso_certificate", "ISO Certificate"],
  ["other", "Other"],
];

let lastHealthPromptPatch = null;
let platformCategories = {};
let lastDraftResult = null;
let reputationData = null;
let currentSession = null;
let selectedVendorTenderId = null;
const FIXED_DEMO_ACCOUNTS = { buyer: "BUY-020", vendor: "VND-001" };
const PDF_TEMPLATES = [
  ["premium_bw", "Premium B/W"],
  ["modern_bw", "Modern B/W"],
];

function selectedPdfTemplate() {
  return "premium_bw";
}

function checked(id) { return !!$(id)?.checked; }
function value(id) { return ($(id)?.value || "").trim(); }
function numberOrNull(id) {
  const raw = value(id);
  if (!raw) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

function lines(id) {
  return value(id).split(/\r?\n/).map(x => x.trim()).filter(Boolean);
}

function checkedLabels(selector) {
  return $$(selector).filter(x => x.checked).map(x => x.value.trim()).filter(Boolean);
}

function parseDelimitedRows(id, columns) {
  return lines(id).map(line => {
    const parts = line.split("|").map(x => x.trim());
    return columns.reduce((row, col, i) => {
      row[col] = parts[i] || "";
      return row;
    }, {});
  }).filter(row => Object.values(row).some(Boolean));
}

function responsibilityRows() {
  return tableRows("draftResponsibilitiesTable", ["party", "responsibilities"]).map(row => ({
    party: row.party,
    responsibilities: row.responsibilities.split(";").map(x => x.trim()).filter(Boolean),
  })).filter(row => row.party && row.responsibilities.length);
}

function addEditableRow(tableId, values = []) {
  const table = document.getElementById(tableId);
  if (!table) return;
  const headers = $$("thead th", table).slice(0, -1).map(th => th.textContent.trim());
  const row = document.createElement("tr");
  row.innerHTML = headers.map((label, index) =>
    `<td data-label="${esc(label)}"><input value="${esc(values[index] || "")}" /></td>`
  ).join("") + '<td><button type="button" class="table-remove" title="Remove row">Remove</button></td>';
  $(".table-remove", row).addEventListener("click", () => row.remove());
  $("tbody", table).appendChild(row);
}

function addTenderTableRow(tableId) {
  addEditableRow(tableId);
  const table = document.getElementById(tableId);
  $("tbody tr:last-child input", table)?.focus();
}
window.addTenderTableRow = addTenderTableRow;

function tableRows(tableId, columns) {
  const table = document.getElementById(tableId);
  if (!table) return [];
  return $$("tbody tr", table).map(row => {
    const values = $$("input", row).map(input => input.value.trim());
    return columns.reduce((item, column, index) => ({ ...item, [column]: values[index] || "" }), {});
  }).filter(row => Object.values(row).some(Boolean));
}

function replaceEditableRows(tableId, rows, columns) {
  const table = document.getElementById(tableId);
  if (!table) return;
  $("tbody", table).innerHTML = "";
  (rows || []).forEach(row => addEditableRow(tableId, columns.map(column => row?.[column] || "")));
}

function parseDocumentRequirements(id, level) {
  return checkedLabels(`${id} input[type="checkbox"]`).map(name => ({
    name,
    requirement_level: level,
    category: "Buyer selected",
    applicability: "As selected by buyer",
  }));
}

function syncDraftSubcategories() {
  const category = value("#draftCategory");
  const sub = $("#draftSubcategory");
  if (!sub) return;
  const items = platformCategories[category] || [];
  sub.innerHTML = items.map(x => `<option>${esc(x)}</option>`).join("");
}

function evaluationWeights(model) {
  const match = String(model || "").match(/(\d+)\s*\/\s*(\d+)/);
  if (!match) return [70, 30];
  return [Number(match[1]), Number(match[2])];
}

function collectDraftOverrides() {
  const evaluation_model = value("#draftEvaluationModel") || "70/30";
  const [technical_weight, financial_weight] = evaluationWeights(evaluation_model);
  const overrides = {
    tender_title: value("#draftTenderTitle") || undefined,
    tender_id: value("#draftTenderId") || undefined,
    buyer_name: value("#draftBuyerName") || undefined,
    buyer_description: value("#draftBuyerDescription") || undefined,
    category: value("#draftCategory") || undefined,
    subcategory: value("#draftSubcategory") || undefined,
    tender_type: value("#draftTenderType") || undefined,
    procurement_method: value("#draftProcurementMethod") || undefined,
    location: value("#draftLocation") || undefined,
    project_objective: value("#draftProjectObjective") || undefined,
    scope_of_work: value("#draftScope") || undefined,
    technical_requirements: value("#draftTechnicalRequirements") || undefined,
    methodology_requirements: value("#draftMethodologyRequirements") || undefined,
    deliverables: tableRows("draftDeliverablesTable", ["name", "description", "format"]),
    timeline: tableRows("draftTimelineTable", ["milestone", "date"]),
    roles_and_responsibilities: responsibilityRows(),
    issue_date: value("#draftIssueDate") || undefined,
    clarification_deadline: value("#draftClarificationDate") || undefined,
    submission_deadline: value("#draftSubmissionDate") || undefined,
    submission_time: value("#draftSubmissionTime") || undefined,
    opening_date: value("#draftOpeningDate") || undefined,
    proposal_validity_days: numberOrNull("#draftProposalValidityDays"),
    site_visit_required: checked("#draftSiteVisitRequired"),
    site_visit_date: value("#draftSiteVisitDate") || undefined,
    bid_security_required: checked("#draftBidSecurityRequired"),
    bid_security_amount_or_percentage: value("#draftBidSecurityAmount") || undefined,
    performance_bond_required: checked("#draftPerformanceBondRequired"),
    performance_bond_percentage: numberOrNull("#draftPerformanceBondPct"),
    performance_bond_validity: value("#draftPerformanceBondValidity") || undefined,
    retention_percentage: numberOrNull("#draftRetentionPct"),
    liquidated_damages_applicable: checked("#draftLiquidatedDamages"),
    liquidated_damages_rate: value("#draftLiquidatedDamagesRate") || undefined,
    estimated_value_sar: numberOrNull("#draftEstimatedValue"),
    budget_range: value("#draftBudgetRange") || undefined,
    payment_terms: value("#draftPaymentTerms") || undefined,
    eligibility_criteria: checkedLabels("#draftEligibilityCriteria input[type='checkbox']"),
    minimum_years_experience: numberOrNull("#draftMinYears"),
    minimum_similar_projects: numberOrNull("#draftMinProjects"),
    minimum_project_value_sar: numberOrNull("#draftMinProjectValue"),
    required_sector_license: value("#draftSectorLicense") || undefined,
    required_certifications: checkedLabels("#draftCertifications input[type='checkbox']"),
    blacklist_declaration_required: checked("#draftBlacklistDeclaration"),
    local_presence_required: checked("#draftLocalPresenceRequired"),
    saudization_required: checked("#draftSaudizationRequired"),
    confidentiality_required: checked("#draftConfidentialityRequired"),
    onsite_required: checked("#draftOnsiteRequired"),
    mandatory_documents: parseDocumentRequirements("#draftMandatoryDocs", "mandatory"),
    conditional_documents: parseDocumentRequirements("#draftConditionalDocs", "conditional"),
    sector_specific_documents: parseDocumentRequirements("#draftSectorDocs", "sector_specific"),
    optional_documents: parseDocumentRequirements("#draftOptionalDocs", "optional"),
    prestige_documents: parseDocumentRequirements("#draftPrestigeDocs", "prestige"),
    required_documents: [
      ...checkedLabels("#draftMandatoryDocs input[type='checkbox']"),
      ...checkedLabels("#draftConditionalDocs input[type='checkbox']"),
      ...checkedLabels("#draftSectorDocs input[type='checkbox']"),
    ],
    evaluation_model,
    technical_weight,
    financial_weight,
    minimum_score: numberOrNull("#draftMinimumScore"),
    evaluation_criteria: parseDelimitedRows("#draftEvaluationCriteria", ["name", "weight", "description"]).map(row => ({
      ...row,
      weight: Number(row.weight) || 0,
    })),
    mandatory_disqualification_criteria: checkedLabels("#draftDisqualificationCriteria input[type='checkbox']"),
    technical_evaluation_parameters: lines("#draftTechnicalEvalParams"),
    financial_evaluation_parameters: lines("#draftFinancialEvalParams"),
    submission_method: value("#draftSubmissionMethod") || undefined,
    proposal_format: value("#draftProposalFormat") || undefined,
    contract_duration: value("#draftContractDuration") || undefined,
    warranty_duration: value("#draftWarrantyDuration") || undefined,
    language_requirements: value("#draftLanguageRequirements") || undefined,
    submission_controls: {
      platform_submission_only: checked("#draftPlatformOnly"),
      separate_technical_commercial: checked("#draftSeparateTechCommercial"),
      max_file_size_mb: numberOrNull("#draftMaxFileSize"),
      resubmission_allowed_before_deadline: checked("#draftResubmissionAllowed"),
      lock_after_deadline: checked("#draftLockAfterDeadline"),
      late_submission_allowed: checked("#draftLateSubmissionAllowed"),
      completeness_check_required: checked("#draftCompletenessCheck"),
      timestamp_is_official: checked("#draftTimestampOfficial"),
      technical_file_format: value("#draftTechnicalFileFormat") || undefined,
      commercial_file_format: value("#draftCommercialFileFormat") || undefined,
    },
  };

  [
    "project_objective",
    "technical_requirements",
    "methodology_requirements",
  ].forEach(field => {
    if (!overrides[field]) {
      delete overrides[field];
    }
  });

  [
    "deliverables",
    "timeline",
    "roles_and_responsibilities",
    "evaluation_criteria",
    "technical_evaluation_parameters",
    "financial_evaluation_parameters",
  ].forEach(field => {
    if (Array.isArray(overrides[field]) && overrides[field].length === 0) {
      delete overrides[field];
    }
  });

  return overrides;
}

function missingRequiredDraftFields() {
  const missing = [
    ["#draftTenderTitle", "Tender title"],
    ["#draftCategory", "Category"],
    ["#draftSubcategory", "Subcategory"],
    ["#draftTenderType", "Tender type"],
    ["#draftProcurementMethod", "Procurement method"],
    ["#draftLocation", "Location"],
    ["#draftIssueDate", "Issue date"],
    ["#draftSiteVisitDate", "Site visit date"],
    ["#draftSubmissionDate", "Submission deadline date"],
    ["#draftSubmissionTime", "Submission deadline time"],
    ["#draftClarificationDate", "Clarification deadline"],
    ["#draftOpeningDate", "Opening date"],
    ["#draftProposalValidityDays", "Proposal validity days"],
    ["#draftEvaluationModel", "Evaluation split"],
    ["#draftMinimumScore", "Minimum technical score"],
    ["#draftContractDuration", "Project duration"],
    ["#draftWarrantyDuration", "Warranty duration"],
    ["#draftScope", "Scope of work"],
    ["#draftPaymentTerms", "Payment terms"],
    ["#draftBidSecurityAmount", "Bid security amount"],
    ["#draftPerformanceBondPct", "Performance bond percentage"],
    ["#draftPerformanceBondValidity", "Performance bond validity"],
    ["#draftRetentionPct", "Retention percentage"],
    ["#draftLiquidatedDamagesRate", "Liquidated damages rate"],
    ["#draftProposalFormat", "Proposal format"],
    ["#draftSubmissionMethod", "Submission method"],
    ["#draftTechnicalFileFormat", "Technical file format"],
    ["#draftCommercialFileFormat", "Commercial file format"],
    ["#draftLanguageRequirements", "Language requirements"],
    ["#draftMaxFileSize", "Max file size"],
  ].filter(([id]) => !value(id)).map(([, label]) => label);

  [
    ["#draftEstimatedValue", "Estimated value"],
    ["#draftBudgetRange", "Budget range"],
    ["#draftMinYears", "Minimum years experience"],
    ["#draftMinProjects", "Minimum similar projects"],
    ["#draftMinProjectValue", "Minimum project value"],
    ["#draftSectorLicense", "Required sector license"],
  ].forEach(([id, label]) => {
    if (!value(id)) missing.push(label);
  });

  [
    ["#draftEligibilityCriteria input[type='checkbox']", "Eligibility criteria"],
    ["#draftCertifications input[type='checkbox']", "Required certifications"],
    ["#draftMandatoryDocs input[type='checkbox']", "Mandatory documents"],
    ["#draftConditionalDocs input[type='checkbox']", "Conditional documents"],
    ["#draftSectorDocs input[type='checkbox']", "Sector-specific documents"],
    ["#draftDisqualificationCriteria input[type='checkbox']", "Mandatory disqualification criteria"],
  ].forEach(([selector, label]) => {
    if (!checkedLabels(selector).length) missing.push(label);
  });

  return missing;
}

function isoDatePlus(days) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

function setDefaultDraftDates() {
  const defaults = [
    ["#draftIssueDate", isoDatePlus(0)],
    ["#draftSiteVisitDate", isoDatePlus(6)],
    ["#draftClarificationDate", isoDatePlus(10)],
    ["#draftSubmissionDate", isoDatePlus(28)],
    ["#draftOpeningDate", isoDatePlus(28)],
  ];
  defaults.forEach(([id, date]) => {
    const el = $(id);
    if (el && !el.value) el.value = date;
  });
}

// ── Navigation ────────────────────────────────────────────────────────────────
function show(view) {
  $$(".nav-item").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  $$(".view").forEach(v => v.classList.toggle("active", v.id === `view-${view}`));
  window.scrollTo({ top: 0 });
  if (view === "vendor-feed") loadVendorFeed();
  if (view === "draft") loadSavedTenders();
  if (view === "buyer-proposals") loadBuyerProposalComparison();
}
$$(".nav-item").forEach(b => b.addEventListener("click", () => show(b.dataset.view)));
$$("[data-go]").forEach(c => c.addEventListener("click", () => show(c.dataset.go)));

// ── Live activity console ─────────────────────────────────────────────────────
// Demo sign-in
function sessionAccountId() {
  return currentSession?.account?.account_id || "";
}

function sessionRole() {
  return currentSession?.role || "";
}

function setSignedInBuyerFields() {
  if (sessionRole() !== "buyer") return;
  const account = currentSession.account || {};
  if (!currentSession.current_tender_id && account.account_id) {
    currentSession.current_tender_id = `TND-${account.account_id.replace("BUY-", "BUY")}-${new Date().toISOString().slice(0, 10).replace(/-/g, "")}`;
    localStorage.setItem("mushtaryDemoSession", JSON.stringify(currentSession));
  }
  const tenderId = $("#draftTenderId");
  const buyerName = $("#draftBuyerName");
  const buyerDescription = $("#draftBuyerDescription");
  if (tenderId) tenderId.value = currentSession.current_tender_id || "";
  if (buyerName) buyerName.value = account.name || buyerName.value;
  if (buyerDescription && account.profile_summary) buyerDescription.value = account.profile_summary;
}

function updateRoleNavigation() {
  const role = sessionRole();
  const buyerOnly = ["draft", "extract", "evaluate", "buyer-proposals"];
  const vendorOnly = ["vendor-feed"];
  $$("[data-role-view]").forEach(el => {
    el.style.display = !role || el.dataset.roleView === role ? "" : "none";
  });
  $$(".nav-item, [data-go]").forEach(el => {
    const view = el.dataset.view || el.dataset.go;
    let visible = true;
    if (role === "vendor" && buyerOnly.includes(view)) visible = false;
    if (role === "buyer" && vendorOnly.includes(view)) visible = false;
    el.style.display = visible ? "" : "none";
  });
}

function renderSession() {
  const gate = $("#signinGate");
  if (gate) gate.classList.toggle("hidden", !!currentSession);
  const account = currentSession?.account || {};
  $("#sessionName").textContent = account.name || "Not signed in";
  $("#sessionMeta").textContent = currentSession
    ? `${currentSession.role.toUpperCase()} - ${account.account_id || ""} - ${account.badge || account.bri?.level || account.vri?.level || ""}`
    : "Choose buyer or vendor";
  updateRoleNavigation();
  setSignedInBuyerFields();
}

async function signInRandom(role) {
  const data = await fetch("/api/session/account", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role, account_id: FIXED_DEMO_ACCOUNTS[role] }),
  }).then(r => r.json());
  setDemoSession(data.session);
  show(role === "vendor" ? "vendor-feed" : "overview");
}

function setDemoSession(session) {
  currentSession = session;
  localStorage.setItem("mushtaryDemoSession", JSON.stringify(currentSession));
  if (currentSession.role === "buyer") localStorage.setItem("mushtaryLastBuyerSession", JSON.stringify(currentSession));
  renderSession();
}

async function signInSelected(role) {
  const select = role === "buyer" ? $("#signinBuyerSelect") : $("#signinVendorSelect");
  const account_id = select?.value;
  if (!account_id) return;
  const response = await fetch("/api/session/account", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role, account_id }),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "Could not select demo account.");
  setDemoSession(data.session);
  show(role === "vendor" ? "vendor-feed" : "overview");
}

async function loadDemoAccounts() {
  const [buyersResult, vendorsResult] = await Promise.all([
    fetch("/api/accounts/buyers").then(r => r.json()),
    fetch("/api/accounts/vendors").then(r => r.json()),
  ]);
  const fill = (select, accounts, label) => {
    if (!select) return;
    select.innerHTML = `<option value="">Select ${label}…</option>` + (accounts || []).map(account =>
      `<option value="${esc(account.account_id)}">${esc(account.account_id)} — ${esc(account.name)}</option>`
    ).join("");
  };
  fill($("#signinBuyerSelect"), buyersResult.buyers, "buyer");
  fill($("#signinVendorSelect"), vendorsResult.vendors, "vendor");
}

async function resetDemoState() {
  if (!confirm("Reset demo jobs, tenders, and proposals? Persisted AI audit records will remain.")) return;
  const response = await fetch("/api/demo/reset", { method: "POST" });
  const data = await response.json();
  if (!response.ok) {
    alert(data.detail || "Could not reset demo state.");
    return;
  }
  lastDraftResult = null;
  selectedVendorTenderId = null;
  alert(data.message || "Demo state reset.");
  show(sessionRole() === "vendor" ? "vendor-feed" : "overview");
}

function returnToLastBuyer() {
  const saved = localStorage.getItem("mushtaryLastBuyerSession");
  if (saved) {
    currentSession = JSON.parse(saved);
    localStorage.setItem("mushtaryDemoSession", JSON.stringify(currentSession));
    renderSession();
    show("buyer-proposals");
    return;
  }
  signInRandom("buyer").then(() => show("buyer-proposals"));
}

function switchToVendorSandbox() {
  if (sessionRole() === "vendor") {
    show("vendor-feed");
    return;
  }
  signInRandom("vendor");
}

function restoreSession() {
  try {
    currentSession = JSON.parse(localStorage.getItem("mushtaryDemoSession") || "null");
  } catch {
    currentSession = null;
  }
  renderSession();
}

$("#signinBuyerBtn")?.addEventListener("click", () => signInRandom("buyer"));
$("#signinVendorBtn")?.addEventListener("click", () => signInRandom("vendor"));
$("#signinSelectedBuyerBtn")?.addEventListener("click", () => signInSelected("buyer").catch(e => alert(e.message)));
$("#signinSelectedVendorBtn")?.addEventListener("click", () => signInSelected("vendor").catch(e => alert(e.message)));
$("#switchSessionBtn")?.addEventListener("click", () => {
  localStorage.removeItem("mushtaryDemoSession");
  currentSession = null;
  renderSession();
});
$("#resetDemoBtn")?.addEventListener("click", resetDemoState);

const consoleEl = $("#console"), consoleBody = $("#consoleBody"),
      consoleDot = $("#consoleDot"), consoleSub = $("#consoleSub");
let actLast = 0, actTimer = null, actStopAt = null;
const labelClass = {};
let labelSeq = 0;

$("#consoleHead").addEventListener("click", () => consoleEl.classList.toggle("collapsed"));

function consoleOpen() { consoleEl.classList.remove("collapsed"); }

function lblCls(label) {
  if (!(label in labelClass)) labelClass[label] = `lbl-${labelSeq++ % 6}`;
  return labelClass[label];
}

function appendEvent(ev) {
  const nearBottom = consoleBody.scrollHeight - consoleBody.scrollTop - consoleBody.clientHeight < 60;
  if (ev.kind === "token") {
    // Append to the last block if it belongs to the same agent; else start a new block.
    let block = consoleBody.lastElementChild;
    if (!block || !block.classList.contains("con-block") || block.dataset.label !== ev.label) {
      block = document.createElement("div");
      block.className = "con-block";
      block.dataset.label = ev.label;
      block.innerHTML = `<span class="con-label ${lblCls(ev.label)}">${esc(ev.label)}</span><div class="con-text"></div>`;
      consoleBody.appendChild(block);
    }
    $(".con-text", block).textContent += ev.text;
  } else if (ev.kind === "info") {
    const line = document.createElement("div");
    line.className = "con-info";
    line.textContent = `[${ev.label}] ${ev.text}`;
    consoleBody.appendChild(line);
  } else { // start / end
    const line = document.createElement("div");
    line.className = "con-meta";
    line.textContent = ev.kind === "start" ? `▶ ${ev.label} started writing…` : `✓ ${ev.label} ${ev.text}`;
    consoleBody.appendChild(line);
  }
  if (nearBottom) consoleBody.scrollTop = consoleBody.scrollHeight;
}

async function pollActivity() {
  try {
    const data = await fetch(`/api/activity?since=${actLast}`).then(r => r.json());
    data.events.forEach(appendEvent);
    if (data.events.length) actLast = data.last_id;
  } catch { /* server briefly unreachable — keep polling */ }
  if (actStopAt && Date.now() > actStopAt) {
    clearInterval(actTimer); actTimer = null;
    consoleDot.classList.remove("live");
    consoleSub.textContent = "idle";
  }
}

function activityStart(what) {
  actStopAt = null;
  consoleDot.classList.add("live");
  consoleSub.textContent = `running: ${what}`;
  consoleOpen();
  if (!actTimer) actTimer = setInterval(pollActivity, 1000);
}
function activityStop() { actStopAt = Date.now() + 4000; } // drain the tail, then idle

// ── Polling helper for background jobs ──────────────────────────────────────────
async function pollJob(jobId, { onTick, intervalMs = 2000 } = {}) {
  const start = Date.now();
  while (true) {
    const job = await fetch(`/api/jobs/${jobId}`).then(r => r.json());
    const secs = Math.floor((Date.now() - start) / 1000);
    if (onTick) onTick(secs);
    if (job.status === "SUCCESS") return job.result;
    if (job.status === "FAILURE") throw new Error(job.error || "Job failed");
    await new Promise(r => setTimeout(r, intervalMs));
  }
}

function loaderHTML(main, sub) {
  return `<div class="loader">
    <div class="spinner"></div>
    <div><div class="loader-main">${esc(main)}</div>
    <div class="loader-sub">${esc(sub)} · <span class="loader-timer" data-timer>0s</span></div></div>
  </div>`;
}
function errorHTML(msg) { return `<div class="error-box"><b>Something went wrong.</b><br>${esc(msg)}</div>`; }
function setTimer(container, secs) {
  const t = $("[data-timer]", container);
  if (t) t.textContent = `${secs}s`;
}

async function runJob({ start, target, loadMain, loadSub, render }) {
  const box = $(target);
  box.innerHTML = loaderHTML(loadMain, loadSub);
  activityStart(loadMain);
  try {
    const { job_id } = await start();
    const result = await pollJob(job_id, { onTick: s => setTimer(box, s) });
    box.innerHTML = render(result);
    box.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    box.innerHTML = errorHTML(e.message);
  } finally {
    activityStop();
  }
}

// ── Rendering primitives ─────────────────────────────────────────────────────────
function block(num, title, body) {
  return `<div class="section-block">
    <div class="sb-head"><span class="num">${num}</span>${esc(title)}</div>
    <div class="sb-body prose">${body}</div>
  </div>`;
}
function ul(items, mapFn) {
  const arr = (items || []).filter(Boolean);
  if (!arr.length) return "";
  return `<ul class="ul">${arr.map(i => `<li>${mapFn ? mapFn(i) : esc(i)}</li>`).join("")}</ul>`;
}
function sub(title, body) {
  if (!body) return "";
  return `<h4>${esc(title)}</h4>${body}`;
}
function para(text) { return text ? `<p>${esc(text)}</p>` : ""; }
function kv(rows) {
  const filled = rows.filter(([, v]) => v !== null && v !== undefined && v !== "");
  if (!filled.length) return "";
  return `<dl class="kv">${filled.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>`;
}
function yesNo(v) { return v === true ? "Yes" : v === false ? "No" : v ?? ""; }
function docList(title, docs) {
  if (!docs || !docs.length) return "";
  const items = docs.map(d => {
    const meta = [d.category, d.applicability, d.issuing_authority].filter(Boolean).join(" · ");
    return `<div class="doc-item"><b>${esc(d.name)}</b><span>${esc(meta)}${d.notes ? " — " + esc(d.notes) : ""}</span></div>`;
  }).join("");
  return `<h4>${esc(title)}</h4>${items}`;
}

// ── DRAFT: render the full 18-section tender (mirrors the PDF layout) ───────────
function scoreNum(value) {
  const n = Number(value);
  return Number.isFinite(n) ? Math.round(n) : null;
}

function findHealthAgent(ti, words) {
  const agents = ti.health_agents || [];
  return agents.find(a => {
    const text = `${a.agent_name || ""} ${a.role || ""}`.toLowerCase();
    return words.some(w => text.includes(w));
  }) || null;
}

function buildAITenderCommittee(ti) {
  if (ti.ai_tender_committee && Array.isArray(ti.ai_tender_committee.agents)) {
    const committee = ti.ai_tender_committee;
    return {
      rows: committee.agents.map(a => ({
        agent: a.agent_name || "AI Agent",
        score: scoreNum(a.score),
        focus: a.focus || a.summary || "",
        summary: a.summary || "",
        recommendation: a.recommendation || "",
      })),
      finalScore: scoreNum(committee.final_score),
      recommendation: committee.final_recommendation || "Buyer review required before publication.",
      priorities: committee.improvement_priorities || [],
      reasoning: committee.committee_reasoning || [],
    };
  }

  const technical = findHealthAgent(ti, ["scope", "technical", "clarity"]);
  const commercial = findHealthAgent(ti, ["commercial"]);
  const compliance = findHealthAgent(ti, ["compliance"]);
  const delivery = findHealthAgent(ti, ["scope", "deliverable", "milestone", "timeline"]);
  const risk = findHealthAgent(ti, ["participation", "risk", "vendor"]);

  const rows = [
    ["Technical Agent", scoreNum(ti.scope_clarity ?? technical?.score), "Scope depth, technical clarity, acceptance criteria"],
    ["Commercial Agent", scoreNum(ti.commercial_clarity ?? commercial?.score), "Pricing clarity, payment terms, commercial packaging"],
    ["Compliance Agent", scoreNum(ti.compliance_readiness ?? compliance?.score), "Documents, eligibility, governance, approval controls"],
    ["Delivery Agent", scoreNum(delivery?.score ?? ti.scope_clarity), "Deliverables, milestones, implementation readiness"],
    ["Risk Agent", scoreNum(risk?.score ?? ti.vendor_participation_score), "Vendor question risk and participation confidence"],
  ].map(([agent, score, focus]) => ({ agent, score, focus }));

  return {
    rows,
    finalScore: scoreNum(ti.tender_quality_score),
    recommendation: ti.publish_readiness || ti.improvement_summary || "Buyer review required before publication.",
    priorities: [],
    reasoning: [],
  };
}

function renderAITenderCommittee(committee) {
  const cards = committee.rows.map(r => `
    <div class="committee-card">
      <div class="committee-card-head">
        <b>${esc(r.agent)}</b>
        <span class="score-pill">${esc(r.score ?? "—")}</span>
      </div>
      <div class="committee-focus">${esc(r.focus)}</div>
      ${r.recommendation ? `<p>${esc(r.recommendation)}</p>` : ""}
    </div>`).join("");
  return `<div class="committee-board">
    ${cards}
    <div class="committee-card final">
      <div class="committee-card-head">
        <b>Final AI Recommendation</b>
        <span class="score-pill">${esc(committee.finalScore ?? "—")}</span>
      </div>
      <div class="committee-focus">${esc(committee.recommendation)}</div>
    </div>
  </div>
  ${committee.priorities && committee.priorities.length ? sub("Improvement Priorities", ul(committee.priorities)) : ""}
  ${committee.reasoning && committee.reasoning.length ? sub("Committee Reasoning", ul(committee.reasoning)) : ""}`;
}

function scoreLabel(score) {
  const n = scoreNum(score);
  if (n === null) return "Pending";
  if (n >= 85) return "Strong";
  if (n >= 70) return "Review";
  return "At Risk";
}

function complianceStatus(ti, committee) {
  const compliance = scoreNum(ti.compliance_readiness);
  const lowCommittee = (committee.rows || []).some(r => scoreNum(r.score) !== null && scoreNum(r.score) < 70);
  if (compliance === null) return "Pending Review";
  if (compliance >= 85 && !lowCommittee) return "Likely Compliant";
  if (compliance >= 70) return "Buyer Review Required";
  return "Compliance Risk";
}

function probabilityOfSuccess(ti, committee) {
  const finalScore = scoreNum(committee.finalScore ?? ti.tender_quality_score);
  const participation = scoreNum(ti.vendor_participation_score);
  const base = finalScore ?? scoreNum(ti.tender_quality_score) ?? 75;
  const adjusted = Math.round((base * 0.7) + ((participation ?? base) * 0.3));
  return Math.max(0, Math.min(100, adjusted));
}

function metricCard(label, value, subtext = "") {
  return `<div class="intel-metric">
    <span>${esc(label)}</span>
    <b>${esc(value ?? "—")}</b>
    ${subtext ? `<small>${esc(subtext)}</small>` : ""}
  </div>`;
}

function renderAIRecommendationLayer(ti, committee) {
  const finalScore = scoreNum(committee.finalScore ?? ti.tender_quality_score);
  const success = probabilityOfSuccess(ti, committee);
  return `<div class="ai-reco-layer">
    <div class="ai-reco-head">
      <div>
        <h4>Tender Revision Recommendation</h4>
        <p>This assesses the tender draft, not vendors. It turns committee findings into revision priorities before buyer approval.</p>
      </div>
      <span class="badge ok dot">Enabled</span>
    </div>
    <div class="reco-grid">
      ${metricCard("Technical Readiness", `${ti.scope_clarity ?? "-"}/100`, "Scope, specifications, acceptance")}
      ${metricCard("Commercial Readiness", `${ti.commercial_clarity ?? "-"}/100`, "Pricing, payment, proposal controls")}
      ${metricCard("Compliance Readiness", `${ti.compliance_readiness ?? "-"}/100`, "Documents, eligibility, governance")}
      ${metricCard("Delivery Readiness", `${committee.rows?.find(r => r.agent === "Delivery Agent")?.score ?? "-"}/100`, "Deliverables, timeline, handover")}
      ${metricCard("Compliance Status", complianceStatus(ti, committee))}
      ${metricCard("Probability of Success", `${success}%`, scoreLabel(success))}
      ${metricCard("Revision Priority", finalScore !== null ? `${finalScore}/100` : "Pending", scoreLabel(finalScore))}
    </div>
  </div>`;
}

function renderTenderIntelligencePanel(ti) {
  const committee = buildAITenderCommittee(ti);
  const finalScore = scoreNum(committee.finalScore ?? ti.tender_quality_score);
  return `<div class="intel-panel">
    <div class="intel-hero">
      <div>
        <div class="intel-eyebrow">Mushtarry Tender Intelligence</div>
        <h2>${esc(finalScore !== null ? `${finalScore}/100` : "Pending")}</h2>
        <p>${esc(committee.recommendation || ti.publish_readiness || "Buyer review required before publication.")}</p>
      </div>
      <span class="badge draft dot">Advisory · Buyer decides</span>
    </div>
    <div class="intel-grid">
      ${metricCard("Tender Quality Score", `${ti.tender_quality_score ?? "—"}/100`, ti.publish_readiness || "")}
      ${metricCard("Scope Clarity", `${ti.scope_clarity ?? "—"}%`)}
      ${metricCard("Commercial Clarity", `${ti.commercial_clarity ?? "—"}%`)}
      ${metricCard("Compliance Readiness", `${ti.compliance_readiness ?? "—"}%`)}
      ${metricCard("Risk of Vendor Questions", ti.risk_of_vendor_questions || "—")}
      ${metricCard("Estimated Vendor Participation", ti.estimated_vendor_participation || "—")}
    </div>
    ${renderAIRecommendationLayer(ti, committee)}
    <div class="intel-section">
      <div class="intel-section-head">
        <h4>AI Tender Committee</h4>
        <span>Premium decision-support preview</span>
      </div>
      ${renderAITenderCommittee(committee)}
    </div>
  </div>`;
}

function buildHealthPromptPatch(form, ti) {
  if (!ti || ti.tender_quality_score == null) return null;
  const title = form.tender_title || "Tender";
  const baseScope = form.scope_of_work || form.project_objective || "";
  const committee = buildAITenderCommittee(ti);
  const findings = (ti.findings || [])
    .filter(f => ["high", "medium"].includes(String(f.severity || "").toLowerCase()))
    .slice(0, 6);
  const missing = (ti.missing_or_weak_requirements || []).slice(0, 6);
  const recommendations = findings.map(f => f.recommendation).filter(Boolean);
  const weakAgents = committee.rows
    .filter(r => r.score !== null && r.score < 90)
    .map(r => `- Improve ${r.agent}: ${r.score}/100 (${r.focus}).`);
  const patchLines = [
    "AI Tender Committee evaluation to address before regenerating:",
    ...committee.rows.map(r => `- ${r.agent}: ${r.score ?? "not scored"}/100 - ${r.focus}`),
    `- Final AI Recommendation: ${committee.finalScore ?? "not scored"}/100`,
    "",
    "Priority improvements from the committee:",
    ...(weakAgents.length ? weakAgents : ["- Maintain current committee strengths while tightening tender clarity."]),
    ...(committee.priorities || []).map(x => `- ${x}`),
    ...missing.map(x => `- Add/clarify: ${x}`),
    ...recommendations.map(x => `- ${x}`),
  ];

  return {
    projectName: title,
    visibleScopeText: baseScope || `Scope of work for ${title}.`,
    editScopeText: [
      baseScope || `Scope of work for ${title}.`,
      "",
      patchLines.join("\n"),
      "",
      "Keep the original buyer intent. Use the AI Tender Committee evaluation to improve the tender draft, especially weaker technical, commercial, compliance, delivery, and risk signals. Do not rewrite unrelated sections unless needed.",
    ].join("\n"),
  };
}

function applyHealthPromptPatch() {
  if (!lastDraftResult || !lastDraftResult.artifact) return;
  runJob({
    target: "#draftResult",
    loadMain: "Editing tender with AI committee feedback...",
    loadSub: "Applying committee priorities to the existing tender draft and regenerating the PDF",
    start: () => fetch("/api/jobs/improve-tender", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        artifact: lastDraftResult.artifact,
        file_id: lastDraftResult.file_id,
        template: selectedPdfTemplate(),
        review_prompt: lastHealthPromptPatch?.editScopeText || "Apply the AI Tender Committee findings to improve this existing tender while preserving buyer-provided facts.",
      }),
    }).then(r => r.json()),
    render: renderDraft,
  });
}
window.applyHealthPromptPatch = applyHealthPromptPatch;

function renderDraft(result) {
  lastDraftResult = result;
  const artifact = result.artifact || {};
  const o = artifact.output || {};
  const form = artifact.input_snapshot || {};   // the buyer form — source of buyer-stated facts
  const fid = result.file_id;
  const activeTemplate = result.template || selectedPdfTemplate();

  const meta = o.metadata || {};
  const ds = o.tender_data_sheet || {};
  const intro = o.introduction || {};
  const ins = o.instructions_to_bidders || {};
  const award = o.award_and_contract || {};
  const pf = o.proposal_format || {};
  const ov = o.project_overview || {};
  const obj = o.objectives || {};
  const scope = o.scope_of_work || {};
  const dels = o.deliverables || {};
  const tl = o.timeline || {};
  const team = o.team_requirements || {};
  const terms = o.general_terms || {};
  const ev = o.evaluation_criteria || {};
  const pay = o.payment_terms || {};
  const ti = o.tender_intelligence || {};
  const consistency = o.consistency_report || {};

  const sections = [];

  if (consistency.status) {
    const issues = (consistency.findings || []).map(item => `<li><b>${esc(item.area || "Consistency")}</b> — ${esc(item.issue || "Review required")}</li>`).join("");
    sections.push(block("✓", "Consistency & Publication Gate",
      `<p><b>${esc(consistency.status)}</b> · ${esc(consistency.analysis_mode || "deterministic")}</p>` +
      (consistency.repairs_applied?.length ? `<p class="muted2">Applied ${esc(consistency.repairs_applied.length)} buyer-fact reconciliation(s).</p>` : "") +
      (issues ? `<ul class="ul">${issues}</ul>` : "<p>No material conflicts found.</p>")));
  }

  if (ti.tender_quality_score != null) {
    lastHealthPromptPatch = buildHealthPromptPatch(form, ti);
    const findings = (ti.findings || []).map(f => {
      const head = [f.area, f.severity].filter(Boolean).join(" · ");
      return `<b>${esc(head)}</b>${f.issue ? " — " + esc(f.issue) : ""}${f.evidence ? "<br><span class='muted2'>Evidence: " + esc(f.evidence) + "</span>" : ""}${f.recommendation ? "<br><span class='muted2'>Recommendation: " + esc(f.recommendation) + "</span>" : ""}`;
    });
    const healthAgents = (ti.health_agents || []).map(a =>
      `<b>${esc(a.agent_name || "Health Agent")}: ${esc(a.score ?? "—")}/100</b><br>` +
      `<span class="muted2">${esc(a.role || "")}</span>` +
      `${a.summary ? `<p style="margin:6px 0 0">${esc(a.summary)}</p>` : ""}` +
      sub("Reasoning", ul(a.reasoning_summary || [])) +
      ul(a.signals || [])
    );
    sections.push(renderTenderIntelligencePanel(ti));
    sections.push(block("AI", "AI Review Detail",
      sub("AI Review Summary", para(ti.improvement_summary)) +
      sub("Committee Reasoning", ul(ti.committee_reasoning)) +
      sub("Strengths", ul(ti.strengths)) +
      sub("Findings and Recommended Improvements", ul(findings, x => x)) +
      sub("Missing or Weak Requirements", ul(ti.missing_or_weak_requirements)) +
      `<div class="toolbar" style="margin-top:14px"><button class="btn ghost" onclick="applyHealthPromptPatch()">Edit This Tender With AI Committee Feedback</button></div>`
    ));
  }

  // 1. Tender Data Sheet
  sections.push(block(1, "Tender Data Sheet", kv([
    ["Tender Title", ds.tender_title], ["Tender Reference", ds.tender_reference],
    ["Buyer Entity", ds.buyer_entity], ["Procurement Category", ds.procurement_category],
    ["Tender Type", ds.tender_type], ["Procurement Method", ds.procurement_method],
    ["Submission Method", ds.submission_method], ["Issue Date", ds.issue_date],
    ["Site Visit", ds.site_visit], ["Clarification Deadline", ds.clarification_deadline],
    ["Submission Deadline", ds.submission_deadline], ["Opening Date", ds.opening_date],
    ["Proposal Validity", ds.proposal_validity], ["Bid Security", ds.bid_security],
    ["Performance Bond", ds.performance_bond], ["Contract Duration", ds.contract_duration],
    ["Warranty Duration", ds.warranty_duration], ["Language", ds.language],
    ["Evaluation Model", ds.evaluation_model], ["Minimum Technical Score", ds.minimum_technical_score],
  ])));

  // 2. Introduction
  sections.push(block(2, "Introduction",
    sub("About the Organisation", para(intro.about_organization)) +
    sub("Background", para(intro.background)) +
    sub("Purpose of this RFP", para(intro.purpose_of_rfp))));

  // 3. Instructions to Bidders
  const sc = ins.submission_controls || {};
  sections.push(block(3, "Instructions to Bidders",
    sub("Submission Rules", ul(ins.submission_rules)) +
    sub("Timetable", kv([
      ["RFP Issue Date", (ins.timetable || {}).issue_date],
      ["Clarifications Deadline", (ins.timetable || {}).clarifications_deadline],
      ["Submission Deadline", (ins.timetable || {}).submission_deadline],
    ])) +
    sub("Clarifications", para(ins.clarifications_process)) +
    sub("Proposal Validity", para(ins.proposal_validity_days ? `Proposals must remain valid for ${ins.proposal_validity_days} days from the closing date.` : "")) +
    sub("Confidentiality", para(ins.confidentiality_statement)) +
    sub("Conflict of Interest", para(ins.conflict_of_interest_policy)) +
    sub("Cancellation Rights", para(ins.cancellation_rights)) +
    sub("Platform Submission Controls", kv([
      ["Platform Submission Only", yesNo(sc.platform_submission_only)],
      ["Separate Technical / Commercial", yesNo(sc.separate_technical_commercial)],
      ["Technical File Format", sc.technical_file_format],
      ["Commercial File Format", sc.commercial_file_format],
      ["Maximum File Size", sc.max_file_size_mb ? `${sc.max_file_size_mb} MB` : ""],
      ["Resubmission Before Deadline", yesNo(sc.resubmission_allowed_before_deadline)],
      ["Late Submission Allowed", yesNo(sc.late_submission_allowed)],
    ]))));

  // 4. Award & Contract
  sections.push(block(4, "Award and Contract",
    sub("Evaluation Process", para(award.evaluation_process)) +
    sub("Negotiation Policy", para(award.negotiation_policy)) +
    sub("Award Rules", para(award.award_rules)) +
    sub("Bid Security", para(award.bid_security)) +
    sub("Performance Bond", para(award.performance_bond_text)) +
    sub("Saudization Requirements", para(award.saudization_requirements))));

  // 5. Vendor Document Requirements
  sections.push(block(5, "Vendor Document Requirements",
    sub("Document Governance Rules", ul(award.vendor_document_rules)) +
    sub("Documents Required for this Tender", ul(award.statutory_documents_required)) +
    docList("Mandatory Documents", award.mandatory_documents) +
    docList("Conditional Documents", award.conditional_documents) +
    docList("Sector-Specific Documents", award.sector_specific_documents) +
    docList("Optional Capability Documents", award.optional_documents)));

  // 6. Proposal Packaging & Format — the financial/commercial requirements live here
  const tp = pf.technical_proposal || {}, cp = pf.commercial_proposal || {};
  sections.push(block(6, "Proposal Packaging and Format",
    para(pf.submission_method) +
    sub("Technical Proposal — Required Sections", kv([["File Naming", tp.file_naming_convention]]) + ul(tp.required_sections)) +
    sub("Commercial Proposal — Pricing Requirements", kv([
      ["File Naming", cp.file_naming_convention],
      ["Accepted Currencies", (cp.accepted_currencies || []).join(", ")],
    ]) + ul(cp.pricing_requirements))));

  // 7. Project Overview
  sections.push(block(7, "Project Overview",
    sub("Introduction", para(ov.project_introduction)) +
    sub("Background", para(ov.background)) +
    sub("Context", para(ov.context))));

  // 8. Objectives
  sections.push(block(8, "Objectives",
    sub("Business Goals", ul(obj.business_goals)) +
    sub("Expected Outcomes", ul(obj.expected_outcomes)) +
    sub("KPIs", ul(obj.kpis))));

  // 9. Scope of Work + buyer-specified technical requirements
  const cats = (scope.categories || []).map(c =>
    sub(c.name, para(c.description) + ul(c.requirements))).join("");
  const phases = (scope.phases || []).map(p =>
    sub(p.phase, ul(p.activities))).join("");
  sections.push(block(9, "Scope of Work",
    cats +
    sub("Technical Requirements (buyer-specified)", para(form.technical_requirements)) +
    sub("Methodology Requirements", para(form.methodology_requirements)) +
    (phases ? `<h4 style="margin-top:18px">Execution Phases</h4>${phases}` : "") +
    sub("General Requirements", ul(scope.general_requirements))));

  // 10. Deliverables
  const delItems = `<table class="draft-data-table"><thead><tr><th>Deliverable</th><th>Description / acceptance output</th><th>Format</th><th>Deadline</th></tr></thead><tbody>${(dels.deliverables || []).map(d =>
    `<tr><td><b>${esc(d.name)}</b></td><td>${esc(d.description || "-")}</td><td>${esc(d.format || "-")}</td><td>${esc(d.deadline_note || "-")}</td></tr>`).join("")}</tbody></table>`;
  const tiers = (dels.escalation_tiers || []).map(t =>
    `<div class="milestone-row"><span>${esc(t.level)}</span><span class="muted2">${esc(t.trigger_delay)}</span><span>${esc(t.contact_role)}</span></div>`).join("");
  sections.push(block(10, "Deliverables",
    sub("Work Order Process", ul(dels.work_order_process)) +
    sub("Required Deliverables", delItems) +
    sub("Approval Process", para(dels.approval_process)) +
    sub("Reporting Requirements", ul(dels.reporting_requirements)) +
    sub("Escalation Matrix", tiers)));

  // 11. Timeline
  const miles = `<table class="draft-data-table"><thead><tr><th>Phase</th><th>Milestone</th><th>Target date / timing</th></tr></thead><tbody>${(tl.milestones || []).map(m =>
    `<tr><td>${esc(m.phase || "-")}</td><td><b>${esc(m.milestone)}</b></td><td>${esc(m.target_date)}</td></tr>`).join("")}</tbody></table>`;
  sections.push(block(11, "Timeline",
    para(tl.total_duration) +
    sub("Project Phases", ul(tl.project_phases)) +
    sub("Key Milestones", miles)));

  // 12. Team Requirements
  const roles = (team.roles || []).map(r =>
    `<div class="doc-item"><b>${esc(r.position)}</b><span>${esc(r.responsibilities)} — Min. experience: ${esc(r.minimum_experience)}</span></div>`).join("");
  sections.push(block(12, "Team Requirements", roles + sub("Saudization", para(team.saudization_note))));

  // 13. General & Special Terms
  sections.push(block(13, "General and Special Terms",
    sub("Legal Terms", ul(terms.legal_terms)) +
    sub("Compliance Requirements", ul(terms.compliance_requirements)) +
    sub("Language Requirements", para(terms.language_requirements)) +
    sub("Equipment and Logistics", para(terms.equipment_and_logistics))));

  // 14. Confidentiality
  sections.push(block(14, "Confidentiality", para(o.confidentiality)));

  // 15. Evaluation Methodology — technical + financial parameters in full
  sections.push(block(15, "Evaluation Methodology",
    kv([
      ["Evaluation Model", ev.evaluation_model],
      ["Technical Weight", ev.technical_weight != null ? ev.technical_weight + "%" : ""],
      ["Financial Weight", ev.financial_weight != null ? ev.financial_weight + "%" : ""],
      ["Minimum Technical Score", ev.minimum_technical_score != null ? ev.minimum_technical_score + "%" : ""],
      ["Award Basis", ev.award_basis],
    ]) +
    sub("Mandatory Pass/Fail Criteria", ul(ev.mandatory_criteria, c => esc(typeof c === "string" ? c : c.criterion))) +
    sub("Technical Evaluation Parameters", ul(ev.technical_parameters)) +
    sub("Financial Evaluation Parameters", ul(ev.financial_parameters))));

  // 16. Payment Terms
  sections.push(block(16, "Payment Terms",
    sub("Payment Basis", para(pay.payment_basis)) +
    sub("Invoice Requirements", ul(pay.invoice_requirements)) +
    sub("Payment Timeline", para(pay.payment_timeline))));

  // 17. Annexures + 18. Approval
  sections.push(block(17, "Annexures", ul(o.annexures)));
  setTimeout(() => loadDraftVendorRecommendations(form), 0);
  sections.push(block(18, "Buyer Approval",
    para("PENDING BUYER APPROVAL — this tender cannot be published until reviewed and approved by the authorized Buyer-Admin.")));

  return `<div class="result">
    <div class="result-head">
      <div>
        <div class="result-title">${esc(meta.title || "Tender Draft")}</div>
        <div class="hint" style="margin-top:4px">Reference: ${esc(meta.tender_id || "—")} · Issued by ${esc(meta.buyer_entity || "—")}${ti.tender_quality_score != null ? " · Health " + esc(ti.tender_quality_score) + "/100" : ""}</div>
      </div>
      <span class="badge draft dot">DRAFT · pending buyer approval</span>
    </div>
    <div class="toolbar" style="margin-bottom:16px">
      ${fid ? `<a class="btn primary" href="/api/download/${fid}/pdf?template=${encodeURIComponent(activeTemplate)}" target="_blank">⬇ Download ${esc(PDF_TEMPLATES.find(([v]) => v === activeTemplate)?.[1] || "PDF")}</a>
      ${PDF_TEMPLATES.filter(([v]) => v !== activeTemplate).map(([v, label]) => `<a class="btn ghost" href="/api/download/${fid}/pdf?template=${encodeURIComponent(v)}" target="_blank">⬇ ${esc(label)}</a>`).join("")}
      <a class="btn ghost" href="/api/download/${fid}/json" target="_blank">⬇ JSON</a>` : ""}
      ${result.artifact?.id ? `<button class="btn primary" onclick="approveTenderDraft('${esc(result.artifact.id)}')">Approve & Publish to Vendor Feed</button>` : ""}
      <button class="btn ghost" onclick="editTenderInputs()">Edit Tender Inputs</button>
    </div>
    <div id="draftVendorRecommendations" class="section-block">
      <div class="sb-head"><span class="num">V</span>Recommended Vendors</div>
      <div class="sb-body">${loaderHTML("Finding eligible vendors...", "Calculating VRI, BRI context, AI ranking, risk score, probability of success, and committee signals")}</div>
    </div>
    ${sections.join("")}
  </div>`;
}

// ── EXTRACT (and full pipeline from SOW) ─────────────────────────────────────────
function shortlistPayloadFromForm(form) {
  const certs = (form.required_certifications || [])
    .map(x => typeof x === "string" ? x : (x.name || ""))
    .filter(Boolean);
  return {
    category: form.category || "Information Technology",
    subcategory: form.subcategory || "IT Infrastructure & Data Centers",
    estimated_value_sar: form.estimated_value_sar || 1500000,
    timeline_days: Number(String(form.contract_duration || "").match(/\d+/)?.[0]) || 90,
    required_certifications: certs.length ? certs : ["ISO 27001"],
    minimum_years_experience: form.minimum_years_experience || 5,
    minimum_similar_projects: form.minimum_similar_projects || 3,
    local_presence_required: !!form.local_presence_required,
    required_sector_license: form.required_sector_license || null,
  };
}

function editTenderInputs() {
  show("draft");
  window.scrollTo({ top: 0, behavior: "smooth" });
}
window.editTenderInputs = editTenderInputs;

async function approveTenderDraft(artifactId) {
  if (sessionRole() !== "buyer") return;
  const response = await fetch(`/api/artifacts/${encodeURIComponent(artifactId)}/approve`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ buyer_id: sessionAccountId(), note: "Approved by Buyer-Admin in demo" }),
  });
  const data = await response.json();
  if (!response.ok) {
    $("#draftResult").insertAdjacentHTML("afterbegin", errorHTML(data.detail || "Could not approve this draft."));
    return;
  }
  $("#draftResult").insertAdjacentHTML("afterbegin", `<div class="result ok-result"><b>Tender approved and published.</b> It is now visible in the Vendor Tender Feed.</div>`);
  loadSavedTenders();
}

async function loadSavedTenders() {
  const box = $("#savedTenders");
  if (!box || sessionRole() !== "buyer") return;
  try {
    const response = await fetch(`/api/tenders/saved?buyer_id=${encodeURIComponent(sessionAccountId())}`);
    const data = await response.json();
    const rows = (data.tenders || []).map(t => `<tr>
      <td><b>${esc(t.title)}</b><span>${esc(t.reference || "")}</span></td>
      <td>${esc(t.publication_status)}</td>
      <td>${esc(t.created_at || "")}</td>
      <td>${t.file_id ? `<a class="btn ghost" href="/api/download/${esc(t.file_id)}/pdf" target="_blank">Open PDF</a>` : ""}</td>
    </tr>`).join("");
    box.innerHTML = `<div class="section-block"><div class="sb-head"><span class="num">S</span>Saved Tender History</div>
      <div class="sb-body"><p class="hint">Drafts and published tenders are stored locally and remain after restarting the demo.</p>
      ${rows ? `<div class="rep-table-wrap"><table class="rep-table"><thead><tr><th>Tender</th><th>Status</th><th>Created</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>` : "<p class='empty'>No saved tenders for this buyer yet.</p>"}</div></div>`;
  } catch (error) {
    box.innerHTML = errorHTML("Could not load saved tender history.");
  }
}

async function loadDraftVendorRecommendations(form) {
  const box = $("#draftVendorRecommendations .sb-body");
  if (!box) return;
  try {
    const data = await fetch("/api/intelligence/shortlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(shortlistPayloadFromForm(form || {})),
    }).then(r => r.json());
    box.innerHTML = renderShortlist(data);
  } catch (e) {
    box.innerHTML = errorHTML(e.message);
  }
}

function renderSowReview(result) {
  const r = (result && result.review) || {};
  const badge = r.readiness === "ready" ? "ok" : r.readiness === "weak" ? "bad" : "warn";
  return `<div class="result">
    <div class="section-block">
      <div class="sb-head"><span class="num">S</span>SoW Review</div>
      <div class="sb-body prose">
        <div class="result-head">
          <div>
            <div class="result-title">${esc(r.score ?? "-")}/100</div>
            <div class="hint">${esc(r.summary || "")}</div>
          </div>
          <span class="badge ${badge} dot">${esc(r.readiness || "needs_review")}</span>
        </div>
        ${sub("Strengths", ul(r.strengths))}
        ${sub("Gaps", ul(r.gaps))}
        ${sub("Recommendations", ul(r.recommendations))}
        ${sub("Rewritten Scope", para(r.rewritten_scope))}
      </div>
    </div>
  </div>`;
}

$("#reviewSowBtn").addEventListener("click", () => {
  const project_name = $("#draftTenderTitle").value.trim() || "Guided Tender";
  const scope_text = $("#draftScope").value.trim();
  if (!scope_text) {
    $("#sowReviewResult").innerHTML = errorHTML("Write the scope of work first.");
    return;
  }
  runJob({
    target: "#sowReviewResult",
    loadMain: "Reviewing the scope of work...",
    loadSub: "Qwen is checking clarity, deliverables, timeline, responsibilities, and acceptance criteria",
    start: () => fetch("/api/jobs/sow-review", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_name, scope_text }),
    }).then(r => r.json()),
    render: result => {
      const rewritten = result && result.review && result.review.rewritten_scope;
      if (rewritten) {
        $("#draftScope").value = rewritten;
      }
      return renderSowReview(result);
    },
  });
});

function applyPopulatedOptionalSections(form) {
  const setIfBlank = (selector, next) => {
    const input = $(selector);
    if (input && !input.value.trim() && next) input.value = next;
  };
  setIfBlank("#draftProjectObjective", form.project_objective);
  setIfBlank("#draftTechnicalRequirements", form.technical_requirements);
  setIfBlank("#draftMethodologyRequirements", form.methodology_requirements);
  setIfBlank("#draftEvaluationCriteria", (form.evaluation_criteria || []).map(c => `${c.name} | ${c.weight} | ${c.description}`).join("\n"));
  setIfBlank("#draftTechnicalEvalParams", (form.technical_evaluation_parameters || []).join("\n"));
  setIfBlank("#draftFinancialEvalParams", (form.financial_evaluation_parameters || []).join("\n"));
  if (!tableRows("draftDeliverablesTable", ["name", "description", "format"]).length) {
    replaceEditableRows("draftDeliverablesTable", form.deliverables, ["name", "description", "format"]);
  }
  if (!tableRows("draftTimelineTable", ["milestone", "date"]).length) {
    replaceEditableRows("draftTimelineTable", form.timeline, ["milestone", "date"]);
  }
  if (!responsibilityRows().length) {
    replaceEditableRows("draftResponsibilitiesTable", (form.roles_and_responsibilities || []).map(row => ({
      party: row.party || "",
      responsibilities: Array.isArray(row.responsibilities) ? row.responsibilities.join("; ") : (row.responsibilities || ""),
    })), ["party", "responsibilities"]);
  }
}

$("#populateOptionalBtn").addEventListener("click", () => {
  const scope_text = value("#draftScope");
  if (!scope_text) {
    $("#draftResult").innerHTML = errorHTML("Enter a Scope of Work before populating optional sections.");
    return;
  }
  runJob({
    target: "#draftResult",
    loadMain: "Populating optional tender sections...",
    loadSub: "Deriving editable deliverables, timeline, requirements, responsibilities, and evaluation inputs",
    start: () => fetch("/api/jobs/populate-optional-sections", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_name: value("#draftTenderTitle"), scope_text, form_overrides: collectDraftOverrides() }),
    }).then(async response => {
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not populate optional sections.");
      return data;
    }),
    render: result => {
      applyPopulatedOptionalSections(result.form || {});
      return `<div class="result ok-result"><b>Optional sections populated.</b> Review the editable tables and text before generating the tender.</div>`;
    },
  });
});

$("#guidedDraftBtn").addEventListener("click", () => {
  if (sessionRole() !== "buyer") {
    $("#draftResult").innerHTML = errorHTML("Sign in as a buyer first. Buyer name, buyer description, and tender ID are generated from the backend buyer session.");
    return;
  }
  setSignedInBuyerFields();
  const project_name = $("#draftTenderTitle").value.trim();
  const scope_text = $("#draftScope").value.trim();
  const template = selectedPdfTemplate();
  const form_overrides = collectDraftOverrides();
  const missing = missingRequiredDraftFields();
  if (missing.length) {
    $("#draftResult").innerHTML = errorHTML(`Complete required fields first: ${missing.join(", ")}.`);
    return;
  }
  runJob({
    target: "#draftResult",
    loadMain: "Drafting tender from approved SoW...",
    loadSub: "Extracting buyer form, then running the expert tender section agents",
    start: () => fetch("/api/jobs/draft-guided", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_name, scope_text, template, form_overrides, buyer_id: sessionRole() === "buyer" ? sessionAccountId() : null }),
    }).then(r => r.json()),
    render: renderDraft,
  });
});

const dropZone = $("#dropZone"), extractFile = $("#extractFile");
let pickedFile = null;
dropZone.addEventListener("click", () => extractFile.click());
extractFile.addEventListener("change", () => setFile(extractFile.files[0]));
["dragover", "dragenter"].forEach(ev => dropZone.addEventListener(ev, e => { e.preventDefault(); dropZone.classList.add("drag"); }));
["dragleave", "drop"].forEach(ev => dropZone.addEventListener(ev, e => { e.preventDefault(); dropZone.classList.remove("drag"); }));
dropZone.addEventListener("drop", e => { if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]); });
function setFile(f) {
  if (!f) return;
  pickedFile = f;
  $("#dzFile").textContent = f.name;
  $("#extractBtn").disabled = false;
  $("#extractDraftBtn").disabled = false;
}
$("#extractBtn").addEventListener("click", () => {
  if (!pickedFile) return;
  const fd = new FormData(); fd.append("file", pickedFile);
  runJob({
    target: "#extractResult",
    loadMain: "Reading the document…",
    loadSub: "Extracting a structured buyer form via intra-document retrieval",
    start: () => fetch("/api/jobs/extract", { method: "POST", body: fd }).then(r => r.json()),
    render: r => renderForm(r.form, "Extracted Buyer Form"),
  });
});
$("#extractDraftBtn").addEventListener("click", () => {
  if (!pickedFile) return;
  const fd = new FormData(); fd.append("file", pickedFile);
  fd.append("template", selectedPdfTemplate());
  fd.append("form_overrides", JSON.stringify(collectDraftOverrides()));
  if (sessionRole() === "buyer") fd.append("buyer_id", sessionAccountId());
  runJob({
    target: "#extractResult",
    loadMain: "Full pipeline: extracting, then drafting the complete tender…",
    loadSub: "Document → buyer form → 4 parallel section agents → assembled RFP",
    start: () => fetch("/api/jobs/draft-sow", { method: "POST", body: fd }).then(r => r.json()),
    render: renderDraft,
  });
});

// ── FORM rendering (shared by extract) ──────────────────────────────────────────
function renderForm(form, title) {
  const f = form || {};
  const dels = (f.deliverables || []).map(d => `<li><b>${esc(d.name)}</b> — ${esc(d.description || "")}</li>`).join("");
  const tl = (f.timeline || []).map(t => `<li>${esc(t.milestone)} — ${esc(t.date)}</li>`).join("");
  return `<div class="result">
    <div class="result-head">
      <div class="result-title">${esc(title)}</div>
      <span class="badge draft dot">DRAFT · review before use</span>
    </div>
    <div class="section-block"><div class="sb-head"><span class="num">i</span>Summary</div>
      <div class="sb-body"><dl class="kv">
        <dt>Tender title</dt><dd>${esc(f.tender_title || "—")}</dd>
        <dt>Buyer</dt><dd>${esc(f.buyer_name || "—")}</dd>
        <dt>Category</dt><dd>${esc(f.category || "—")} / ${esc(f.subcategory || "—")}</dd>
        <dt>Objective</dt><dd>${esc(f.project_objective || "—")}</dd>
        <dt>Technical requirements</dt><dd>${esc(f.technical_requirements || "—")}</dd>
        <dt>Submission deadline</dt><dd>${esc(f.submission_deadline || "—")}</dd>
        <dt>Estimated value</dt><dd>${f.estimated_value_sar ? "SAR " + Number(f.estimated_value_sar).toLocaleString() : "—"}</dd>
        <dt>Payment terms</dt><dd>${esc(f.payment_terms || "—")}</dd>
      </dl></div></div>
    <div class="section-block"><div class="sb-head"><span class="num">✎</span>Scope</div>
      <div class="sb-body prose"><p>${esc(f.scope_of_work || "—")}</p></div></div>
    ${dels ? `<div class="section-block"><div class="sb-head"><span class="num">◆</span>Deliverables</div><div class="sb-body"><ul class="ul">${dels}</ul></div></div>` : ""}
    ${tl ? `<div class="section-block"><div class="sb-head"><span class="num">⏱</span>Timeline</div><div class="sb-body"><ul class="ul">${tl}</ul></div></div>` : ""}
  </div>`;
}

// ── VALIDATE ────────────────────────────────────────────────────────────────────
function buildDocChips() {
  $("#vDocs").innerHTML = DOC_TYPES.map(([v, label], i) =>
    `<span class="chip ${i < 3 ? "on" : ""}" data-doc="${v}">${esc(label)}</span>`).join("");
  $$("#vDocs .chip").forEach(c => c.addEventListener("click", () => c.classList.toggle("on")));
}
$("#validateBtn").addEventListener("click", () => {
  const document_types = $$("#vDocs .chip.on").map(c => c.dataset.doc);
  const body = {
    cr_number: $("#vCr").value.trim(),
    legal_name_en: $("#vNameEn").value.trim(),
    legal_name_ar: $("#vNameAr").value.trim(),
    selected_categories: [$("#vCategory").value],
    document_types,
  };
  runJob({
    target: "#validateResult",
    loadMain: "Validating vendor…",
    loadSub: "Running the 4-tool reasoning loop (registry · duplicate · category · documents)",
    start: () => fetch("/api/jobs/validate", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    }).then(r => r.json()),
    render: r => renderValidation(r.artifact),
  });
});

function renderValidation(artifact) {
  const v = (artifact && artifact.output) || {};
  const map = {
    AUTO_VALIDATED: ["ok", "Auto-validated"],
    NEEDS_CORRECTION: ["warn", "Needs correction"],
    FLAGGED_FOR_REVIEW: ["bad", "Flagged for review"],
  };
  const [cls, label] = map[v.outcome] || ["warn", v.outcome || "—"];
  const flags = (v.flags || []).map(f => `<span class="chip">${esc(f)}</span>`).join("") || "<span class='empty'>none</span>";
  const missing = (v.missing_documents || []).map(f => `<li>${esc(f)}</li>`).join("");
  return `<div class="result">
    <div class="result-head">
      <div class="result-title">Validation result</div>
      <span class="badge ${cls} dot">${esc(label)}</span>
    </div>
    <div class="section-block"><div class="sb-body">
      <dl class="kv">
        <dt>CR status</dt><dd>${esc(v.cr_status || "—")}</dd>
        <dt>Name match</dt><dd>${v.name_match ? "Yes" : "No"} (${Math.round((v.name_match_confidence || 0) * 100)}% confidence)</dd>
        <dt>Category alignment</dt><dd>${esc(v.category_alignment || "—")}</dd>
        <dt>Duplicate</dt><dd>${v.is_duplicate ? "Yes" : "No"}</dd>
      </dl>
      <h4>Flags</h4><div class="chips">${flags}</div>
      ${missing ? `<h4>Missing documents</h4><ul class="ul">${missing}</ul>` : ""}
      ${v.vendor_message ? `<h4>Message to vendor</h4><p class="prose">${esc(v.vendor_message)}</p>` : ""}
      ${v.admin_note ? `<h4>Admin note</h4><p class="prose">${esc(v.admin_note)}</p>` : ""}
    </div></div>
    <div class="hint">Decision is advisory — a human admin takes the final action.</div>
  </div>`;
}

// ── EVALUATE ────────────────────────────────────────────────────────────────────
$("#evaluateBtn").addEventListener("click", () => {
  runJob({
    target: "#evaluateResult",
    loadMain: "Evaluating bids…",
    loadSub: "Scoring each vendor in isolation, then ranking",
    start: () => fetch("/api/jobs/evaluate", { method: "POST" }).then(r => r.json()),
    render: renderEvaluation,
  });
});

function renderEvaluation(result) {
  const ranking = result.ranking || {};
  const names = result.vendor_names || {};
  const ranked = (ranking.ranked_list || []).map(v => {
    const name = names[v.vendor_id] || v.vendor_id;
    return `<div class="vendor-card">
      <div class="vc-head">
        <div style="display:flex;align-items:center;gap:12px">
          <div class="rank-pill ${v.rank === 1 ? "rank-1" : ""}">#${v.rank}</div>
          <div><div class="vc-name">${esc(name)}</div><div class="hint" style="margin:0">VRI ${esc(v.vri)} · risk ${esc(v.risk_level)}</div></div>
        </div>
        <div class="score-big">${Number(v.weighted_total).toFixed(1)}</div>
      </div>
      <p class="prose" style="margin:0">${esc(v.summary || "")}</p>
    </div>`;
  }).join("");

  const breakdowns = (result.scores || []).map(s => {
    const fb = s.fit_score_breakdown || {};
    const name = names[s.vendor_id] || s.vendor_id;
    const dq = s.disqualification || {};
    if (dq.disqualified) {
      return `<div class="vendor-card"><div class="vc-head"><div class="vc-name">${esc(name)}</div>
        <span class="badge bad dot">Disqualified</span></div>
        <p class="prose" style="margin:0">${esc((dq.reasons || []).join("; "))}</p></div>`;
    }
    const bar = (label, val) => `<div class="bar-row"><span>${label}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${Math.max(0, Math.min(100, val))}%"></div></div>
      <span style="text-align:right">${Number(val).toFixed(0)}</span></div>`;
    return `<div class="vendor-card">
      <div class="vc-head"><div class="vc-name">${esc(name)}</div>
        <span class="badge ${s.risk_level === 'low' ? 'ok' : s.risk_level === 'medium' ? 'warn' : 'bad'} dot">risk: ${esc(s.risk_level)}</span></div>
      <div class="bars">
        ${bar("VRI (40%)", fb.vri_component)}
        ${bar("Requirement match (30%)", fb.requirement_match)}
        ${bar("Proposal quality (20%)", fb.proposal_quality)}
        ${bar("Price competitiveness (10%)", fb.price_competitiveness)}
      </div>
      <p class="prose" style="margin:12px 0 0;font-size:13px;color:var(--ink-soft)">${esc(s.overall_reasoning || "")}</p>
    </div>`;
  }).join("");

  return `<div class="result">
    <div class="result-head"><div class="result-title">${esc(result.tender_title || "Evaluation")}</div>
      <span class="badge draft dot">DRAFT · buyer must approve award</span></div>
    <div class="reco">
      <h3>★ Recommendation</h3>
      <p>${esc(ranking.recommendation || "—")}</p>
      ${ranking.explainability_summary ? `<p style="color:#8595b8;font-size:13px">${esc(ranking.explainability_summary)}</p>` : ""}
    </div>
    <h3 style="margin:18px 0 10px">Ranked vendors</h3>
    ${ranked || "<p class='empty'>No ranked vendors.</p>"}
    <h3 style="margin:24px 0 10px">Score breakdown (each scored in isolation)</h3>
    ${breakdowns}
  </div>`;
}

// ── KB SEARCH ────────────────────────────────────────────────────────────────────
// Reputation Hub
function sar(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "-";
  return "SAR " + new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(n);
}

function scoreBadgeClass(value) {
  const n = Number(value);
  if (n >= 80) return "ok";
  if (n >= 65) return "warn";
  return "bad";
}

function riskBadgeClass(value) {
  const text = String(value || "").toLowerCase();
  if (text === "low") return "ok";
  if (text === "medium") return "warn";
  return "bad";
}

function badgeList(items) {
  const list = (items || []).slice(0, 3);
  if (!list.length) return "<span class='empty'>No special badges</span>";
  return list.map(item => `<span class="mini-badge">${esc(item)}</span>`).join("");
}

function renderReputationHub(data) {
  reputationData = data;
  const summary = data.summary || {};
  $("#reputationSnapshot").innerHTML = `<div class="rep-summary">
    <div class="intel-grid">
      ${metricCard("Buyer Accounts", summary.buyer_count, "Demo BRI profiles")}
      ${metricCard("Vendor Accounts", summary.vendor_count, "Demo VRI profiles")}
      ${metricCard("Average Vendor VRI", summary.average_vendor_vri, "Category-aware reputation")}
      ${metricCard("Average Buyer BRI", summary.average_buyer_bri, "Payment and fairness")}
      ${metricCard("Elite/Strategic Vendors", summary.elite_or_strategic_vendors, "VRI 75+")}
      ${metricCard("Trusted Buyers", summary.trusted_or_strategic_buyers, "BRI 75+")}
    </div>
  </div>`;

  const vendors = (data.vendors || []).slice().sort((a, b) => b.vri.category_specific - a.vri.category_specific);
  const buyers = (data.buyers || []).slice().sort((a, b) => b.bri.overall - a.bri.overall);
  const atRiskVendor = vendors.find(v => v.status === "under_review" && v.vri.category_specific < 50);
  const atRiskBuyer = buyers.find(b => b.status === "under_review" && b.bri.overall < 50);
  $("#reputationAccounts").innerHTML = `<div class="rep-columns">
    ${(atRiskVendor || atRiskBuyer) ? `<div class="section-block rep-risk-showcase">
      <div class="sb-head"><span class="num">!</span>Enhanced Due Diligence Demo Profiles</div>
      <div class="sb-body"><p class="hint">These profiles demonstrate how BRI/VRI makes risk evidence visible before a buyer publishes or a vendor commits to a tender.</p>
        <div class="rep-risk-grid">
          ${atRiskVendor ? `<div><b>${esc(atRiskVendor.name)}</b><span>Vendor VRI ${esc(atRiskVendor.vri.category_specific)}/100 · ${esc(atRiskVendor.status.replace("_", " "))}</span><small>${esc(atRiskVendor.profile_summary)}</small></div>` : ""}
          ${atRiskBuyer ? `<div><b>${esc(atRiskBuyer.name)}</b><span>Buyer BRI ${esc(atRiskBuyer.bri.overall)}/100 · ${esc(atRiskBuyer.status.replace("_", " "))}</span><small>${esc(atRiskBuyer.profile_summary)}</small></div>` : ""}
        </div>
      </div>
    </div>` : ""}
    <div class="section-block">
      <div class="sb-head"><span class="num">V</span>Vendor Accounts</div>
      <div class="sb-body">${renderVendorAccountTable(vendors)}</div>
    </div>
    <div class="section-block">
      <div class="sb-head"><span class="num">B</span>Buyer Accounts</div>
      <div class="sb-body">${renderBuyerAccountTable(buyers)}</div>
    </div>
  </div>`;
}

function renderVendorAccountTable(vendors) {
  const rows = vendors.map(v => `<tr>
    <td><b>${esc(v.name)}</b><span>${esc(v.account_id)} - ${esc(v.city)}</span></td>
    <td>${esc(v.categories[0])}<span>${esc(v.subcategories[0])}</span></td>
    <td><b>${esc(v.vri.category_specific)}</b><span>${esc(v.vri.level)}</span></td>
    <td><span class="badge ${scoreBadgeClass(v.vri.category_specific)}">${esc(v.badge)}</span><span>${badgeList(v.special_badges)}</span><span class="account-status ${esc(v.status)}">${esc(v.status.replace("_", " "))}</span></td>
    <td>${esc(v.rating)}/5<span>${esc(v.completed_contracts)} contracts</span></td>
  </tr>`).join("");
  return `<div class="rep-table-wrap"><table class="rep-table">
    <thead><tr><th>Vendor</th><th>Category</th><th>VRI</th><th>Badge</th><th>Rating</th></tr></thead>
    <tbody>${rows}</tbody>
  </table></div>`;
}

function renderBuyerAccountTable(buyers) {
  const rows = buyers.map(b => `<tr>
    <td><b>${esc(b.name)}</b><span>${esc(b.account_id)} - ${esc(b.city)}</span></td>
    <td>${esc(b.primary_category)}<span>${esc(b.primary_subcategory)}</span></td>
    <td><b>${esc(b.buyer_score ?? b.bri.overall)}/100</b><span>${esc(b.bri.level)}</span></td>
    <td><span class="badge ${scoreBadgeClass(b.bri.overall)}">${esc(b.badge)}</span><span>${badgeList(b.special_badges)}</span><span class="account-status ${esc(b.status)}">${esc(b.status.replace("_", " "))}</span></td>
    <td>${esc(b.payment_reliability)}%<span>Dispute Rate: ${esc(b.dispute_rate_level || b.dispute_rate)}</span></td>
  </tr>`).join("");
  return `<div class="rep-table-wrap"><table class="rep-table">
    <thead><tr><th>Buyer</th><th>Category</th><th>Buyer Score</th><th>Badge</th><th>Payment Reliability</th></tr></thead>
    <tbody>${rows}</tbody>
  </table></div>`;
}

async function loadReputationHub() {
  const snapshot = $("#reputationSnapshot");
  const accounts = $("#reputationAccounts");
  if (!snapshot || !accounts) return;
  snapshot.innerHTML = loaderHTML("Loading reputation accounts...", "Preparing VRI, BRI, and badge signals");
  accounts.innerHTML = "";
  try {
    const data = await fetch("/api/reputation").then(r => r.json());
    renderReputationHub(data);
  } catch (e) {
    snapshot.innerHTML = errorHTML(e.message);
  }
}

function shortlistPayloadFromDraft() {
  const d = collectDraftOverrides();
  return {
    category: d.category || "Information Technology",
    subcategory: d.subcategory || "IT Infrastructure & Data Centers",
    estimated_value_sar: d.estimated_value_sar || 1500000,
    timeline_days: 90,
    required_certifications: d.required_certifications || ["ISO 27001"],
    minimum_years_experience: d.minimum_years_experience || 5,
    minimum_similar_projects: d.minimum_similar_projects || 3,
    local_presence_required: !!d.local_presence_required,
    required_sector_license: d.required_sector_license || null,
  };
}

async function runVendorShortlist() {
  const box = $("#shortlistResult");
  box.innerHTML = loaderHTML("Shortlisting vendors...", "Calculating VRI, requirement match, proposal quality, price, risk, and committee scores");
  try {
    const data = await fetch("/api/intelligence/shortlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(shortlistPayloadFromDraft()),
    }).then(r => r.json());
    box.innerHTML = renderShortlist(data);
    box.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    box.innerHTML = errorHTML(e.message);
  }
}

function renderShortlist(result) {
  const counts = result.counts || {};
  const reco = result.top_recommendation;
  const committee = result.committee || {};
  const layer = result.ai_recommendation_layer || {};
  const weights = layer.weights || {};
  const topThree = result.top_three || [];

  return `<div class="result">
    <div class="intel-panel">
      <div class="intel-hero">
        <div>
          <div class="intel-eyebrow">AI Vendor Selection Engine</div>
          <h2>${esc(reco ? `${reco.ai_recommendation_score}/100` : "No Match")}</h2>
          <p>${esc(committee.final_recommendation || result.human_in_the_loop || "")}</p>
        </div>
        <span class="badge draft dot">Advisory - Buyer decides</span>
      </div>
      <div class="intel-grid">
        ${metricCard("AI Recommendation Enabled", layer.enabled ? "YES" : "NO")}
        ${metricCard("VRI Weight", `${weights.vri ?? 20}%`, "Vendor reputation signal")}
        ${metricCard("Technical Evaluation", `${weights.technical_evaluation ?? 50}%`, "Fit and proposal quality")}
        ${metricCard("Financial Evaluation", `${weights.financial_evaluation ?? 20}%`, "Value for money")}
        ${metricCard("Risk Assessment", `${weights.risk_assessment ?? 10}%`, "Risk score")}
        ${metricCard("Risk Score", layer.risk_score ?? "-")}
        ${metricCard("Probability of Success", layer.probability_of_success != null ? `${layer.probability_of_success}%` : "-")}
        ${metricCard("Compliance Status", layer.compliance_status || "-")}
        ${metricCard("Recommended Vendor", reco ? reco.vendor_name : "Manual review")}
      </div>
      <div class="intel-grid">
        ${metricCard("Potential Eligible Vendors Found", counts.potential_eligible_vendors_found ?? 0)}
        ${metricCard("High Match Vendors", counts.high_match_vendors ?? 0)}
        ${metricCard("Medium Match Vendors", counts.medium_match_vendors ?? 0)}
        ${metricCard("Low Match Vendors", counts.low_match_vendors ?? 0)}
        ${metricCard("Excluded Vendors", counts.excluded_vendors ?? 0)}
      </div>
      ${renderCommitteeComparison(committee)}
    </div>
    <h3 style="margin:18px 0 10px">Top 3 Vendors</h3>
    ${topThree.map(renderShortlistVendor).join("") || "<p class='empty'>No eligible vendors found.</p>"}
    <h3 style="margin:24px 0 10px">Eligible Vendor Buckets</h3>
    ${renderBucket("High Match", result.buckets?.high_match)}
    ${renderBucket("Medium Match", result.buckets?.medium_match)}
    ${renderBucket("Low Match", result.buckets?.low_match)}
  </div>`;
}

function renderCommitteeComparison(committee) {
  const rows = (committee.comparison || []).map(v => `<tr>
    <td>#${esc(v.rank)} ${esc(v.vendor_name)}<span>VRI ${esc(v.vri)} - risk ${esc(v.risk_level)}</span></td>
    <td><span class="committee-score">${esc(v.ai_recommendation_score ?? v.fit_score)}</span></td>
    <td><span class="committee-score">${esc(v.committee_score)}</span></td>
  </tr>`).join("");
  if (!rows) return "";
  return `<div class="intel-section">
    <div class="intel-section-head"><h4>AI Tender Committee Comparison</h4><span>Technical Agent / Commercial Agent / Compliance Agent / Delivery Agent / Risk Agent</span></div>
    <div class="committee-box"><table class="committee-table">
      <thead><tr><th>Vendor</th><th>AI Ranking</th><th>Committee</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>
  </div>`;
}

function renderShortlistVendor(v) {
  return `<div class="vendor-card">
    <div class="vc-head">
      <div style="display:flex;align-items:center;gap:12px">
        <div class="rank-pill ${v.rank === 1 ? "rank-1" : ""}">#${esc(v.rank)}</div>
        <div>
          <div class="vc-name">${esc(v.vendor_name)}</div>
          <div class="hint" style="margin:0">VRI ${esc(v.vri)} - ${esc(v.vri_level)} - ${esc(v.badge)}</div>
        </div>
      </div>
      <div class="score-big">${esc(v.ai_recommendation_score)}</div>
    </div>
    <span class="badge ${riskBadgeClass(v.risk_level)} dot">risk: ${esc(v.risk_level)}</span>
    <div class="bars">
      ${barRow("Technical Evaluation (50%)", v.technical_evaluation)}
      ${barRow("Financial Evaluation (20%)", v.financial_evaluation)}
      ${barRow("VRI (20%)", v.vri)}
      ${barRow("Risk Assessment (10%)", v.risk_score)}
      ${barRow("AI Tender Committee", v.committee?.final_score)}
    </div>
    <dl class="kv" style="margin-top:12px">
      <dt>Probability of Success</dt><dd>${esc(v.probability_of_success)}%</dd>
      <dt>Compliance Status</dt><dd>${esc(v.compliance_status)}</dd>
      <dt>Vendor Fit Score</dt><dd>${esc(v.fit_score)}/100</dd>
    </dl>
    <div class="badge-row">${badgeList(v.special_badges)}</div>
    ${ul(v.why_selected)}
  </div>`;
}

function barRow(label, val) {
  const n = Math.max(0, Math.min(100, Number(val) || 0));
  return `<div class="bar-row"><span>${esc(label)}</span>
    <div class="bar-track"><div class="bar-fill" style="width:${n}%"></div></div>
    <span style="text-align:right">${n.toFixed(0)}</span></div>`;
}

function renderBucket(label, vendors) {
  const rows = (vendors || []).slice(0, 8).map(v => `<div class="bucket-row">
    <b>#${esc(v.rank)} ${esc(v.vendor_name)}</b>
    <span>AI ${esc(v.ai_recommendation_score)} - VRI ${esc(v.vri)} - ${esc(v.risk_level)} risk</span>
  </div>`).join("");
  return `<div class="section-block">
    <div class="sb-head"><span class="num">${esc(label[0])}</span>${esc(label)}</div>
    <div class="sb-body">${rows || "<p class='empty'>No vendors in this bucket.</p>"}</div>
  </div>`;
}

function buyerReputationHTML(buyer) {
  if (!buyer) return "";
  return `<div class="rep-summary">
    <div class="intel-grid">
      ${metricCard("Buyer Score", `${buyer.buyer_score ?? buyer.bri?.overall ?? "-"} / 100`, buyer.bri?.level || "")}
      ${metricCard("Badge", buyer.badge || "-")}
      ${metricCard("Payment Reliability", `${buyer.payment_reliability ?? "-"}%`)}
      ${metricCard("Dispute Rate", buyer.dispute_rate_level || buyer.dispute_rate || "-")}
    </div>
  </div>`;
}

function tenderReqHTML(tender) {
  return `<dl class="kv">
    <dt>Category</dt><dd>${esc(tender.category)} / ${esc(tender.subcategory)}</dd>
    <dt>Location</dt><dd>${esc(tender.location || "-")}</dd>
    <dt>Budget</dt><dd>${esc(tender.budget_range || sar(tender.estimated_value_sar))}</dd>
    <dt>Evaluation</dt><dd>${esc(tender.evaluation_model || "-")}</dd>
    <dt>Required Certifications</dt><dd>${esc((tender.required_certifications || []).join(", ") || "-")}</dd>
    <dt>Minimum Experience</dt><dd>${esc(tender.minimum_years_experience)} years, ${esc(tender.minimum_similar_projects)} similar projects</dd>
  </dl>`;
}

function renderVendorTenderCard(tender) {
  const vendor = currentSession?.account || {};
  const id = tender.id;
  const submitted = tender.current_vendor_proposal;
  const recommended = tender.recommended_to_current_vendor
    ? `<span class="badge ok dot">Recommended to you${tender.current_vendor_rank ? ` - rank #${tender.current_vendor_rank}` : ""}</span>`
    : `<span class="badge draft dot">Open opportunity</span>`;
  return `<div class="section-block vendor-opportunity" id="tender-${esc(id)}">
    <div class="sb-head"><span class="num">T</span>${esc(tender.title)} <span class="badge draft">${esc(tender.reference)}</span></div>
    <div class="sb-body">
      <div class="result-head">
        <div>
          <div class="vc-name">${esc(tender.buyer?.name || "Buyer")}</div>
          <div class="hint" style="margin:0">${esc(tender.human_in_the_loop || "AI recommends only. Buyer controls final approval and award.")}</div>
        </div>
        ${recommended}
      </div>
      ${buyerReputationHTML(tender.buyer)}
      ${sub("Tender Requirements", tenderReqHTML(tender))}
      ${sub("Scope of Work", para(tender.scope_of_work))}
      <div class="grid two proposal-grid">
        <div>
          <label class="field-label">Demo price SAR</label>
          <input id="proposalPrice-${esc(id)}" class="input" type="number" value="${esc(vendor.typical_bid_sar || tender.estimated_value_sar || "")}" />
        </div>
        <div>
          <label class="field-label">Delivery timeline days</label>
          <input id="proposalTimeline-${esc(id)}" class="input" type="number" value="90" />
        </div>
      </div>
      <label class="field-label" style="margin-top:14px">Technical proposal summary</label>
      <textarea id="proposalTech-${esc(id)}" class="input textarea mini-textarea">We can deliver the requested scope using our relevant category experience, verified documents, and delivery team.</textarea>
      <label class="field-label" style="margin-top:14px">Commercial proposal summary</label>
      <textarea id="proposalCommercial-${esc(id)}" class="input textarea mini-textarea">Commercial offer is aligned with the stated budget range and includes required support and warranty assumptions.</textarea>
      <div class="toolbar" style="margin-top:14px">
        <button class="btn primary" onclick="submitDemoProposal('${esc(id)}')" ${submitted ? "disabled" : ""}>${submitted ? "Proposal Submitted" : "Submit Demo Proposal"}</button>
        <button class="btn ghost" onclick="returnToLastBuyer()">Return to Buyer Comparison</button>
      </div>
      ${submitted ? `<div class="isolation-note" style="margin-top:14px"><b>Submitted.</b> Proposal ${esc(submitted.id)} is ready for buyer-side AI comparison.</div>` : ""}
    </div>
  </div>`;
}

async function loadVendorFeed() {
  const box = $("#vendorFeedResult");
  if (!box) return;
  if (sessionRole() !== "vendor") {
    box.innerHTML = errorHTML("Sign in as a vendor to view the tender feed.");
    return;
  }
  box.innerHTML = loaderHTML("Loading vendor feed...", "Fetching generated tenders, buyer BRI, shortlist context, and proposal status");
  try {
    const data = await fetch(`/api/tenders/feed?vendor_id=${encodeURIComponent(sessionAccountId())}`).then(r => r.json());
    const tenders = data.tenders || [];
    box.innerHTML = tenders.length
      ? tenders.map(renderVendorTenderCard).join("")
      : `<div class="empty-list">No generated tenders yet. Sign in as a buyer, draft a tender, then return here.</div>`;
  } catch (e) {
    box.innerHTML = errorHTML(e.message);
  }
}

async function submitDemoProposal(tenderId) {
  if (sessionRole() !== "vendor") return;
  selectedVendorTenderId = tenderId;
  const body = {
    vendor_id: sessionAccountId(),
    price_sar: Number(value(`#proposalPrice-${tenderId}`)) || null,
    timeline_days: Number(value(`#proposalTimeline-${tenderId}`)) || null,
    technical_summary: value(`#proposalTech-${tenderId}`),
    commercial_summary: value(`#proposalCommercial-${tenderId}`),
  };
  const data = await fetch(`/api/tenders/${encodeURIComponent(tenderId)}/proposals`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(r => r.json());
  await loadVendorFeed();
  const target = $(`#tender-${tenderId}`);
  if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
  return data;
}

function renderProposalComparisonCard(comparison) {
  const tender = comparison.tender || {};
  const ranking = comparison.ranking || [];
  const recommended = comparison.recommended_vendor || null;
  const approvalButton = recommended?.committee_artifact_id && recommended?.committee_approval_status !== "APPROVED"
    ? `<button class="btn primary" style="margin-top:12px" onclick="approveCommitteeArtifact('${esc(recommended.committee_artifact_id)}')">Approve AI Committee Recommendation</button>`
    : (recommended?.committee_approval_status === "APPROVED" ? `<span class="badge approved dot">Committee recommendation approved</span>` : "");
  const rows = ranking.map(v => `<div class="vendor-card">
    <div class="vc-head">
      <div style="display:flex;align-items:center;gap:12px">
        <div class="rank-pill ${v.rank === 1 ? "rank-1" : ""}">#${esc(v.rank)}</div>
        <div>
          <div class="vc-name">${esc(v.vendor_name || v.vendor?.name || v.vendor_id)}</div>
          <div class="hint" style="margin:0">VRI ${esc(v.vri)} / 100 - ${esc(v.vri_level)} - ${esc(v.proposal?.badge || "")}</div>
        </div>
      </div>
      <div class="score-big">${esc(v.ai_recommendation_score)}</div>
    </div>
    <span class="badge ${riskBadgeClass(v.risk_level)} dot">risk: ${esc(v.risk_level)}</span>
    <div class="bars">
      ${barRow("AI Recommendation", v.ai_recommendation_score)}
      ${barRow("Risk Score", v.risk_score)}
      ${barRow("Probability of Success", v.probability_of_success)}
      ${barRow("AI Tender Committee", v.committee?.final_score)}
    </div>
    <dl class="kv" style="margin-top:12px">
      <dt>Proposal Price</dt><dd>${sar(v.proposal?.price_sar)}</dd>
      <dt>Timeline</dt><dd>${esc(v.proposal?.timeline_days || "-")} days</dd>
      <dt>Compliance Status</dt><dd>${esc(v.compliance_status || "-")}</dd>
    </dl>
    ${sub("AI Tender Committee", renderCommitteeAgents(v.committee))}
    ${ul(v.why_selected)}
  </div>`).join("");
  return `<div class="section-block">
    <div class="sb-head"><span class="num">C</span>${esc(tender.title || "Tender")} <span class="badge draft">${esc(tender.reference || "")}</span></div>
    <div class="sb-body">
      <div class="intel-panel">
        <div class="intel-hero">
          <div>
            <div class="intel-eyebrow">Submitted Vendor Comparison</div>
            <h2>${esc(comparison.recommended_vendor ? `${comparison.recommended_vendor.ai_recommendation_score}/100` : "No Bids")}</h2>
            <p>${esc(comparison.human_in_the_loop || "AI recommends only. Buyer controls final approval and award.")}</p>
          </div>
          <span class="badge draft dot">Buyer decides</span>
        </div>
        ${approvalButton}
      </div>
      ${rows || "<p class='empty'>No submitted vendor proposals for this tender yet.</p>"}
    </div>
  </div>`;
}

function renderCommitteeAgents(committee) {
  const agents = committee?.agents || [];
  if (!agents.length) return "<p class='empty'>Committee signals require buyer review.</p>";
  return `<div class="committee-board">${agents.map(agent => `<div class="committee-card">
    <div class="committee-card-head"><b>${esc(agent.agent)}</b><span class="score-pill">${esc(agent.score)}</span></div>
    <p>${esc(agent.summary || "")}</p>
  </div>`).join("")}</div>`;
}

async function loadBuyerProposalComparison() {
  const box = $("#buyerProposalResult");
  if (!box) return;
  if (sessionRole() !== "buyer") {
    box.innerHTML = errorHTML("Sign in as a buyer to compare submitted vendors.");
    return;
  }
  box.innerHTML = loaderHTML("Comparing submitted vendors...", "Applying VRI, risk, probability of success, compliance, and AI committee signals");
  try {
    const data = await fetch(`/api/proposals/compare?buyer_id=${encodeURIComponent(sessionAccountId())}`).then(r => r.json());
    const comparisons = data.comparisons || [];
    box.innerHTML = comparisons.length
      ? comparisons.map(renderProposalComparisonCard).join("")
      : `<div class="empty-list">No tenders for this buyer yet. Generate a tender first, then submit as a vendor.</div>`;
  } catch (e) {
    box.innerHTML = errorHTML(e.message);
  }
}

async function approveCommitteeArtifact(artifactId) {
  if (sessionRole() !== "buyer") return;
  const response = await fetch(`/api/artifacts/${encodeURIComponent(artifactId)}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ buyer_id: sessionAccountId(), note: "Approved from buyer proposal comparison" }),
  });
  const data = await response.json();
  if (!response.ok) {
    alert(data.detail || "Could not record approval.");
    return;
  }
  await loadBuyerProposalComparison();
}

window.submitDemoProposal = submitDemoProposal;
window.returnToLastBuyer = returnToLastBuyer;
window.switchToVendorSandbox = switchToVendorSandbox;
window.approveCommitteeArtifact = approveCommitteeArtifact;

$("#refreshReputationBtn")?.addEventListener("click", loadReputationHub);
$("#shortlistBtn")?.addEventListener("click", runVendorShortlist);
$("#refreshVendorFeedBtn")?.addEventListener("click", loadVendorFeed);
$("#refreshBuyerProposalsBtn")?.addEventListener("click", loadBuyerProposalComparison);

$("#kbBtn").addEventListener("click", kbSearch);
$("#kbQuery").addEventListener("keydown", e => { if (e.key === "Enter") kbSearch(); });
async function kbSearch() {
  const q = $("#kbQuery").value.trim();
  if (!q) return;
  const box = $("#kbResult");
  box.innerHTML = loaderHTML("Searching…", "Embedding the query and ranking chunks");
  try {
    const data = await fetch(`/api/kb/search?q=${encodeURIComponent(q)}&k=6`).then(r => r.json());
    if (!data.hits.length) { box.innerHTML = "<p class='empty'>No matches found.</p>"; return; }
    box.innerHTML = `<div class="result">${data.hits.map(h => `
      <div class="hit">
        <div class="hit-head">
          <span class="tag ${esc(h.authority)}">${esc(h.authority)}</span>
          <span class="hit-src">${esc(h.source)}</span>
          <span class="hit-score">${(h.score * 100).toFixed(0)}% match</span>
        </div>
        <div class="hit-text">${esc(h.text)}</div>
      </div>`).join("")}</div>`;
  } catch (e) { box.innerHTML = errorHTML(e.message); }
}

// ── Boot: load metadata ──────────────────────────────────────────────────────────
(async function init() {
  restoreSession();
  buildDocChips();
  try { await loadDemoAccounts(); } catch (e) { console.warn("demo account list load failed", e); }
  // Seed the activity poll position so old events aren't replayed on page load.
  try {
    const a = await fetch("/api/activity?since=0").then(r => r.json());
    actLast = a.last_id || 0;
  } catch { }
  try {
    const m = await fetch("/api/meta").then(r => r.json());
    $("#envModel").textContent = m.model;
    $("#envEmbed").textContent = m.embed_model;
    $("#envKb").textContent = m.kb_available ? "ready" : "empty";
    platformCategories = m.categories || {};
    const sel = $("#vCategory");
    sel.innerHTML = Object.keys(m.categories || {}).map(c => `<option>${esc(c)}</option>`).join("");
    const draftCategory = $("#draftCategory");
    if (draftCategory) {
      draftCategory.innerHTML = Object.keys(platformCategories).map(c => `<option>${esc(c)}</option>`).join("");
      if (platformCategories["Information Technology"]) draftCategory.value = "Information Technology";
      draftCategory.addEventListener("change", syncDraftSubcategories);
      syncDraftSubcategories();
      const draftSubcategory = $("#draftSubcategory");
      if (draftSubcategory && [...draftSubcategory.options].some(o => o.value === "IT Infrastructure & Data Centers")) {
        draftSubcategory.value = "IT Infrastructure & Data Centers";
      }
    }
    setDefaultDraftDates();
    $("#kbCount").textContent = m.kb_count ?? (m.kb_available ? "—" : "0");
  } catch (e) {
    console.warn("meta load failed", e);
  }
  await loadReputationHub();
})();
