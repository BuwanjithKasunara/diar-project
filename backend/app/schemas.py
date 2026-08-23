from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class BenchmarkSummary(BaseModel):
    name: str
    description: str
    required_skills: List[str]
    preferred_skills: List[str]


class ReportHistoryItem(BaseModel):
    id: int
    benchmark_identity: str
    visibility_level: str
    github_username: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class AnalyzeResponse(BaseModel):
    id: int
    digital_identity_profile: Dict[str, Any]
    benchmark_comparison: Dict[str, Any]
    gap_analysis: Dict[str, Any]
    visibility_assessment: Dict[str, Any]
    recommendations: List[Dict[str, Any]]
    explanation_summary: Dict[str, Any]
