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

// ── Navigation ────────────────────────────────────────────────────────────────
function show(view) {
  $$(".nav-item").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  $$(".view").forEach(v => v.classList.toggle("active", v.id === `view-${view}`));
  window.scrollTo({ top: 0 });
}
$$(".nav-item").forEach(b => b.addEventListener("click", () => show(b.dataset.view)));
$$("[data-go]").forEach(c => c.addEventListener("click", () => show(c.dataset.go)));

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

// ── Generic "run a job and render" wrapper ──────────────────────────────────────
async function runJob({ start, target, loadMain, loadSub, render }) {
  const box = $(target);
  box.innerHTML = loaderHTML(loadMain, loadSub);
  try {
    const { job_id } = await start();
    const result = await pollJob(job_id, { onTick: s => setTimer(box, s) });
    box.innerHTML = render(result);
    box.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    box.innerHTML = errorHTML(e.message);
  }
}

// ── DRAFT ───────────────────────────────────────────────────────────────────────
$("#draftBtn").addEventListener("click", () => {
  const seed = $("#draftSeed").value.trim();
  runJob({
    target: "#draftResult",
    loadMain: "Drafting your tender…",
    loadSub: "Inventing the buyer brief, then drafting 4 sections in parallel",
    start: () => fetch("/api/jobs/draft", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ seed }),
    }).then(r => r.json()),
    render: renderDraft,
  });
});

function renderDraft(result) {
  const o = (result.artifact && result.artifact.output) || {};
  const meta = o.metadata || {};
  const fid = result.file_id;
  const title = meta.title || "Tender Draft";

  const sections = [];
  const ov = o.project_overview || {};
  sections.push(block("1", "Project Overview", `
    ${ov.project_introduction ? `<p>${esc(ov.project_introduction)}</p>` : ""}
    ${ov.background ? `<h4>Background</h4><p>${esc(ov.background)}</p>` : ""}
    ${ov.context ? `<h4>Context</h4><p>${esc(ov.context)}</p>` : ""}`));

  const obj = o.objectives || {};
  sections.push(block("2", "Objectives", `
    ${listBlock("Business goals", obj.business_goals)}
    ${listBlock("Expected outcomes", obj.expected_outcomes)}
    ${listBlock("KPIs", obj.kpis)}`));

  const scope = o.scope_of_work || {};
  const cats = (scope.categories || []).map(c =>
    `<h4>${esc(c.name)}</h4><p>${esc(c.description || "")}</p>${listBlock("", c.requirements)}`).join("");
  sections.push(block("3", "Scope of Work", cats || "<p class='empty'>—</p>"));

  const ev = o.evaluation_criteria || {};
  sections.push(block("4", "Evaluation", `
    <dl class="kv">
      <dt>Model</dt><dd>${esc(ev.evaluation_model || meta.evaluation_model || "—")}</dd>
      <dt>Technical / Financial</dt><dd>${esc(ev.technical_weight ?? "—")} / ${esc(ev.financial_weight ?? "—")}</dd>
      <dt>Award basis</dt><dd>${esc(ev.award_basis || "—")}</dd>
    </dl>
    ${listBlock("Technical parameters", ev.technical_parameters)}`));

  const legal = o.general_terms || {};
  sections.push(block("5", "Legal & Terms", listBlock("Legal terms", legal.legal_terms) || "<p class='empty'>—</p>"));

  return `<div class="result">
    <div class="result-head">
      <div>
        <div class="result-title">${esc(title)}</div>
        <div class="hint" style="margin-top:4px">Reference: ${esc(meta.tender_id || "—")} · Issued by ${esc(meta.buyer_entity || "—")}</div>
      </div>
      <span class="badge draft dot">DRAFT · pending buyer approval</span>
    </div>
    <div class="toolbar" style="margin-bottom:16px">
      <a class="btn primary" href="/api/download/${fid}/pdf" target="_blank">⬇ Download PDF</a>
      <a class="btn ghost" href="/api/download/${fid}/json" target="_blank">⬇ JSON</a>
    </div>
    ${sections.join("")}
  </div>`;
}

function block(num, title, body) {
  return `<div class="section-block">
    <div class="sb-head"><span class="num">${num}</span>${esc(title)}</div>
    <div class="sb-body prose">${body}</div>
  </div>`;
}
function listBlock(label, items) {
  if (!items || !items.length) return label ? `` : "";
  const lis = items.map(i => `<li>${esc(typeof i === "string" ? i : (i.criterion || JSON.stringify(i)))}</li>`).join("");
  return `${label ? `<h4>${esc(label)}</h4>` : ""}<ul class="ul">${lis}</ul>`;
}

// ── EXTRACT ───────────────────────────────────────────────────────────────────
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
        <dt>Submission deadline</dt><dd>${esc(f.submission_deadline || "—")}</dd>
        <dt>Estimated value</dt><dd>${f.estimated_value_sar ? "SAR " + Number(f.estimated_value_sar).toLocaleString() : "—"}</dd>
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
        <dt>Name match</dt><dd>${v.name_match ? "Yes" : "No"} (${Math.round((v.name_match_confidence||0)*100)}% confidence)</dd>
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
        <p class="prose" style="margin:0">${esc((dq.reasons||[]).join("; "))}</p></div>`;
    }
    const bar = (label, val) => `<div class="bar-row"><span>${label}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${Math.max(0,Math.min(100,val))}%"></div></div>
      <span style="text-align:right">${Number(val).toFixed(0)}</span></div>`;
    return `<div class="vendor-card">
      <div class="vc-head"><div class="vc-name">${esc(name)}</div>
        <span class="badge ${s.risk_level==='low'?'ok':s.risk_level==='medium'?'warn':'bad'} dot">risk: ${esc(s.risk_level)}</span></div>
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
          <span class="hit-score">${(h.score*100).toFixed(0)}% match</span>
        </div>
        <div class="hit-text">${esc(h.text)}</div>
      </div>`).join("")}</div>`;
  } catch (e) { box.innerHTML = errorHTML(e.message); }
}

// ── Boot: load metadata ──────────────────────────────────────────────────────────
(async function init() {
  buildDocChips();
  try {
    const m = await fetch("/api/meta").then(r => r.json());
    $("#envModel").textContent = m.model;
    $("#envEmbed").textContent = m.embed_model;
    $("#envKb").textContent = m.kb_available ? "ready" : "empty";
    // category dropdown
    const sel = $("#vCategory");
    sel.innerHTML = Object.keys(m.categories || {}).map(c => `<option>${esc(c)}</option>`).join("");
    $("#kbCount").textContent = m.kb_count ?? (m.kb_available ? "—" : "0");
  } catch (e) {
    console.warn("meta load failed", e);
  }
})();
