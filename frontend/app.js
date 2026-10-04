"use strict";
const API_BASE = window.DIAR_API_BASE || "http://127.0.0.1:8000";
const CURRENT_SCHEMA_VERSION = 3;
const state = { report: null, loading: false, saving: false, benchmarks: [], history: [], limits: {max_pdf_bytes:5 * 1024 * 1024, max_pdf_pages:30, max_text_chars:50000, activity_days:180} };
const $ = id => document.getElementById(id);
function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  Object.entries(attrs).forEach(([key, value]) => {
    if (key.startsWith("on")) node.addEventListener(key.slice(2).toLowerCase(), value);
    else if (value !== false && value != null) node.setAttribute(key, value === true ? "" : value);
  });
  children.forEach(child => { if (child != null) node.append(child instanceof Node ? child : String(child)); });
  return node;
}
const panel = (title, children) => el("section", {class:"panel"}, [el("h2", {}, [title]), ...children]);
const note = text => el("p", {class:"notice"}, [text]);
const button = (label, action, attrs = {}) => el("button", {type:"button", class:"secondary", onClick:action, ...attrs}, [label]);
const details = (title, children) => el("details", {}, [el("summary", {}, [title]), ...children]);
function chips(items, kind = "") { return el("div", {class:"chip-row"}, (items || []).length ? items.map(x => el("span", {class:"chip " + kind}, [x])) : [note("None recorded.")]); }
function error(message) { $("error-box").textContent = message || ""; $("error-box").hidden = !message; }
async function request(path, options = {}) {
  let response;
  try { response = await fetch(API_BASE + path, {...options, signal:AbortSignal.timeout(120000)}); }
  catch (e) { throw new Error(e.name === "TimeoutError" ? "The request timed out. Check the backend, then retry." : "Cannot reach the backend. Start it and select Retry connection."); }
  if (!response.ok) {
    let data = {}; try { data = await response.json(); } catch (_) { /* Non-JSON server error. */ }
    const detail = data.detail;
    throw new Error(typeof detail === "string" ? detail : detail?.message || (Array.isArray(detail) ? detail.map(x => x.msg).join("; ") : "Request failed (" + response.status + ")."));
  }
  return response.status === 204 ? null : response.json();
}
function scoreCard(title, label, score) {
  const known = typeof score === "number" && Number.isFinite(score);
  const card = el("div", {class:"score-card"}, [el("div", {class:"label"}, [title]), el("div", {class:"val"}, [known ? label || "Assessed" : "Not assessed"])]);
  if (known) {
    const percent = Math.round(Math.max(0, Math.min(1, score)) * 100);
    const bar = el("div", {class:"bar-fill"}); bar.style.width = percent + "%"; bar.style.background = percent >= 66 ? "var(--match)" : percent >= 33 ? "var(--beacon)" : "var(--gap)";
    card.append(el("div", {class:"bar-track", role:"meter", "aria-label":title, "aria-valuemin":0, "aria-valuemax":100, "aria-valuenow":percent}, [bar]));
  }
  return card;
}
function observationCard(title, value, description) {
  return el("div", {class:"observation-card"}, [
    el("div", {class:"label"}, [title]),
    el("div", {class:"val"}, [value]),
    description ? el("div", {class:"observation-detail"}, [description]) : null
  ].filter(Boolean));
}
function formatLabel(value) {
  return String(value || "not recorded").replaceAll("_", " ");
}
function formatDate(value) {
  if (!value) return "not recorded";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleDateString(undefined, {year:"numeric", month:"short", day:"numeric"});
}
function asFiniteNumber(...values) {
  const value = values.find(candidate => typeof candidate === "number" && Number.isFinite(candidate));
  return value == null ? null : value;
}
function membershipContent(memberships, emptyMessage) {
  if (!memberships || !Object.keys(memberships).length) return [note(emptyMessage)];
  if (Object.values(memberships).every(value => typeof value === "number")) {
    return [note("Membership degrees describe overlap in the scoring method; they are not probabilities or public grades."),
      el("ul", {class:"source-list"}, Object.entries(memberships).map(([label, value]) => el("li", {}, [label + ": " + value.toFixed(3)])))];
  }
  return [note("Membership degrees describe overlap in the scoring method; they are not probabilities or public grades."), ...Object.entries(memberships).map(([dimension, degrees]) => el("div", {class:"evidence-item"}, [
    el("strong", {}, [dimension.replaceAll("_", " ")]),
    Object.keys(degrees || {}).length ? el("ul", {class:"source-list"}, Object.entries(degrees).map(([label, value]) => el("li", {}, [label + ": " + (typeof value === "number" ? value.toFixed(3) : "not assessed")]))) : note("Insufficient evidence; no membership assigned.")
  ]))];
}
function legacyMembershipDetails(ga) {
  const memberships = ga.memberships || ga.fuzzy_memberships;
  return details("Fuzzy membership details", membershipContent(memberships, "Membership degrees were not stored in this legacy report."));
}
function contentDetails(profile, sources) {
  if (!profile.content_completeness) return [note("Content completeness was not recorded in this legacy report.")];
  return [note("Content completeness describes recognised fields in each supplied source. It is separate from source coverage and competence."),
    el("ul", {class:"source-list"}, Object.entries(profile.content_completeness).map(([source, complete]) => {
      const status = sources?.[source]?.status;
      return el("li", {}, [source + ": " + (status === "not_supplied" || status === "failed" ? "not assessed" : complete ? "expected content detected" : "some expected content not detected")]);
    }))];
}
function recommendations(items) {
  if (!items?.length) return note("No recommendations recorded. This does not establish complete competence.");
  return el("div", {}, items.map((r, i) => el("article", {class:"rec-item"}, [
    el("div", {class:"rec-rank"}, [i + 1]), el("div", {}, [
      el("div", {class:"rec-title"}, [r.recommendation || r.title || r.id]),
      el("div", {class:"rec-meta"}, [el("span", {class:"prio " + (r.priority || "low")}, [r.priority || "action"]), el("span", {class:"rule-id"}, [r.rule_id || ""])]),
      details("Why this action?", [note(r.explanation || "No explanation stored.")])
    ])
  ])));
}
function focusAnalysisForm() {
  const form = $("analyze-form");
  form?.scrollIntoView({behavior:"smooth", block:"start"});
  $("benchmark-select")?.focus({preventScroll:true});
}
function reportVersion(report) {
  const value = Number(report?.schema_version);
  return Number.isInteger(value) ? value : null;
}
function renderLegacyReport(r) {
  const p = r.digital_identity_profile || {}, bc = r.benchmark_comparison || {}, ga = r.gap_analysis || {}, va = r.visibility_assessment || {};
  const root = el("div");
  root.append(el("section", {class:"panel legacy-banner", role:"note"}, [
    el("h2", {}, ["Historical report"]),
    el("p", {class:"legacy-title"}, ["Historical heuristic—not recalculated"]),
    note("This saved v2 or unversioned report uses the earlier keyword, completeness, and repository-activity heuristics. Its labels are preserved exactly for auditability and are not a current assessment."),
    el("div", {class:"actions"}, [button("Run a new analysis", focusAnalysisForm), note(r.id ? "Saved report #" + r.id + ". Historical data remains unchanged." : "Legacy reports are view-only and cannot be saved again.")]),
    details("Show historical heuristic grades", [
      el("div", {class:"score-row legacy-scores"}, [scoreCard("Skill match", ga.skill_match_label, ga.skill_match_score), scoreCard(reportVersion(r) === 2 ? "Source coverage" : "Profile completeness (legacy)", ga.profile_completeness_label, ga.profile_completeness_score), scoreCard("GitHub push activity proxy", ga.github_activity_label, ga.github_activity_score)]),
      note("These scores describe the old heuristic's alignment of supplied evidence, not professional competence or contribution activity."),
      legacyMembershipDetails(ga)
    ])
  ]));
  root.append(panel("Historical assessment context", [
    note((r.benchmark_identity || bc.benchmark_identity || "Saved assessment") + " · " + (r.visibility_level || va.selected_level || "Visibility not recorded")),
    note("The sections below reproduce the evidence and recommendations stored with the historical report.")
  ]));
  const sources = r.source_statuses || p.source_statuses;
  const sourceItems = sources ? Object.entries(sources).map(([name, value]) => el("li", {}, [name + ": " + value.status.replaceAll("_", " ") + (value.reason ? " — " + value.reason : "")])) : [el("li", {}, ["Legacy report: detailed source status was not recorded."])];
  root.append(panel("Sources and warnings", [el("ul", {class:"source-list"}, sourceItems), r.github_warning ? el("p", {class:"warning"}, [r.github_warning]) : null, ...(r.clarification_requests || []).map(x => el("p", {class:"warning"}, [x]))].filter(Boolean)));
  root.append(panel("Content completeness", contentDetails(p, sources)));
  if (p.github?.username || p.github?.repo_count != null) root.append(panel("GitHub evidence", [
    note((p.github.username ? "@" + p.github.username + " · " : "") + (p.github.repo_count ?? "Unknown number of") + " non-fork repositories · " + (p.github.recently_active_repo_count ?? "Unknown number of") + " recently pushed repositories."),
    note("Activity uses repository push timestamps" + (p.github.activity_window_days ? " within the last " + p.github.activity_window_days + " days" : " within the configured recent window") + ". It does not measure contribution quality or all work undertaken."),
    chips(p.github.languages)
  ]));
  root.append(panel("Benchmark comparison", [note(bc.benchmark_description || ""), el("h3", {class:"subhead"}, ["Matched skills"]), chips(bc.matched_skills, "match"), el("h3", {class:"subhead"}, ["Required skills not evidenced"]), chips(bc.missing_required_skills, "gap"), el("h3", {class:"subhead"}, ["Preferred skills not evidenced"]), chips(bc.missing_preferred_skills)]));
  root.append(panel("Visibility and explanation", [...(va.findings || []).map(x => el("p", {class:"visibility-note"}, [x])), note(r.explanation_summary?.narrative || "No narrative stored.")]));
  root.append(panel("Suggested action plan", renderPlan(r.suggested_plan)));
  root.append(panel("Ranked recommendations", [recommendations(r.recommendations)]));
  const evidence = r.evidence || p.evidence || [];
  root.append(panel("Consolidated profile and evidence", [chips(p.skills, "match"), details("Supporting and uncertain skill mentions (" + evidence.length + ")", evidence.length ? evidence.map(e => el("div", {class:"evidence-item"}, [el("strong", {}, [e.skill]), note([e.source, e.assertion, e.method].filter(Boolean).join(" · ")), el("blockquote", {}, [e.excerpt || "No excerpt stored."])])) : [note("Evidence excerpts were not recorded for this report.")])]));
  return root;
}
function scopeList(scope, key) {
  const aliases = {
    usable:["usable", "usable_sources", "analysed", "analyzed"],
    partial:["partial", "partial_sources"],
    failed:["failed", "failed_sources"],
    unsupplied:["unsupplied", "unsupplied_sources", "not_supplied"]
  }[key] || [key];
  for (const alias of aliases) {
    if (Array.isArray(scope?.[alias])) return scope[alias];
  }
  return [];
}
function scopeCount(scope, key, list) {
  const aliases = {
    usable:["usable_count", "analysed_count", "analyzed_count"],
    partial:["partial_count"],
    failed:["failed_count"],
    unsupplied:["unsupplied_count", "not_supplied_count"]
  }[key] || [];
  for (const alias of aliases) {
    const value = asFiniteNumber(scope?.counts?.[key], scope?.[alias]);
    if (value != null) return value;
  }
  return list.length;
}
function sourceStatuses(report, scope) {
  const stored = report.source_statuses || report.digital_identity_profile?.source_statuses;
  if (stored && Object.keys(stored).length) return stored;
  const statuses = {};
  for (const key of ["usable", "partial", "failed", "unsupplied"]) {
    for (const item of scopeList(scope, key)) {
      const name = typeof item === "string" ? item : item.name || item.source;
      if (name) statuses[name] = typeof item === "string" ? {status:key === "usable" ? "analysed" : key} : {status:item.status || (key === "usable" ? "analysed" : key), reason:item.reason};
    }
  }
  return statuses;
}
function sourceScopeModel(report, scope) {
  const lists = Object.fromEntries(["usable", "partial", "failed", "unsupplied"].map(key => [key, scopeList(scope, key)]));
  const counts = Object.fromEntries(Object.entries(lists).map(([key, list]) => [key, scopeCount(scope, key, list)]));
  const statuses = sourceStatuses(report, scope);
  if (!Object.keys(statuses).length && !Object.values(counts).some(Boolean)) {
    return {counts, statuses, analysed:null, total:null};
  }
  if (!Object.values(counts).some(Boolean)) {
    Object.values(statuses).forEach(value => {
      const status = value?.status;
      if (status === "analysed" || status === "analyzed" || status === "usable") counts.usable += 1;
      else if (status === "not_supplied" || status === "unsupplied") counts.unsupplied += 1;
      else if (Object.hasOwn(counts, status)) counts[status] += 1;
    });
  }
  const analysed = asFiniteNumber(scope?.usable_count, scope?.analysed_count, scope?.analyzed_count, scope?.counts?.analysed, scope?.counts?.analyzed) ?? counts.usable;
  const total = asFiniteNumber(scope?.total_count, scope?.total_sources, scope?.counts?.total) ?? counts.usable + counts.partial + counts.failed + counts.unsupplied;
  return {counts, statuses, analysed, total};
}
function renderScopeBanner(report, scope) {
  const model = sourceScopeModel(report, scope);
  const countText = model.analysed == null || model.total == null ? "Source scope was not recorded." : model.analysed + " of " + model.total + " sources yielded analysed evidence.";
  const limited = model.counts.partial + model.counts.failed + model.counts.unsupplied > 0;
  const statusItems = Object.entries(model.statuses).map(([name, value]) => el("li", {}, [
    el("strong", {}, [formatLabel(name)]),
    " — " + formatLabel(value?.status) + (value?.reason ? ": " + value.reason : "")
  ]));
  return el("aside", {class:"scope-banner" + (limited ? " limited" : ""), role:"note", "aria-label":"Evidence scope"}, [
    el("strong", {}, ["Evidence scope"]),
    el("p", {}, [countText + " Results describe only the supplied, successfully processed evidence; they are not an overall judgement of expertise."]),
    statusItems.length ? el("ul", {class:"scope-statuses"}, statusItems) : null
  ].filter(Boolean));
}
function capabilityResults(benchmark) {
  const value = benchmark.capability_results || benchmark.capabilities || benchmark.results;
  if (Array.isArray(value)) return value;
  if (value && typeof value === "object") return Object.entries(value).map(([id, result]) => ({id, ...(result || {})}));
  return [];
}
function capabilityCounts(benchmark, capabilities) {
  const counts = benchmark.capability_counts || benchmark.counts || {};
  const stateCount = state => capabilities.filter(item => item.state === state || item.status === state).length;
  return {
    evidenced:asFiniteNumber(counts.evidenced, benchmark.evidenced_count, benchmark.evidenced_capability_count) ?? stateCount("evidenced"),
    weak:asFiniteNumber(counts.weakly_evidenced, counts.weak, benchmark.weakly_evidenced_count) ?? stateCount("weakly_evidenced"),
    total:asFiniteNumber(counts.total, benchmark.total_count, benchmark.total_capabilities) ?? capabilities.length
  };
}
function evidenceId(record) {
  return record?.id || record?.evidence_id || record?.stable_id || null;
}
function evidenceForCapability(capability, evidenceIndex) {
  const inline = capability.supporting_evidence || capability.evidence;
  const records = Array.isArray(inline) ? inline : [];
  const references = capability.evidence_ids || capability.supporting_evidence_ids || capability.evidence_refs || [];
  const resolved = records.map(item => typeof item === "string" ? evidenceIndex.get(item) : item).filter(Boolean);
  for (const reference of references) {
    const record = evidenceIndex.get(typeof reference === "string" ? reference : evidenceId(reference));
    if (record && !resolved.includes(record)) resolved.push(record);
  }
  return resolved;
}
function renderEvidenceRecord(record) {
  const artifact = record.artifact_type || record.artifact || "source text";
  const origin = record.origin || record.source || "unknown source";
  const repository = record.repository_locator || record.repository || record.repository_name || record.repo;
  const method = record.extraction_method || record.method;
  const strength = asFiniteNumber(record.strength, record.evidence_strength);
  return el("div", {class:"provenance-item"}, [
    el("div", {class:"provenance-heading"}, [record.skill || record.concept || record.term || evidenceId(record) || "Evidence"]),
    el("div", {class:"provenance-meta"}, [[origin, artifact, repository, method, strength == null ? null : "strength " + strength.toFixed(2)].filter(Boolean).join(" · ")]),
    record.excerpt ? el("blockquote", {}, [record.excerpt]) : note("No excerpt stored.")
  ]);
}
function renderCapability(capability, evidenceIndex) {
  const name = capability.name || capability.label || capability.capability || capability.title || capability.id || "Capability";
  const state = capability.state || capability.status || "not_assessed";
  const strength = asFiniteNumber(capability.strength, capability.satisfaction, capability.evidence_strength);
  const matched = capability.matched_concepts || capability.matched_skills || capability.matches || [];
  const evidence = evidenceForCapability(capability, evidenceIndex);
  const reasoning = capability.reason || capability.explanation || capability.limitation;
  return el("article", {class:"capability-item", "data-state":state}, [
    el("div", {class:"capability-heading"}, [el("h3", {}, [name]), el("span", {class:"state-badge"}, [formatLabel(state)])]),
    el("p", {class:"capability-meta"}, [[strength == null ? null : "Evidence strength " + strength.toFixed(2), typeof capability.weight === "number" ? "Benchmark weight " + Math.round(capability.weight * 100) + "%" : null].filter(Boolean).join(" · ") || "No numeric evidence strength stored."]),
    matched.length ? chips(matched, state === "evidenced" ? "match" : "") : null,
    reasoning ? note(reasoning) : null,
    (state === "evidenced" || state === "weakly_evidenced" || state === "explicit_gap") ? details("Evidence provenance (" + evidence.length + ")", evidence.length ? evidence.map(renderEvidenceRecord) : [note("No linked provenance was stored for this capability.")]) : null
  ].filter(Boolean));
}
function githubRecencyModel(recency) {
  const availability = recency?.availability;
  const owned = asFiniteNumber(recency?.owned_public_non_fork_repository_count, recency?.owned_non_fork_repository_count, recency?.owned_repository_count, recency?.repository_count, recency?.repo_count);
  const recent = asFiniteNumber(recency?.recently_pushed_owned_repository_count, recency?.recently_pushed_repository_count, recency?.recent_repository_count, recency?.recently_active_repo_count);
  const windowDays = asFiniteNumber(recency?.window_days, recency?.activity_window_days, recency?.window);
  const latest = recency?.last_owned_repository_push_at || recency?.latest_repository_push_at || recency?.latest_push_at || recency?.most_recent_push_at;
  const available = availability === true || availability === "available" || (availability == null && (owned != null || recent != null || latest));
  return {available, availability, owned, recent, windowDays, latest};
}
function renderMethodDetails(benchmark) {
  const memberships = benchmark.fuzzy_memberships || benchmark.memberships;
  const method = typeof benchmark.method === "string" ? benchmark.method : benchmark.method?.description;
  const limitations = benchmark.limitation || benchmark.limitations || benchmark.limitation_text;
  const limitationText = Array.isArray(limitations) ? limitations.join(" ") : limitations;
  return details("Method details", [
    method ? note(method) : note("The report did not store a scoring-method description."),
    limitationText ? el("p", {class:"warning"}, [limitationText]) : null,
    el("h3", {class:"subhead"}, ["Fuzzy memberships"]),
    ...membershipContent(memberships, "No fuzzy membership degrees were stored.")
  ].filter(Boolean));
}
function renderV3Report(r) {
  const assessment = r.assessment || {};
  const benchmark = assessment.benchmark_evidence || {};
  const scope = assessment.source_scope || {};
  const recency = assessment.github_portfolio_recency || {};
  const capabilities = capabilityResults(benchmark);
  const counts = capabilityCounts(benchmark, capabilities);
  const scopeModel = sourceScopeModel(r, scope);
  const github = githubRecencyModel(recency);
  const allEvidence = r.evidence || r.digital_identity_profile?.evidence || [];
  const evidenceIndex = new Map(allEvidence.map(record => [evidenceId(record), record]).filter(([id]) => id));
  const root = el("div", {class:"v3-report"});
  root.append(renderScopeBanner(r, scope));
  root.append(panel("Evidence assessment", [
    note((r.benchmark_identity || "Saved assessment") + " · " + (r.visibility_level || "Visibility not recorded") + " · report schema v" + CURRENT_SCHEMA_VERSION),
    el("div", {class:"actions"}, [
      button(r.id ? "Saved report #" + r.id : state.saving ? "Saving…" : "Save report", saveReport, {disabled:!!r.id || state.saving}),
      note(r.id ? "Stored in the local backend database." : "Not saved. Save only if you want this report retained locally.")
    ]),
    el("div", {class:"observation-row"}, [
      observationCard("Benchmark evidence detected", counts.total ? counts.evidenced + " of " + counts.total : "Not assessed", counts.weak ? counts.weak + " additional capability group" + (counts.weak === 1 ? " is" : "s are") + " weakly evidenced." : "Capability groups with evidence strength of at least 0.60."),
      observationCard("Sources analysed", scopeModel.analysed == null || scopeModel.total == null ? "Not recorded" : scopeModel.analysed + " of " + scopeModel.total, scopeModel.counts.partial ? scopeModel.counts.partial + " source" + (scopeModel.counts.partial === 1 ? " was" : "s were") + " only partially analysed." : "Usable and partial sources are counted as analysed."),
      observationCard("GitHub portfolio recency", github.available && github.owned != null && github.recent != null ? github.recent + " of " + github.owned : "Not available", github.available ? "Owned public non-fork repositories pushed" + (github.windowDays ? " within " + github.windowDays + " days" : " in the recorded window") + "; latest push " + formatDate(github.latest) + "." : "GitHub repository recency was not available for this report.")
    ]),
    note("These are observations about supplied evidence. They are not grades of expertise, employability, reputation, or professional activity."),
    renderMethodDetails(benchmark)
  ]));
  root.append(panel("Benchmark capability evidence", [
    r.benchmark_comparison?.benchmark_description ? note(r.benchmark_comparison.benchmark_description) : null,
    capabilities.length ? el("div", {class:"capability-list"}, capabilities.map(capability => renderCapability(capability, evidenceIndex))) : note("No capability results were stored.")
  ].filter(Boolean)));
  if (github.available || github.availability) root.append(panel("GitHub portfolio recency detail", [
    el("dl", {class:"fact-list"}, [
      el("div", {}, [el("dt", {}, ["Availability"]), el("dd", {}, [formatLabel(github.availability || (github.available ? "available" : "unavailable"))])]),
      el("div", {}, [el("dt", {}, ["Owned public non-fork repositories"]), el("dd", {}, [github.owned ?? "not recorded"])]),
      el("div", {}, [el("dt", {}, ["Recently pushed repositories"]), el("dd", {}, [github.recent ?? "not recorded"])]),
      el("div", {}, [el("dt", {}, ["Observation window"]), el("dd", {}, [github.windowDays ? github.windowDays + " days" : "not recorded"])]),
      el("div", {}, [el("dt", {}, ["Latest repository push"]), el("dd", {}, [formatDate(github.latest)])])
    ]),
    note("Repository push timestamps cover owned public non-fork repositories only. They do not measure contribution quality, organisation work, private work, reviews, issues, or overall professional activity.")
  ]));
  const va = r.visibility_assessment || {};
  root.append(panel("Visibility and explanation", [...(va.findings || []).map(x => el("p", {class:"visibility-note"}, [x])), note(r.explanation_summary?.narrative || "No narrative stored.")]));
  root.append(panel("Suggested action plan", renderPlan(r.suggested_plan)));
  root.append(panel("Ranked recommendations", [recommendations(r.recommendations)]));
  root.append(panel("Evidence index", [details("All stored evidence (" + allEvidence.length + ")", allEvidence.length ? allEvidence.map(renderEvidenceRecord) : [note("No evidence records were stored.")])]));
  return root;
}
function renderUnsupportedReport(r) {
  return panel("Unsupported report version", [
    el("p", {class:"warning"}, ["This report uses schema v" + reportVersion(r) + ", but this interface supports v" + CURRENT_SCHEMA_VERSION + ". It has not been reinterpreted."]),
    button("Run a new analysis", focusAnalysisForm)
  ]);
}
function renderReport(r) {
  const version = reportVersion(r);
  if (version === CURRENT_SCHEMA_VERSION) return renderV3Report(r);
  if (version == null || version <= 2) return renderLegacyReport(r);
  return renderUnsupportedReport(r);
}
function renderPlan(plan) {
  if (!plan) return [note("This legacy report has no action plan. Run a new analysis to generate one.")];
  return [note("Status: " + plan.status + ". Total relative effort: " + (plan.total_cost ?? "not available") + "."),
    note(plan.optimal ? "Minimum effort within this action catalogue and its assumptions." : "This result does not claim a minimum-cost solution."),
    note("Suggested actions address documentation or development objectives; they do not change observed evidence or prove competence."),
    el("ol", {}, (plan.steps || []).map(step => el("li", {class:"evidence-item"}, [el("strong", {}, [step.title || step.id]), note("Relative effort: " + step.cost), details("Objectives and reasoning", [chips(step.objectives), note(step.explanation || "")])]))),
    ...(plan.unresolved_objectives?.length ? [el("p", {class:"warning"}, ["Unresolved: " + plan.unresolved_objectives.join(", ")])] : []),
    ...(plan.fallback_recommendations?.length ? [details("Fallback ranked actions", [recommendations(plan.fallback_recommendations)])] : [])];
}
function renderResults() {
  const results = $("results"); results.replaceChildren(); results.setAttribute("aria-busy", String(state.loading));
  if (state.loading) results.append(el("div", {class:"loading", role:"status"}, [el("span", {class:"spinner", "aria-hidden":"true"}), "Analysing… Your previous report remains below."]));
  results.append(state.report ? renderReport(state.report) : el("div", {class:"empty"}, [el("h2", {}, ["No report yet"]), note("Supply at least one source, select a career and visibility preference, then run an analysis.")]));
}
function updateRun() { $("run-btn").disabled = state.loading || !$("benchmark-select").value || !($("resume").files.length || $("github").value.trim() || $("linkedin").value.trim()); $("run-btn").textContent = state.loading ? "Analysing…" : "Run Digital Identity Analysis"; }
async function analyse(event) {
  event.preventDefault(); error(null);
  const file = $("resume").files[0], username = $("github").value.trim(), text = $("linkedin").value.trim();
  if (!file && !username && !text) return error("Supply at least one input source.");
  if (file && (!/\.pdf$/i.test(file.name) || file.size > state.limits.max_pdf_bytes)) return error("Choose a PDF up to " + (state.limits.max_pdf_bytes / (1024 * 1024)).toLocaleString() + " MB.");
  if (username && !/^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?$/.test(username)) return error("Enter a GitHub username, not a profile URL (maximum 39 characters).");
  if (text.length > state.limits.max_text_chars) return error("LinkedIn text must be at most " + state.limits.max_text_chars.toLocaleString() + " characters.");
  const form = new FormData($("analyze-form")); if (!file) form.delete("resume"); form.set("github_username", username); form.set("linkedin_text", text);
  state.loading = true; updateRun(); renderResults();
  try { state.report = await request("/api/analyze", {method:"POST", body:form}); }
  catch (e) { error(e.message); }
  finally { state.loading = false; updateRun(); renderResults(); }
}
async function saveReport() {
  if (!state.report || state.report.id || state.saving || reportVersion(state.report) !== CURRENT_SCHEMA_VERSION) return;
  state.saving = true; const report = state.report; renderResults(); error(null);
  try { const saved = await request("/api/reports", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(report)}); if (state.report === report) state.report = saved; await loadHistory(); }
  catch (e) { error(e.message); }
  finally { state.saving = false; renderResults(); }
}
async function loadHistory() {
  $("history-status").textContent = "Loading…";
  try { state.history = await request("/api/reports"); $("history-status").textContent = state.history.length ? "Stored in this local backend; no accounts or shared-access protection." : "No saved reports."; renderHistory(); }
  catch (e) { $("history-status").textContent = e.message; }
}
function renderHistory() {
  $("history-list").replaceChildren(...state.history.map(r => {
    const version = reportVersion(r);
    const versionLabel = version === CURRENT_SCHEMA_VERSION ? "v" + CURRENT_SCHEMA_VERSION : version == null || version <= 2 ? "historical heuristic" : "schema v" + version;
    return el("article", {class:"history-item"}, [note("#" + r.id + " · " + r.benchmark_identity + " · " + versionLabel + " · " + (r.created_at || "Date unknown")), el("div", {class:"actions"}, [button("Open #" + r.id, async () => { try { state.report = await request("/api/reports/" + r.id); error(null); renderResults(); $("results").focus(); } catch(e) { error(e.message); } }), button("Delete #" + r.id, async () => {
    if (!window.confirm("Delete saved report #" + r.id + " from the local database? This cannot be undone.")) return;
    try { await request("/api/reports/" + r.id, {method:"DELETE"}); if (state.report?.id === r.id) { state.report = {...state.report}; delete state.report.id; delete state.report.created_at; renderResults(); } await loadHistory(); } catch(e) { error(e.message); }
  })])]);
  }));
}
async function connect() {
  $("status-pill").textContent = "Connecting…";
  try {
    const [, benchmarks, limits] = await Promise.all([request("/api/health"), request("/api/benchmarks"), request("/api/config").catch(() => null)]); state.benchmarks = benchmarks;
    if (limits) Object.keys(state.limits).forEach(key => { if (Number.isInteger(limits[key]) && limits[key] > 0) state.limits[key] = limits[key]; });
    $("linkedin").maxLength = state.limits.max_text_chars;
    $("pdf-hint").textContent = "Up to " + (state.limits.max_pdf_bytes / (1024 * 1024)).toLocaleString() + " MB and " + state.limits.max_pdf_pages + " pages. Text-based PDF required; scanned documents need OCR outside DIAR.";
    const selected = $("benchmark-select").value;
    $("benchmark-select").replaceChildren(...benchmarks.map(b => el("option", {value:b.name}, [b.name])));
    if (benchmarks.some(b => b.name === selected)) $("benchmark-select").value = selected;
    $("benchmark-desc").textContent = benchmarks.find(b => b.name === $("benchmark-select").value)?.description || "";
    $("status-pill").textContent = "API online"; $("status-pill").className = "status-pill";
  } catch (e) { $("status-pill").textContent = "API offline — start the backend and retry"; $("status-pill").className = "status-pill off"; }
  updateRun();
}
function build() {
  const app = $("app");
  app.append(el("header", {class:"top"}, [el("div", {}, [el("div", {class:"eyebrow"}, ["DIAR · Digital Identity Analysis & Recommendation System"]), el("h1", {class:"display"}, ["Align your digital identity to where you're headed."]), note("Bring your professional evidence, choose a career, and explore explained recommendations.")]), el("div", {}, [el("div", {id:"status-pill", class:"status-pill", role:"status"}), button("Retry connection", connect)])]));
  const field = (label, id, tag, attrs = {}, extra = []) => [el("label", {for:id}, [label]), el(tag, {id, ...attrs}), ...extra];
  const form = el("form", {id:"analyze-form", class:"panel", onSubmit:analyse, onInput:updateRun}, [el("h2", {}, ["Input sources"]),
    ...field("Resume (PDF)", "resume", "input", {type:"file", name:"resume", accept:".pdf,application/pdf", "aria-describedby":"pdf-hint"}), el("p", {id:"pdf-hint", class:"hint"}, ["Up to 5 MB and 30 pages. Text-based PDF required; scanned documents need OCR outside DIAR."]),
    ...field("GitHub username", "github", "input", {type:"text", name:"github_username", placeholder:"octocat", maxlength:39, autocomplete:"off"}),
    ...field("LinkedIn profile text", "linkedin", "textarea", {name:"linkedin_text", maxlength:50000, placeholder:"Paste headline, skills, work experience, and projects…"}),
    el("label", {for:"linkedin-visibility"}, ["Visibility of pasted LinkedIn information"]), el("select", {id:"linkedin-visibility", name:"linkedin_visibility"}, [el("option", {value:"unverified"}, ["Unknown / unverified"]), el("option", {value:"public"}, ["I confirm this information is public"]), el("option", {value:"private"}, ["Private / restricted"])]),
    ...field("Benchmark identity", "benchmark-select", "select", {name:"benchmark_identity", required:true, onChange:() => { $("benchmark-desc").textContent = state.benchmarks.find(b => b.name === $("benchmark-select").value)?.description || ""; updateRun(); }}), el("p", {id:"benchmark-desc", class:"hint"}),
    el("fieldset", {}, [el("legend", {}, ["Preferred visibility level"]), el("div", {class:"radio-row"}, ["Fully Public", "Semi-Public", "Privacy Focused"].map((level, i) => el("label", {class:"radio-opt", for:"visibility-" + i}, [el("input", {type:"radio", id:"visibility-" + i, name:"visibility_level", value:level, checked:level === "Semi-Public", required:true}), level])))]),
    note("Analysis is not automatically saved. GitHub is fetched publicly; uploaded and pasted evidence is processed by your local backend."),
    el("button", {type:"submit", id:"run-btn", class:"run"}, ["Run Digital Identity Analysis"]), el("div", {id:"error-box", class:"error-box", role:"alert", hidden:true})]);
  const history = panel("Saved reports", [button("Refresh history", loadHistory), el("p", {id:"history-status", class:"notice", role:"status"}, ["Select Refresh history to view local reports."]), el("div", {id:"history-list"})]);
  app.append(el("div", {class:"grid"}, [el("div", {}, [form, history]), el("div", {id:"results", tabindex:"-1", "aria-label":"Analysis results"})]));
  app.append(el("footer", {}, ["DIAR PROTOTYPE · Heuristic extraction · Fuzzy scoring · Rules · Uniform-cost planning"]));
  renderResults(); updateRun(); connect();
}
build();
