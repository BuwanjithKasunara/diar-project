var review = {history: [], historyLoading: false, historyError: '', opening: false,
  openRequest: 0, historyRequest: 0, category: 'all', priority: 'all'};

function reportBusy() { return state.loading || state.deletingReport || review.opening; }

async function reviewFetch(path) {
  var controller = new AbortController();
  var timer = setTimeout(function () { controller.abort(); }, 15000);
  try {
    var response = await fetch(API_BASE + path, {signal: controller.signal});
    if (!response.ok) throw new Error(response.status === 404 ? 'Saved report no longer exists. Refresh history.' : 'Could not load saved reports. Try again.');
    return await response.json();
  } finally { clearTimeout(timer); }
}

async function loadReportHistory() {
  var request = ++review.historyRequest;
  review.historyLoading = true; review.historyError = ''; renderReportHistory();
  try {
    var rows = await reviewFetch('/api/reports');
    if (request === review.historyRequest) review.history = rows;
  } catch (error) {
    if (request === review.historyRequest) review.historyError = error.name === 'AbortError' ? 'History request timed out. Try again.' : error.message;
  } finally {
    if (request === review.historyRequest) { review.historyLoading = false; renderReportHistory(); }
  }
}

async function openSavedReport(id) {
  if (reportBusy()) return;
  var request = ++review.openRequest;
  review.opening = true; review.historyError = ''; state.confirmingDelete = false;
  renderReportHistory(); renderResultsPanel(); renderRunButton();
  try {
    var report = await reviewFetch('/api/reports/' + encodeURIComponent(id));
    if (request !== review.openRequest) return;
    state.report = report; state.deleteError = null; state.reportNotice = null; state.error = null; renderError();
    review.category = review.priority = 'all';
  } catch (error) { review.historyError = error.name === 'AbortError' ? 'Opening report timed out; the previous report is still available.' : error.message; }
  finally { review.opening = false; renderReportHistory(); renderResultsPanel(); renderRunButton(); }
}

function renderReportHistory() {
  var host = document.getElementById('report-history');
  if (!host) return;
  var refresh = el('button', {type:'button', onClick:loadReportHistory}, ['Refresh history']);
  refresh.disabled = review.historyLoading;
  host.replaceChildren(h2('', 'Saved reports'), el('p', {class:'hint'}, ['Latest 50 reports on this local prototype. Reopening does not reanalyse or change your input form.']), refresh);
  if (review.historyLoading) host.appendChild(el('p', {role:'status'}, ['Loading history…']));
  if (review.opening) host.appendChild(el('p', {role:'status'}, ['Opening saved report…']));
  if (review.historyError) host.appendChild(el('p', {role:'alert'}, [review.historyError]));
  if (!review.historyLoading && !review.history.length && !review.historyError) host.appendChild(el('p', {class:'hint'}, ['No saved reports yet.']));
  review.history.forEach(function (row) {
    var button = el('button', {type:'button', onClick:function () { openSavedReport(row.id); }}, ['Open report #' + row.id]);
    button.disabled = reportBusy();
    host.appendChild(el('div', {class:'history-entry'}, [button,
      el('div', {class:'hint'}, [row.benchmark_identity + ' · ' + (row.created_at || 'Time unavailable')]),
      el('div', {class:'hint'}, [(row.report_metadata || {}).report_redaction || 'Legacy protection policy'])]));
  });
}

function exportDisplayedReport() {
  if (!state.report || reportBusy()) return;
  var blob = new Blob([JSON.stringify(state.report, null, 2)], {type:'application/json'});
  var url = URL.createObjectURL(blob);
  var link = document.createElement('a'); link.href = url;
  link.download = 'diar-report-' + (/^\d+$/.test(String(state.report.id)) ? state.report.id : 'saved') + '.json';
  link.click(); setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
}

function recommendationCategory(rec) {
  if (rec.category === 'visibility' || rec.category === 'privacy') return 'privacy';
  return rec.category === 'career' ? 'career' : 'legacy';
}

function revealRecommendation(ruleId) {
  review.category = review.priority = 'all'; renderResultsPanel();
  var target = document.getElementById('recommendation-' + ruleId);
  if (target) { target.scrollIntoView({block:'center'}); target.focus(); }
}

function recommendationLink(rec, text) {
  return el('a', {href:'#recommendation-' + rec.rule_id, onClick:function (event) { event.preventDefault(); revealRecommendation(rec.rule_id); }}, [text]);
}

function renderRecommendationNavigation(recs) {
  recs = recs || [];
  var wrap = el('div', {id:'recommendation-navigation'}, []);
  wrap.appendChild(subhead('Suggested first steps'));
  var first = el('div', {}, []);
  recs.slice(0, 3).forEach(function (rec) { first.appendChild(el('p', {}, [recommendationLink(rec, rec.recommendation)])); });
  if (!recs.length) first.appendChild(el('p', {class:'hint'}, ['No recommended actions recorded.']));
  wrap.appendChild(first);
  var privacy = recs.filter(function (rec) { return rec.source === 'github_repository_file'; });
  if (privacy.length) {
    wrap.appendChild(subhead('Public repository file actions'));
    privacy.forEach(function (rec) { wrap.appendChild(el('p', {}, [recommendationLink(rec, rec.recommendation)])); });
  }
  [['category', 'Recommendation category', ['all','career','privacy','legacy']], ['priority', 'Recommendation priority', ['all','high','medium','low']]].forEach(function (spec) {
    var select = el('select', {id:'filter-' + spec[0], onChange:function (event) {
      review[spec[0]] = event.target.value; renderResultsPanel();
      document.getElementById('filter-' + spec[0]).focus();
    }}, spec[2].map(function (value) { return el('option', {value:value}, [value === 'legacy' ? 'Legacy / uncategorized' : value]); }));
    select.value = review[spec[0]];
    wrap.appendChild(el('label', {for:'filter-' + spec[0]}, [spec[1]])); wrap.appendChild(select);
  });
  var visible = recs.filter(function (rec) { return (review.category === 'all' || recommendationCategory(rec) === review.category) && (review.priority === 'all' || rec.priority === review.priority); });
  wrap.appendChild(el('p', {role:'status', class:'hint'}, ['Showing ' + visible.length + ' of ' + recs.length + ' actions. Original ranking preserved.']));
  wrap.appendChild(visible.length ? renderRecommendations(visible) : el('p', {class:'hint'}, ['No actions match these filters.']));
  return wrap;
}

var printFilters = null;
window.addEventListener('beforeprint', function () {
  printFilters = [review.category, review.priority];
  review.category = review.priority = 'all'; renderResultsPanel();
});
window.addEventListener('afterprint', function () {
  if (printFilters) { review.category = printFilters[0]; review.priority = printFilters[1]; printFilters = null; renderResultsPanel(); }
});
