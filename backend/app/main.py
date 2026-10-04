"""Local single-user API. Analysis is transient; only explicit saving persists data."""
import json
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, Literal
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from . import database, config
from .schemas import AnalyzeResponseV3, AnalyzeRequest, SavedReport, ReportHistoryItem
from .modules import extraction, identity_construction, alignment_engine, recommendation_engine, explainable_ai, planner

BENCHMARKS = json.loads((Path(__file__).parent / "data/benchmarks.json").read_text())
known_skills = {skill for category in extraction.SKILLS_DICT.values() for skill in category}
for name, benchmark in BENCHMARKS.items():
    capability_skills = {skill for c in benchmark.get("capabilities", [])
                         for skill in [*c.get("skills", []), *c.get("related_skills", [])]}
    unknown = (set(benchmark["required_skills"]) | set(benchmark["preferred_skills"]) |
               capability_skills) - known_skills
    if unknown:
        raise ValueError(f"Unknown benchmark skills in {name}: {unknown}")
VISIBILITY_LEVELS = alignment_engine.VISIBILITY_LEVELS


@asynccontextmanager
async def lifespan(app):
    database.init_db()
    yield


app = FastAPI(title="DIAR", version="0.3.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.LOCAL_ORIGINS,
                   allow_credentials=False, allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type"])


def fail(code, message, status=400):
    raise HTTPException(status_code=status, detail={"code": code, "message": message})


@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    return JSONResponse(status_code=422, content={"detail": {"code": "invalid_request", "message": "Invalid fields or report format."}})


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/benchmarks")
def list_benchmarks():
    return [{"name": name, **{k: b[k] for k in ("description", "required_skills", "preferred_skills")}} for name, b in BENCHMARKS.items()]


@app.get("/api/visibility-levels")
def visibility_levels():
    return VISIBILITY_LEVELS


@app.get("/api/config")
def public_config():
    return {"max_pdf_bytes": config.MAX_PDF_BYTES, "max_pdf_pages": config.MAX_PDF_PAGES,
            "max_text_chars": config.MAX_TEXT_CHARS, "activity_days": config.ACTIVITY_DAYS,
            "max_github_readmes": config.MAX_GITHUB_READMES,
            "max_github_readme_chars": config.MAX_GITHUB_README_CHARS}


def process(benchmark_identity, visibility_level, github_username, linkedin_text, linkedin_visibility, file_bytes,
            as_of=None):
    benchmark = BENCHMARKS[benchmark_identity]
    resume = extraction.extract_from_resume_text("")
    if file_bytes is not None:
        try:
            resume = extraction.extract_from_resume_text(extraction.extract_text_from_pdf(file_bytes))
        except ValueError as exc:
            resume["source_status"] = extraction.status("failed", str(exc))
    github = extraction.extract_from_github(github_username, benchmark=benchmark, as_of=as_of) if github_username else {
        "source_status": extraction.status("not_supplied")}
    linkedin = extraction.extract_from_linkedin_text(linkedin_text, linkedin_visibility)
    profile = identity_construction.build_digital_identity_profile(resume, github, linkedin)
    if not profile["sources_provided_count"]:
        reasons = [s["reason"] for s in profile["source_statuses"].values() if s["reason"]]
        fail("no_usable_source", "No usable source. " + (" ".join(reasons) or "Supply PDF text, GitHub, or LinkedIn text."))
    aligned = alignment_engine.run_alignment(profile, benchmark, benchmark_identity, visibility_level)
    recommendations = recommendation_engine.generate_recommendations(aligned["fired_rules"])
    explanation = explainable_ai.build_explanation_summary(profile, benchmark_identity, aligned["assessment"],
                                                          aligned["visibility_assessment"], recommendations)
    explanation["rules_fired_count"] = len(aligned["fired_rules"])
    return {
        "schema_version": 3, "benchmark_version": config.BENCHMARK_VERSION, "planner_version": config.PLANNER_VERSION,
        "benchmark_identity": benchmark_identity, "visibility_level": visibility_level, "github_username": github_username,
        "digital_identity_profile": profile, "source_statuses": profile["source_statuses"], "evidence": profile["evidence"],
        "benchmark_comparison": aligned["benchmark_comparison"],
        "assessment": aligned["assessment"], "visibility_assessment": aligned["visibility_assessment"],
        "recommendations": recommendations, "explanation_summary": explanation,
        "github_warning": github.get("error"),
        "suggested_plan": planner.generate_plan(aligned["objectives"], benchmark_identity, visibility_level, profile["skills"], recommendations),
        "clarification_requests": aligned["clarification_requests"],
    }


@app.post("/api/analyze", response_model=AnalyzeResponseV3)
async def analyze(benchmark_identity: str = Form(...), visibility_level: str = Form(...),
                  github_username: Optional[str] = Form(None), linkedin_text: str = Form(""),
                  linkedin_visibility: Literal["unverified", "public", "private"] = Form("unverified"),
                  resume: Optional[UploadFile] = File(None)):
    if benchmark_identity not in BENCHMARKS:
        fail("unknown_benchmark", "Select a supported benchmark.")
    if visibility_level not in VISIBILITY_LEVELS:
        fail("unknown_visibility", "Select a supported visibility level.")
    username = github_username.strip() if github_username else None
    if username and not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", username):
        fail("invalid_username", "Use a GitHub username, not a URL.")
    if len(linkedin_text) > config.MAX_TEXT_CHARS:
        fail("text_too_large", "Pasted text exceeds the configured character limit.", 413)
    if not username and not linkedin_text.strip() and resume is None:
        fail("no_input", "Supply at least one source.")
    file_bytes = None
    if resume is not None:
        try:
            file_bytes = await resume.read(config.MAX_PDF_BYTES + 1)
        finally:
            await resume.close()
        if len(file_bytes) > config.MAX_PDF_BYTES:
            fail("pdf_too_large", "PDF exceeds the configured byte limit.", 413)
    return await run_in_threadpool(process, benchmark_identity, visibility_level, username or None,
                                   linkedin_text, linkedin_visibility, file_bytes)


@app.post("/api/reports", response_model=SavedReport, status_code=201)
def save_report(report: AnalyzeRequest, db: Session = Depends(database.get_db)):
    if report.benchmark_identity not in BENCHMARKS:
        fail("unknown_benchmark", "Unknown report benchmark.")
    row = database.Report(benchmark_identity=report.benchmark_identity, visibility_level=report.visibility_level,
                          github_username=report.github_username, report_json=report.model_dump_json())
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        fail("storage_error", "Report could not be saved.", 503)
    return {**report.model_dump(), "id": row.id, "created_at": row.created_at.isoformat()}


@app.get("/api/reports", response_model=list[ReportHistoryItem])
def list_reports(db: Session = Depends(database.get_db)):
    rows = db.query(database.Report).order_by(database.Report.id.desc()).limit(50).all()
    items = []
    for row in rows:
        try:
            version = json.loads(row.report_json).get("schema_version")
        except (json.JSONDecodeError, AttributeError):
            version = None
        items.append({"id": row.id, "benchmark_identity": row.benchmark_identity,
                      "visibility_level": row.visibility_level, "github_username": row.github_username,
                      "created_at": row.created_at.isoformat(), "schema_version": version})
    return items


@app.get("/api/reports/{report_id}")
def get_report(report_id: int, db: Session = Depends(database.get_db)):
    row = db.get(database.Report, report_id)
    if row is None:
        fail("not_found", "Report not found.", 404)
    # Do not reinterpret legacy reports with new scores or invented evidence.
    return {**json.loads(row.report_json), "id": row.id, "created_at": row.created_at.isoformat()}


@app.delete("/api/reports/{report_id}", status_code=204)
def delete_report(report_id: int, db: Session = Depends(database.get_db)):
    row = db.get(database.Report, report_id)
    if row is None:
        fail("not_found", "Report not found.", 404)
    db.delete(row)
    db.commit()
    return Response(status_code=204)
