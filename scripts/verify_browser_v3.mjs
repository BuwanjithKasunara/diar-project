const targets = await fetch("http://127.0.0.1:9222/json/list").then((response) => response.json());
const target = targets.find((item) => item.type === "page" && item.url.startsWith("http://127.0.0.1:5173"));
if (!target) throw new Error("DIAR browser target not found.");
console.error("browser target selected");

const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, {once: true});
  socket.addEventListener("error", reject, {once: true});
});
console.error("browser websocket connected");

let sequence = 0;
const pending = new Map();
const consoleErrors = [];
const networkFailures = [];
socket.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);
  if (message.id && pending.has(message.id)) {
    const {resolve, reject} = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) reject(new Error(message.error.message));
    else resolve(message.result);
  }
  if (message.method === "Runtime.consoleAPICalled" && message.params.type === "error") {
    consoleErrors.push(message.params.args.map((arg) => arg.value ?? arg.description ?? "").join(" "));
  }
  if (message.method === "Runtime.exceptionThrown") {
    consoleErrors.push(message.params.exceptionDetails.text);
  }
  if (message.method === "Network.loadingFailed") {
    networkFailures.push(message.params.errorText);
  }
});

function call(method, params = {}) {
  const id = ++sequence;
  const response = new Promise((resolve, reject) => pending.set(id, {resolve, reject}));
  socket.send(JSON.stringify({id, method, params}));
  return response;
}

async function evaluate(expression) {
  const result = await call("Runtime.evaluate", {expression, awaitPromise: true, returnByValue: true});
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
  return result.result.value;
}

async function waitFor(expression, timeoutMs = 15000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (await evaluate(expression)) return;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  const diagnostic = await evaluate(`({body:document.body.innerText.slice(-3000), error:document.querySelector("#error-box")?.textContent})`);
  console.error(JSON.stringify({timeout: expression, diagnostic, consoleErrors, networkFailures}, null, 2));
  socket.close();
  process.exit(1);
}

await call("Runtime.enable");
console.error("runtime enabled");
await call("Network.enable");
await call("Page.enable");
await call("Emulation.setDeviceMetricsOverride", {width: 1280, height: 900, deviceScaleFactor: 1, mobile: false});
await call("Page.reload", {ignoreCache: true});
console.error("page reloaded");
await waitFor(`document.readyState === "complete" && document.querySelector("#status-pill")?.textContent === "API online"`);
console.error("app connected");

await evaluate(`(() => {
  const input = document.querySelector("#linkedin");
  input.value = "Skills: Python, machine learning, PyTorch, LLM, Docker, SQL\\nProjects:\\nBuilt and evaluated a retrieval-augmented AI model API.";
  input.dispatchEvent(new Event("input", {bubbles: true}));
  document.querySelector("#benchmark-select").value = "AI Engineer";
  document.querySelector("#visibility-2").click();
  document.querySelector("#analyze-form").requestSubmit();
  return true;
})()`);
await waitFor(`document.querySelector("#results")?.textContent.includes("Benchmark evidence detected")`, 30000);
console.error("analysis rendered");

const desktop = await evaluate(`(() => {
  const text = document.querySelector("#results").textContent;
  const details = [...document.querySelectorAll("#results details")].map((item) => ({summary:item.querySelector("summary")?.textContent, open:item.open}));
  const ids = [...document.querySelectorAll("[id]")].map((node) => node.id);
  const duplicateIds = ids.filter((id, index) => ids.indexOf(id) !== index);
  const unlabeled = [...document.querySelectorAll("input, textarea, select")].filter((node) => !node.labels?.length && !node.getAttribute("aria-label")).map((node) => node.id || node.name);
  return {
    viewport: [innerWidth, innerHeight],
    noHorizontalOverflow: document.documentElement.scrollWidth <= innerWidth,
    benchmarkObservation: text.match(/Benchmark evidence detected[\\s\\S]{0,80}/)?.[0] ?? null,
    sourceObservation: text.match(/Sources analysed[\\s\\S]{0,80}/)?.[0] ?? null,
    recencyObservation: text.match(/GitHub portfolio recency[\\s\\S]{0,120}/)?.[0] ?? null,
    capabilityCount: document.querySelectorAll(".capability-item").length,
    provenanceCount: document.querySelectorAll(".provenance-item").length,
    forbiddenTermsPresent: /\\b(?:inactive|skill match|source coverage|moderate)\\b/i.test(text),
    methodDetailsCollapsed: details.some((item) => item.summary === "Method details" && !item.open),
    duplicateIds,
    unlabeled,
    saveButtonPresent: [...document.querySelectorAll("button")].some((button) => button.textContent === "Save report")
  };
})()`);

await evaluate(`(() => {
  const button = [...document.querySelectorAll("button")].find((item) => item.textContent === "Save report");
  if (!button) throw new Error("Save report button missing");
  button.click();
  return true;
})()`);
await waitFor(`document.querySelector("#results")?.innerText.includes("Saved report #")`);
const persistence = await evaluate(`({
  resultSaved: document.querySelector("#results").innerText.includes("Saved report #"),
  historyShowsV3: document.querySelector("#history-list").innerText.includes("v3")
})`);

await evaluate(`(async () => {
  const legacy = {
    schema_version:2, benchmark_version:"2", planner_version:"1", benchmark_identity:"AI Engineer",
    visibility_level:"Semi-Public", github_username:null,
    digital_identity_profile:{skills:["python"]}, benchmark_comparison:{matched_skills:["python"]},
    gap_analysis:{matched_skills:["python"], missing_required_skills:["machine learning"], missing_preferred_skills:[],
      skill_match_score:0.1, skill_match_label:"low", github_activity_score:null,
      github_activity_label:"insufficient evidence", profile_completeness_score:0.333,
      profile_completeness_label:"partial", memberships:{skill_match:{low:1}, github_activity:{}, source_coverage:{partial:1}},
      project_keyword_matches:[], relevant_certifications:[]},
    visibility_assessment:{selected_level:"Semi-Public", findings:[]}, recommendations:[],
    explanation_summary:{historical:true}, github_warning:null,
    source_statuses:{resume:{status:"not_supplied",reason:null}, github:{status:"not_supplied",reason:null}, linkedin:{status:"analysed",reason:null}},
    evidence:[], suggested_plan:{status:"no_actions_needed",steps:[],total_cost:0,objectives:[],unresolved_objectives:[],expanded_states:0,optimal:true,fallback_recommendations:[]},
    clarification_requests:[]
  };
  const response = await fetch("http://127.0.0.1:8000/api/reports", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(legacy)});
  if (!response.ok) throw new Error("Legacy fixture save failed: " + response.status);
  const refresh = [...document.querySelectorAll("button")].find((button) => button.textContent === "Refresh history");
  refresh.click();
  return true;
})()`);
await waitFor(`document.querySelector("#history-list")?.textContent.includes("historical heuristic")`);
await evaluate(`(() => {
  const item = [...document.querySelectorAll(".history-item")].find((node) => node.textContent.includes("historical heuristic"));
  const open = [...item.querySelectorAll("button")].find((button) => button.textContent.startsWith("Open #"));
  open.click();
  return true;
})()`);
await waitFor(`document.querySelector("#results")?.textContent.includes("Historical heuristic—not recalculated")`);
const legacy = await evaluate(`({
  markedHistorical: document.querySelector("#results").textContent.includes("Historical heuristic—not recalculated"),
  gradesCollapsed: [...document.querySelectorAll("#results details")].some((item) => item.querySelector("summary")?.textContent === "Show historical heuristic grades" && !item.open),
  rerunOptionPresent: [...document.querySelectorAll("#results button")].some((button) => button.textContent === "Run a new analysis")
})`);

await call("Emulation.setDeviceMetricsOverride", {width: 375, height: 812, deviceScaleFactor: 1, mobile: true});
await new Promise((resolve) => setTimeout(resolve, 250));
const narrow = await evaluate(`({
  viewport: [innerWidth, innerHeight],
  noHorizontalOverflow: document.documentElement.scrollWidth <= innerWidth,
  formVisible: Boolean(document.querySelector("#analyze-form")?.getBoundingClientRect().width),
  resultsVisible: Boolean(document.querySelector("#results")?.getBoundingClientRect().width)
})`);
const screenshot = await call("Page.captureScreenshot", {format: "png", captureBeyondViewport: false});

console.log(JSON.stringify({
  desktop,
  persistence,
  legacy,
  narrow,
  screenshotBytes: Math.floor((screenshot.data.length * 3) / 4),
  consoleErrors,
  networkFailures
}, null, 2));
socket.close();
