import json
import os
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import database
from .modules import extraction, identity_construction, alignment_engine, recommendation_engine, explainable_ai

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
with open(os.path.join(DATA_DIR, "benchmarks.json")) as f:
    BENCHMARKS = json.load(f)

VISIBILITY_LEVELS = ["Fully Public", "Semi-Public", "Privacy Focused"]

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


@app.post("/api/analyze")
async def analyze(
    benchmark_identity: str = Form(...),
    visibility_level: str = Form(...),
    github_username: Optional[str] = Form(None),
    linkedin_text: Optional[str] = Form(""),
    resume: Optional[UploadFile] = File(None),
    db: Session = Depends(database.get_db),
):
    if benchmark_identity not in BENCHMARKS:
        raise HTTPException(status_code=400, detail=f"Unknown benchmark identity '{benchmark_identity}'.")
    if visibility_level not in VISIBILITY_LEVELS:
        raise HTTPException(status_code=400, detail=f"Unknown visibility level '{visibility_level}'.")

    # 1. Information Extraction Module
    resume_text = ""
    if resume is not None:
        file_bytes = await resume.read()
        try:
            resume_text = extraction.extract_text_from_pdf(file_bytes)
        except Exception:
            raise HTTPException(status_code=400, detail="Could not read the uploaded resume as a PDF.")
    resume_data = extraction.extract_from_resume_text(resume_text)

    github_data = {"skills": [], "languages": [], "repo_count": 0, "profile_complete": False}
    if github_username:
        github_data = extraction.extract_from_github(github_username.strip())

    linkedin_data = extraction.extract_from_linkedin_text(linkedin_text or "")

    # 2. Identity Construction Module
    profile = identity_construction.build_digital_identity_profile(resume_data, github_data, linkedin_data)

    # 3. Identity Benchmark Module (lookup) + 4. Digital Identity Alignment Engine
    benchmark = BENCHMARKS[benchmark_identity]
    alignment_result = alignment_engine.run_alignment(profile, benchmark, benchmark_identity, visibility_level)

    # 5. Recommendation Engine
    recommendations = recommendation_engine.generate_recommendations(alignment_result["fired_rules"])

    # 6. Explainable AI Module
    explanation_summary = explainable_ai.build_explanation_summary(
        profile, benchmark_identity, alignment_result["gap_analysis"],
        alignment_result["visibility_assessment"], recommendations,
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
        "gap_analysis": alignment_result["gap_analysis"],
        "visibility_assessment": alignment_result["visibility_assessment"],
        "recommendations": recommendations,
        "explanation_summary": explanation_summary,
        "github_warning": github_data.get("error"),
    }

    # 7. Persist Digital Identity Report
    db_report = database.Report(
        benchmark_identity=benchmark_identity,
        visibility_level=visibility_level,
        github_username=github_username,
        report_json=json.dumps(report_payload),
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)

    return {"id": db_report.id, **report_payload}


@app.get("/api/reports")
def list_reports(db: Session = Depends(database.get_db)):
    reports = db.query(database.Report).order_by(database.Report.id.desc()).limit(50).all()
    return [
        {
            "id": r.id,
            "benchmark_identity": r.benchmark_identity,
            "visibility_level": r.visibility_level,
            "github_username": r.github_username,
            "created_at": r.created_at.isoformat(),
        }
        for r in reports
    ]


@app.get("/api/reports/{report_id}")
def get_report(report_id: int, db: Session = Depends(database.get_db)):
    r = db.query(database.Report).filter(database.Report.id == report_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found.")
    payload = json.loads(r.report_json)
    return {"id": r.id, "created_at": r.created_at.isoformat(), **payload}
