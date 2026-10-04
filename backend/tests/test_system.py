import copy
import itertools
import json
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config, database, main
from app.modules import extraction as ex, fuzzy_logic as fuzzy, planner
from app.schemas import AnalyzeResponse

FIXTURES = Path(__file__).parent / "fixtures"
PROFILES = json.loads((FIXTURES / "profiles.json").read_text())["profiles"]
BASELINE = json.loads((FIXTURES / "baseline.json").read_text())["cases"]


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    database.Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)
    def override():
        with session() as db:
            yield db
    main.app.dependency_overrides[database.get_db] = override
    # Deliberately avoid lifespan: it initializes the user's DB.
    with TestClient(main.app, raise_server_exceptions=True) as c:
        # lifespan is patched in another fixture below to prevent user DB writes.
        yield c
    main.app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture(autouse=True)
def no_user_db(monkeypatch):
    monkeypatch.setattr(database, "init_db", lambda: None)


@pytest.mark.parametrize("case", BASELINE, ids=lambda c: c["text"])
def test_extraction_regressions(case):
    assert ex._find_skills(case["text"]) == case["expected"]


def test_assertions_and_provenance():
    evidence = ex.extract_evidence("No experience with Python. I plan to learn Docker. Maybe SQL. Skills: Java", "resume")
    assert {(e["skill"], e["assertion"]) for e in evidence} == {
        ("python", "negated"), ("docker", "planned"), ("sql", "uncertain"), ("java", "claimed")}
    assert all(e["source"] == "resume" and e["excerpt"] and e["method"] for e in evidence)


def test_experience_sections_overlaps_dates():
    assert ex.experience_years("Education: Bachelor 2020-2024") is None
    text = "Experience\nEngineer 2020-2023\nDeveloper 2022-2024\nEducation\nDegree 2010-2015"
    assert ex.experience_years(text, date(2026, 1, 1)) == 4
    assert ex.experience_years("Experience\nEngineer 2024-present", date(2027, 1, 1)) == 3
    assert ex.experience_years("Experience\nEngineer 2030-2020") is None


@pytest.mark.parametrize("case", PROFILES, ids=lambda c:c["id"])
def test_profile_matrix(case):
    r = main.process(case["role"], case["visibility"], None, case["linkedin_text"], case["linkedin_visibility"], None)
    AnalyzeResponse.model_validate(r)
    assert r == main.process(case["role"], case["visibility"], None, case["linkedin_text"], case["linkedin_visibility"], None)
    assert r["digital_identity_profile"]["skills"] == case["expected_skills"]
    assert {k:v["status"] for k,v in r["source_statuses"].items()} == case["expected_source_statuses"]
    rules = {v["rule_id"] for v in r["recommendations"]}
    assert {"R1-evidence", "R4-project-evidence"} <= rules
    assert ("R10-privacy-contact" in rules) == ("R10-privacy-contact" in case["expected_rule_ids"])
    assert "R7-certifications" not in rules
    assert not set(case["forbidden_rule_ids"]) & rules
    assert r["assessment"]["github_portfolio_recency"]["availability"] == "not_assessed"
    assert r["digital_identity_profile"]["estimated_years_experience"] is None
    assert r["suggested_plan"]["optimal"]
    assert any(case["expected_sharing"] in s["title"] for s in r["suggested_plan"]["steps"] if s["id"].startswith(("project:", "portfolio:")))
    assert r["suggested_plan"]["unresolved_objectives"] == []


def test_visibility_does_not_change_skill_score():
    rs = [main.process("AI Engineer", v, None, "Skills: Python\nContact: synthetic@example.test", "public", None)
          for v in main.VISIBILITY_LEVELS]
    assert len({r["assessment"]["benchmark_evidence"]["score"] for r in rs}) == 1
    assert all(not r["digital_identity_profile"]["public_contact_info_detected"]
               for r in [main.process("AI Engineer", "Privacy Focused", None, "Skills: Python\nContact: synthetic@example.test", "private", None)])


def test_certification_relevance_and_project_keywords():
    r = main.process("Researcher", "Privacy Focused", None,
                     "Skills: research methodology\nProjects: research publication\nCertificate in unrelated cooking", "unverified", None)
    assert r["benchmark_comparison"]["project_keyword_matches"]
    assert "R7-certifications" not in {a["rule_id"] for a in r["recommendations"]}
    assert not any("GitHub counts" in c for c in r["clarification_requests"])


def test_fuzzy_boundaries():
    assert fuzzy._triangular(0, 0, 0, 1) == 1
    assert fuzzy._triangular(1, 0, 1, 1) == 1
    assert fuzzy.skill_match_degree({"x"}, {"x"}, set())[0] == 1
    assert fuzzy.skill_match_degree({"x"}, set(), {"x"})[0] == 1
    assert fuzzy.skill_match_degree(set(), set(), set()) == (1, "strong")
    for score in (0, .15, .2, .25, .4, .5, .6, .7, .85, 1):
        for kind in ("skill", "activity", "completeness"):
            m = fuzzy.memberships(score, kind)
            assert all(0 <= v <= 1 for v in m.values()) and max(m.values()) > 0
    assert fuzzy.memberships(None, "activity") == {}


def action(id, cost, goals, deps=(), vis=("Privacy Focused",)):
    return dict(id=id, title=id, cost=cost, objectives=list(goals), prerequisites=list(deps),
                roles=["AI Engineer"], visibilities=list(vis), explanation="Synthetic planning case")


def brute_cost(actions, goals):
    best = float("inf")
    for n in range(len(actions)+1):
        for sequence in itertools.permutations(actions, n):
            chosen, covered, cost = set(), set(), 0
            for a in sequence:
                if not set(a["prerequisites"]) <= chosen:
                    break
                chosen.add(a["id"]); covered.update(a["objectives"]); cost += a["cost"]
            else:
                if set(goals) <= covered:
                    best = min(best, cost)
    return best


def test_search_against_exhaustive_prerequisites_and_overlap():
    actions = [action("a", 2, ["x"]), action("b", 2, ["y"]),
               action("combined", 3, ["x", "y"]), action("dependent", 1, ["z"], ["combined"])]
    original = copy.deepcopy(actions)
    r = planner.search(actions, ["x", "y", "z"], "AI Engineer", "Privacy Focused")
    assert r["total_cost"] == brute_cost(actions, ["x", "y", "z"]) == 4
    assert [a["id"] for a in r["steps"]] == ["combined", "dependent"]
    assert actions == original
    assert r["total_cost"] < 2+2+3+1  # Independent action ranking does not optimise combinations.


def test_search_failures_and_privacy():
    a = [action("public", 1, ["x"], vis=["Fully Public"])]
    assert planner.search(a, ["x"], "AI Engineer", "Privacy Focused")["status"] == "unreachable"
    a = [action("a", 1, ["x"]), action("b", 1, ["y"])]
    for kwargs, status in [({"max_actions":1}, "candidate_limit"), ({"max_states":0}, "search_limit")]:
        r = planner.search(a, ["x"], "AI Engineer", "Privacy Focused", **kwargs)
        assert r["status"] == status and not r["optimal"] and r["unresolved_objectives"]
    assert planner.search(a, [], "AI Engineer", "Privacy Focused")["status"] == "no_actions_needed"
    with pytest.raises(ValueError):
        planner.search([action("bad", 0, ["x"])], ["x"], "AI Engineer", "Privacy Focused")


def response(body, code=200, links=None):
    return SimpleNamespace(status_code=code, json=lambda: body, links=links or {})


def mock_github(monkeypatch, responses):
    iterator = iter(responses)
    class Session:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, *args, **kwargs):
            value = next(iterator)
            if isinstance(value, Exception): raise value
            return value
    monkeypatch.setattr(ex.requests, "Session", Session)


def repo(name="r", fork=False):
    return {"name":name,"fork":fork,"language":"Python","description":"Skills: Python",
            "pushed_at":datetime.now(timezone.utc).isoformat()}


def test_github_pagination_forks_and_recency(monkeypatch):
    batch = [repo(str(i)) for i in range(100)]
    old = repo("old"); old["pushed_at"] = "2000-01-01T00:00:00Z"
    fork = repo("fork", True); fork["language"] = "Java"
    mock_github(monkeypatch, [response({"login":"synthetic"}),response(batch),response([old,fork])])
    r = ex.extract_from_github("synthetic")
    assert r["source_status"]["status"] == "analysed"
    assert r["repo_count"] == 101 and r["recently_active_repo_count"] == 100
    assert r["languages"] == ["python"]


@pytest.mark.parametrize("responses,expected", [
    ([response({},404)], "failed"),
    ([response({},429)], "failed"),
    ([response([])], "failed"),
    ([response({"login":"synthetic"}),response({},403)], "partial"),
    ([response({"login":"synthetic"}),response({"malformed":True})], "partial"),
    ([ex.requests.Timeout()], "failed"),
])
def test_github_failures(monkeypatch, responses, expected):
    mock_github(monkeypatch, responses)
    r = ex.extract_from_github("synthetic")
    assert r["source_status"]["status"] == expected
    assert r["repo_count"] is None and r["recently_active_repo_count"] is None


def test_github_cap(monkeypatch):
    monkeypatch.setattr(config, "MAX_REPOS", 1)
    mock_github(monkeypatch, [response({"login":"synthetic"}),response([repo(),repo("2")])])
    r = ex.extract_from_github("synthetic")
    assert r["source_status"]["status"] == "partial" and r["repo_count"] is None


def pdf(text=None, pages=1, password=None):
    with fitz.open() as d:
        for _ in range(pages):
            page = d.new_page()
            if text: page.insert_text((72,72), text)
        if password:
            return d.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw=password, user_pw=password)
        return d.tobytes()


def test_pdf_limits_and_errors(monkeypatch):
    assert "Python" in ex.extract_text_from_pdf(pdf("Skills: Python"))
    for data, msg in [(b"garbage", "PDF"), (pdf(), "No readable"), (pdf(password="test"), "Encrypted")]:
        with pytest.raises(ValueError, match=msg):
            ex.extract_text_from_pdf(data)
    monkeypatch.setattr(config, "MAX_PDF_PAGES", 1)
    with pytest.raises(ValueError, match="page limit"):
        ex.extract_text_from_pdf(pdf("text",2))


def fields():
    return {"benchmark_identity":"AI Engineer","visibility_level":"Privacy Focused","linkedin_text":"Skills: Python, SQL"}


def test_api_explicit_save_delete_and_legacy(client):
    assert client.get("/api/reports").json() == []
    r = client.post("/api/analyze", data=fields())
    assert r.status_code == 200
    report = r.json()
    assert "id" not in report and client.get("/api/reports").json() == []
    saved = client.post("/api/reports", json=report)
    assert saved.status_code == 201
    id = saved.json()["id"]
    assert client.get(f"/api/reports/{id}").json()["assessment"] == report["assessment"]
    assert len(client.get("/api/reports").json()) == 1
    assert client.delete(f"/api/reports/{id}").status_code == 204
    assert client.get(f"/api/reports/{id}").status_code == 404
    # Insert an old payload into the same isolated database.
    with next(main.app.dependency_overrides[database.get_db]()) as db:
        row = database.Report(benchmark_identity="AI Engineer",visibility_level="Semi-Public",report_json='{"gap_analysis":{"skill_match_score":0.5}}')
        db.add(row); db.commit(); legacy_id = row.id
    legacy = client.get(f"/api/reports/{legacy_id}").json()
    assert "evidence" not in legacy and "suggested_plan" not in legacy


def test_api_validation_partial_pdf_and_cors(client, monkeypatch):
    assert client.post("/api/analyze", data={"benchmark_identity":"AI Engineer","visibility_level":"Semi-Public"}).status_code == 400
    assert client.post("/api/analyze", data={**fields(),"github_username":"https://github.com/example"}).status_code == 400
    assert client.post("/api/analyze", data={**fields(),"linkedin_visibility":"invalid"}).status_code == 422
    r = client.post("/api/analyze", data=fields(), files={"resume":("bad.pdf",b"bad","application/pdf")})
    assert r.status_code == 200 and r.json()["source_statuses"]["resume"]["status"] == "failed"
    monkeypatch.setattr(config,"MAX_PDF_BYTES",3)
    assert client.post("/api/analyze", data=fields(), files={"resume":("big.pdf",b"1234")}).status_code == 413
    monkeypatch.setattr(config,"MAX_TEXT_CHARS",3)
    assert client.post("/api/analyze", data=fields()).status_code == 413
    assert client.get("/api/health",headers={"Origin":"https://untrusted.test"}).headers.get("access-control-allow-origin") is None
    assert client.get("/api/health",headers={"Origin":"http://127.0.0.1:5173"}).headers["access-control-allow-origin"] == "http://127.0.0.1:5173"

