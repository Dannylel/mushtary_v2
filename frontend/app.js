// Mushtary demo UI — vanilla JS, no build step. Talks to the FastAPI layer in api.py.

const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const esc = (s) => String(s ?? "").replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

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
const PDF_TEMPLATES = [
  ["premium_bw", "Premium B/W"],
  ["modern_bw", "Modern B/W"],
];

function selectedPdfTemplate() {
  const picked = $("input[name='pdfTemplate']:checked");
  return picked ? picked.value : "premium_bw";
}

function checked(id) { return !!$(id)?.checked; }
function value(id) { return ($(id)?.value || "").trim(); }
function numberOrNull(id) {
  const raw = value(id);
  if (!raw) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
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
  return {
    category: value("#draftCategory") || undefined,
    subcategory: value("#draftSubcategory") || undefined,
    tender_type: value("#draftTenderType") || undefined,
    procurement_method: value("#draftProcurementMethod") || undefined,
    issue_date: value("#draftIssueDate") || undefined,
    clarification_deadline: value("#draftClarificationDate") || undefined,
    submission_deadline: value("#draftSubmissionDate") || undefined,
    submission_time: value("#draftSubmissionTime") || undefined,
    opening_date: value("#draftOpeningDate") || undefined,
    site_visit_required: checked("#draftSiteVisitRequired"),
    site_visit_date: value("#draftSiteVisitDate") || undefined,
    bid_security_required: checked("#draftBidSecurityRequired"),
    bid_security_amount_or_percentage: value("#draftBidSecurityAmount") || undefined,
    performance_bond_required: checked("#draftPerformanceBondRequired"),
    performance_bond_percentage: numberOrNull("#draftPerformanceBondPct"),
    local_presence_required: checked("#draftLocalPresenceRequired"),
    saudization_required: checked("#draftSaudizationRequired"),
    confidentiality_required: checked("#draftConfidentialityRequired"),
    evaluation_model,
    technical_weight,
    financial_weight,
    minimum_score: numberOrNull("#draftMinimumScore"),
    contract_duration: value("#draftContractDuration") || undefined,
    submission_controls: {
      separate_technical_commercial: checked("#draftSeparateTechCommercial"),
      late_submission_allowed: checked("#draftLateSubmissionAllowed"),
    },
  };
}

function isoDatePlus(days) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

function setDefaultDraftDates() {
  const defaults = [
    ["#draftIssueDate", 0],
    ["#draftSiteVisitDate", 5],
    ["#draftClarificationDate", 7],
    ["#draftSubmissionDate", 14],
    ["#draftOpeningDate", 15],
  ];
  defaults.forEach(([id, days]) => {
    const el = $(id);
    if (el && !el.value) el.value = isoDatePlus(days);
  });
}

// ── Navigation ────────────────────────────────────────────────────────────────
function show(view) {
  $$(".nav-item").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  $$(".view").forEach(v => v.classList.toggle("active", v.id === `view-${view}`));
  window.scrollTo({ top: 0 });
}
$$(".nav-item").forEach(b => b.addEventListener("click", () => show(b.dataset.view)));
$$("[data-go]").forEach(c => c.addEventListener("click", () => show(c.dataset.go)));

// ── Live activity console ─────────────────────────────────────────────────────
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
  const rowHtml = committee.rows.map(r => `
    <tr>
      <td><b>${esc(r.agent)}</b><span>${esc(r.focus)}</span></td>
      <td><span class="committee-score">${esc(r.score ?? "—")}</span></td>
    </tr>`).join("");
  return `<div class="committee-box">
    <table class="committee-table">
      <thead><tr><th>AI Agent</th><th>Score</th></tr></thead>
      <tbody>
        ${rowHtml}
        <tr class="committee-final"><td>Final AI Recommendation</td><td><span class="committee-score">${esc(committee.finalScore ?? "—")}</span></td></tr>
      </tbody>
    </table>
    ${committee.priorities && committee.priorities.length ? sub("Improvement Priorities", ul(committee.priorities)) : ""}
    ${committee.reasoning && committee.reasoning.length ? sub("Committee Reasoning", ul(committee.reasoning)) : ""}
    <div class="hint">${esc(committee.recommendation)}</div>
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

  const sections = [];

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
    const committee = buildAITenderCommittee(ti);
    sections.push(block("AI", "AI Tender Committee",
      kv([
        ["Tender Quality Score", `${ti.tender_quality_score}/100`],
        ["Scope Clarity", `${ti.scope_clarity}%`],
        ["Commercial Clarity", `${ti.commercial_clarity}%`],
        ["Compliance Readiness", `${ti.compliance_readiness}%`],
        ["Vendor Participation Score", `${ti.vendor_participation_score ?? "—"}%`],
        ["Risk of Vendor Questions", ti.risk_of_vendor_questions],
        ["Estimated Vendor Participation", ti.estimated_vendor_participation],
        ["Publish Readiness", ti.publish_readiness],
        ["Document Status", ti.document_status],
      ]) +
      sub("AI Tender Committee", renderAITenderCommittee(committee)) +
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
  const delItems = (dels.deliverables || []).map(d =>
    `<div class="doc-item"><b>${esc(d.name)}</b><span>${esc(d.description || "")}${d.format ? " · Format: " + esc(d.format) : ""}${d.deadline_note ? " · " + esc(d.deadline_note) : ""}</span></div>`).join("");
  const tiers = (dels.escalation_tiers || []).map(t =>
    `<div class="milestone-row"><span>${esc(t.level)}</span><span class="muted2">${esc(t.trigger_delay)}</span><span>${esc(t.contact_role)}</span></div>`).join("");
  sections.push(block(10, "Deliverables",
    sub("Work Order Process", ul(dels.work_order_process)) +
    sub("Required Deliverables", delItems) +
    sub("Approval Process", para(dels.approval_process)) +
    sub("Reporting Requirements", ul(dels.reporting_requirements)) +
    sub("Escalation Matrix", tiers)));

  // 11. Timeline
  const miles = (tl.milestones || []).map(m =>
    `<div class="milestone-row"><span class="muted2">${esc(m.phase)}</span><span><b>${esc(m.milestone)}</b></span><span>${esc(m.target_date)}</span></div>`).join("");
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
    </div>
    ${sections.join("")}
  </div>`;
}

// ── DRAFT (seed) ───────────────────────────────────────────────────────────────
$("#draftBtn").addEventListener("click", () => {
  const seed = $("#draftSeed").value.trim();
  const template = selectedPdfTemplate();
  const form_overrides = collectDraftOverrides();
  runJob({
    target: "#draftResult",
    loadMain: "Drafting your tender…",
    loadSub: "Inventing the buyer brief, then drafting 4 sections in parallel — watch the console below",
    start: () => fetch("/api/jobs/draft", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ seed, template, form_overrides }),
    }).then(r => r.json()),
    render: renderDraft,
  });
});

// ── EXTRACT (and full pipeline from SOW) ─────────────────────────────────────────
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
  const project_name = $("#guidedProjectName").value.trim();
  const scope_text = $("#guidedScope").value.trim();
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
        $("#guidedScope").value = rewritten;
        $("#guidedStatus").textContent = "Scope rewritten. Edit it if needed, then generate the tender.";
      }
      return renderSowReview(result);
    },
  });
});

$("#guidedDraftBtn").addEventListener("click", () => {
  const project_name = $("#guidedProjectName").value.trim();
  const scope_text = $("#guidedScope").value.trim();
  const template = selectedPdfTemplate();
  const form_overrides = collectDraftOverrides();
  if (!project_name || !scope_text) {
    $("#draftResult").innerHTML = errorHTML("Add both the project name and scope of work first.");
    return;
  }
  runJob({
    target: "#draftResult",
    loadMain: "Drafting tender from approved SoW...",
    loadSub: "Extracting buyer form, then running the expert tender section agents",
    start: () => fetch("/api/jobs/draft-guided", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_name, scope_text, template, form_overrides }),
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
  buildDocChips();
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
      draftCategory.addEventListener("change", syncDraftSubcategories);
      syncDraftSubcategories();
    }
    setDefaultDraftDates();
    $("#kbCount").textContent = m.kb_count ?? (m.kb_available ? "—" : "0");
  } catch (e) {
    console.warn("meta load failed", e);
  }
})();
