"""Versioned report contracts; legacy rows bypass new validation on retrieval."""
from typing import Literal, Any
from pydantic import BaseModel, Field, ConfigDict

Visibility = Literal["Fully Public", "Semi-Public", "Privacy Focused"]


class SourceStatus(BaseModel):
    status: Literal["not_supplied", "analysed", "partial", "failed"]
    reason: str | None = None


class Evidence(BaseModel):
    skill: str
    source: Literal["resume", "github", "linkedin"]
    excerpt: str
    method: Literal["exact", "alias", "typo", "metadata"]
    assertion: Literal["claimed", "planned", "negated", "uncertain"]


class Recommendation(BaseModel):
    rank: int
    priority: Literal["high", "medium", "low"]
    recommendation: str
    rule_id: str
    explanation: str


class PlanStep(BaseModel):
    id: str
    title: str
    cost: int = Field(gt=0)
    objectives: list[str]
    explanation: str
    prerequisites: list[str] = []
    roles: list[str] = []
    visibilities: list[str] = []


class Plan(BaseModel):
    status: Literal["optimal", "no_actions_needed", "candidate_limit", "search_limit", "unreachable"]
    steps: list[PlanStep]
    total_cost: int
    objectives: list[str]
    unresolved_objectives: list[str]
    expanded_states: int
    optimal: bool
    fallback_recommendations: list[Recommendation]


class GapAnalysis(BaseModel):
    matched_skills: list[str]
    missing_required_skills: list[str]
    missing_preferred_skills: list[str]
    skill_match_score: float | None = Field(ge=0, le=1)
    skill_match_label: str
    github_activity_score: float | None = Field(ge=0, le=1)
    github_activity_label: str
    profile_completeness_score: float = Field(ge=0, le=1)
    profile_completeness_label: str
    memberships: dict[str, dict[str, float]]
    project_keyword_matches: list[str]
    relevant_certifications: list[str]


class AnalyzeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[2] = 2
    benchmark_version: str
    planner_version: str
    benchmark_identity: str
    visibility_level: Visibility
    github_username: str | None = None
    digital_identity_profile: dict[str, Any]
    benchmark_comparison: dict[str, Any]
    gap_analysis: GapAnalysis
    visibility_assessment: dict[str, Any]
    recommendations: list[Recommendation]
    explanation_summary: dict[str, Any]
    github_warning: str | None = None
    source_statuses: dict[str, SourceStatus]
    evidence: list[Evidence]
    suggested_plan: Plan
    clarification_requests: list[str]


class SavedReport(AnalyzeResponse):
    id: int
    created_at: str


class ReportHistoryItem(BaseModel):
    id: int
    benchmark_identity: str
    visibility_level: str
    github_username: str | None = None
    created_at: str
