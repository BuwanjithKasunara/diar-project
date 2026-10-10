import json
import os
import re
import logging
import time
from functools import partial
import anyio
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import database
from .modules import extraction, identity_construction, alignment_engine, recommendation_engine, explainable_ai, ml_classifier, privacy_assessment, privacy, repository_privacy

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
with open(os.path.join(DATA_DIR, "benchmarks.json")) as f:
    BENCHMARKS = json.load(f)

VISIBILITY_LEVELS = ["Fully Public", "Semi-Public", "Privacy Focused"]
MAX_RESUME_BYTES = 5 * 1024 * 1024
MAX_LINKEDIN_CHARACTERS = 100_000
ANALYSIS_TIMEOUT_SECONDS = 40
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI-Based Digital Identity Analysis and Recommendation System",
    description="Analyses a user's resume, GitHub, and LinkedIn data against a benchmark "
                "professional identity and generates explainable recommendations.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    database.init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/benchmarks")
def list_benchmarks():
    return [
        {
            "name": name,
            "description": data["description"],
            "required_skills": data["required_skills"],
            "preferred_skills": data["preferred_skills"],
        }
        for name, data in BENCHMARKS.items()
    ]


@app.get("/api/visibility-levels")
def list_visibility_levels():
    return VISIBILITY_LEVELS


def sanitize_profile_for_visibility(profile: dict, visibility_level: str) -> dict:
    """Enforces dynamic privacy redactions based on selected visibility consent tier."""
    import copy
    import re
    sanitized = copy.deepcopy(profile)
    email_re = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
    phone_re = re.compile(r"(\+?\d[\d\-\s]{8,}\d)")

    def mask_text(t: str) -> str:
        if not t:
            return ""
        t = email_re.sub("[REDACTED_EMAIL]", t)
        t = phone_re.sub("[REDACTED_PHONE]", t)
        return t

    if visibility_level in ("Privacy Focused", "Semi-Public"):
        if "resume" in sanitized:
            sanitized["resume"]["experience_snippet"] = mask_text(sanitized["resume"].get("experience_snippet", ""))
            sanitized["resume"]["projects_snippet"] = mask_text(sanitized["resume"].get("projects_snippet", ""))
        if "linkedin" in sanitized:
            sanitized["linkedin"]["headline"] = mask_text(sanitized["linkedin"].get("headline", ""))

    if visibility_level == "Privacy Focused":
        if sanitized.get("github", {}).get("username"):
            sanitized["github"]["username"] = "[ANONYMOUS_USER]"
            sanitized["github"]["bio"] = mask_text(sanitized["github"].get("bio", ""))

    return sanitized


@app.post("/api/analyze")
async def analyze(
    benchmark_identity: str = Form(...),
    visibility_level: str = Form(...),
    github_username: Optional[str] = Form(None),
    linkedin_text: Optional[str] = Form(""),
    resume_publicly_shared: bool = Form(False),
    report_redaction: str = Form("mask_contacts"),
    scan_repository_files: bool = Form(False),
    resume: Optional[UploadFile] = File(None),
    db: Session = Depends(database.get_db),
):
    if benchmark_identity not in BENCHMARKS:
        raise HTTPException(status_code=400, detail=f"Unknown benchmark identity '{benchmark_identity}'.")
    if visibility_level not in VISIBILITY_LEVELS:
        raise HTTPException(status_code=400, detail=f"Unknown visibility level '{visibility_level}'.")
    if report_redaction not in privacy.REPORT_POLICIES:
        raise HTTPException(status_code=400, detail="Unknown saved report protection policy.")
    github_username = (github_username or "").strip() or None
    linkedin_text = (linkedin_text or "").strip()
    if github_username and ("--" in github_username or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", github_username)):
        raise HTTPException(status_code=400, detail="Enter a GitHub username (up to 39 letters, digits or internal hyphens), not a profile URL.")
    if len(linkedin_text) > MAX_LINKEDIN_CHARACTERS:
        raise HTTPException(status_code=413, detail="LinkedIn text must contain at most 100,000 characters.")
    if resume is None and not github_username and not linkedin_text:
        raise HTTPException(status_code=400, detail="Supply a resume, GitHub username or LinkedIn text before running analysis.")

    file_bytes = None
    if resume is not None:
        try:
            file_bytes = await resume.read(MAX_RESUME_BYTES + 1)
        finally:
            await resume.close()
        if len(file_bytes) > MAX_RESUME_BYTES:
            raise HTTPException(status_code=413, detail="The resume PDF must be no larger than 5 MiB.")
    # Only immutable source values go to the worker; the DB session stays here.
    try:
        with anyio.fail_after(ANALYSIS_TIMEOUT_SECONDS):
            report_payload, stored_username = await anyio.to_thread.run_sync(
                partial(_build_report, file_bytes, github_username, linkedin_text,
                        benchmark_identity, visibility_level, resume_publicly_shared,
                        report_redaction, scan_repository_files), abandon_on_cancel=True,
            )
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Analysis took too long. No report was saved for this timed-out analysis. Try fewer sources or retry later.")

    # 7. Persist Digital Identity Report
    db_report = database.Report(
        benchmark_identity=benchmark_identity,
        visibility_level=visibility_level,
        github_username=stored_username,
        report_json=json.dumps(report_payload),
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)

    return {"id": db_report.id, "created_at": db_report.created_at.isoformat(), **report_payload}



def _build_report(file_bytes, github_username, linkedin_text, benchmark_identity,
                  visibility_level, resume_publicly_shared, report_redaction, scan_repository_files=False):
    """Build protected report data in a worker without accessing report storage."""
    file_scan_deadline = time.monotonic() + ANALYSIS_TIMEOUT_SECONDS - 3
    # 1. Information Extraction Module
    resume_text = ""
    if file_bytes is not None:
        try:
            resume_text = extraction.extract_text_from_pdf(file_bytes)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except Exception:
            raise HTTPException(status_code=400, detail="Could not read the uploaded resume as a PDF.")
    resume_data = extraction.extract_from_resume_text(resume_text)

    github_data = {"skills": [], "languages": [], "repo_count": 0, "profile_complete": False}
    if github_username:
        github_data = extraction.extract_from_github(github_username.strip(), scan_repository_files=True, file_scan_deadline=file_scan_deadline) if scan_repository_files else extraction.extract_from_github(github_username.strip())

    linkedin_data = extraction.extract_from_linkedin_text(linkedin_text or "")

    # 2. Identity Construction Module
    profile = identity_construction.build_digital_identity_profile(resume_data, github_data, linkedin_data)
    if not resume_text and not linkedin_text and github_data.get("source_state") == "failed":
        raise HTTPException(status_code=422, detail="GitHub could not be retrieved and no other source was supplied. Check the username, retry later or supply another source.")
    privacy_evidence = privacy_assessment.collect_privacy_evidence(
        resume_text, linkedin_text or "", github_data.get("privacy_data"),
        resume_publicly_shared=resume_publicly_shared,
        repository_file_data=github_data.get("repository_file_privacy") or repository_privacy.empty_result(scan_repository_files, "unavailable" if scan_repository_files else "disabled"),
    )
    profile["public_contact_info_detected"] = any(
        item.get("kind") in ("email", "phone")
        and item.get("recommendation_eligible")
        and item.get("exposure_status") in ("observed_public", "user_declared_public")
        for item in privacy_evidence["evidence"]
    )

    # 3. Machine Learning Role Classification
    combined_ml_text = "\n".join(filter(None, [
        resume_text,
        linkedin_text,
        f"Skills: {', '.join(profile.get('skills', []))}" if profile.get('skills') else "",
        f"Projects: {', '.join(profile.get('projects', []))}" if profile.get('projects') else "",
    ]))
    try:
        ml_prediction = ml_classifier.predict_role(combined_ml_text, target_benchmark=benchmark_identity)
    except Exception as error:
        logger.warning("ML prediction unavailable (%s)", type(error).__name__)
        ml_prediction = {
            "model_available": False, "predicted_role": "Unavailable",
            "confidence": 0.0, "probabilities": {}, "matches_target": False,
            "top_features": [], "note": "Role prediction is temporarily unavailable. Rule-based analysis is still included.",
        }

    # 4. Identity Benchmark Module (lookup) + Digital Identity Alignment Engine
    benchmark = BENCHMARKS[benchmark_identity]
    alignment_result = alignment_engine.run_alignment(
        profile, benchmark, benchmark_identity, visibility_level, privacy_evidence=privacy_evidence,
    )

    # 5. Recommendation Engine
    recommendations = recommendation_engine.generate_recommendations(alignment_result["fired_rules"])

    # 6. Explainable AI Module
    explanation_summary = explainable_ai.build_explanation_summary(
        profile, benchmark_identity, alignment_result["gap_analysis"],
        alignment_result["visibility_assessment"], recommendations,
        ml_prediction=ml_prediction,
    )

    benchmark_comparison = {
        "benchmark_identity": benchmark_identity,
        "benchmark_description": benchmark["description"],
        "matched_skills": alignment_result["gap_analysis"]["matched_skills"],
        "missing_required_skills": alignment_result["gap_analysis"]["missing_required_skills"],
        "missing_preferred_skills": alignment_result["gap_analysis"]["missing_preferred_skills"],
    }

    report_payload = {
        "digital_identity_profile": profile,
        "benchmark_comparison": benchmark_comparison,
        "ml_prediction": ml_prediction,
        "gap_analysis": alignment_result["gap_analysis"],
        "visibility_assessment": alignment_result["visibility_assessment"],
        "recommendations": recommendations,
        "explanation_summary": explanation_summary,
        "github_warning": github_data.get("error"),
        "report_metadata": {"version": 1, "report_redaction": report_redaction},
    }
    report_payload = privacy.sanitize_report(report_payload, report_redaction, github_username)
    stored_username = privacy.sanitize_report({"github_username": github_username}, report_redaction, github_username)["github_username"]

    return report_payload, stored_username


@app.get("/api/reports")
def list_reports(db: Session = Depends(database.get_db)):
    reports = db.query(database.Report).order_by(database.Report.id.desc()).limit(50).all()
    history = []
    for r in reports:
        policy = privacy.effective_report_policy(json.loads(r.report_json), r.visibility_level)
        item = privacy.sanitize_report({
            "id": r.id,
            "benchmark_identity": r.benchmark_identity,
            "visibility_level": r.visibility_level,
            "github_username": r.github_username,
            "created_at": r.created_at.isoformat(),
            "report_metadata": {"report_redaction": policy},
        }, policy, r.github_username)
        # This is a server-generated timestamp, not profile contact evidence.
        item["created_at"] = r.created_at.isoformat()
        history.append(item)
    return history


@app.get("/api/reports/{report_id}")
def get_report(report_id: int, db: Session = Depends(database.get_db)):
    r = db.query(database.Report).filter(database.Report.id == report_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found.")
    payload = json.loads(r.report_json)
    policy = privacy.effective_report_policy(payload, r.visibility_level)
    payload = privacy.sanitize_report(payload, policy, r.github_username)
    payload.setdefault("report_metadata", {"version": 0, "report_redaction": policy, "legacy_policy": True})
    return {"id": r.id, "created_at": r.created_at.isoformat(), **payload}


@app.delete("/api/reports/{report_id}", status_code=204)
def delete_report(report_id: int, db: Session = Depends(database.get_db)):
    report = db.query(database.Report).filter(database.Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    db.delete(report)
    db.commit()
    return Response(status_code=204)
