"""Versioned report contracts; stored legacy JSON is never recalculated on retrieval."""
from typing import Annotated, Any, Literal, Union
from pydantic import BaseModel, Field, ConfigDict

Visibility = Literal["Fully Public", "Semi-Public", "Privacy Focused"]


class SourceStatus(BaseModel):
    status: Literal["not_supplied", "analysed", "partial", "failed"]
    reason: str | None = None


class EvidenceV2(BaseModel):
    skill: str
    source: Literal["resume", "github", "linkedin"]
    excerpt: str
    method: Literal["exact", "alias", "typo", "metadata"]
    assertion: Literal["claimed", "planned", "negated", "uncertain"]


class EvidenceV3(EvidenceV2):
    id: str
    origin: str
    artifact_type: Literal["resume", "linkedin", "bio", "description", "topic", "readme", "language", "name", "text"]
    repository: str | None = None
    repository_locator: str | None = None
    extraction_method: Literal["exact", "alias", "typo", "metadata"]
    strength: float = Field(ge=0, le=1)


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


class GapAnalysisV2(BaseModel):
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


class CapabilityResult(BaseModel):
    id: str
    label: str
    importance: Literal["required", "preferred"]
    weight: float = Field(gt=0, le=1)
    accepted_skills: list[str]
    matched_skills: list[str]
    evidence_ids: list[str]
    strength: float = Field(ge=0, le=1)
    state: Literal["evidenced", "weakly_evidenced", "not_observed", "not_assessed", "explicit_gap"]


class BenchmarkEvidence(BaseModel):
    score: float | None = Field(ge=0, le=1)
    evidenced_count: int = Field(ge=0)
    weakly_evidenced_count: int = Field(ge=0)
    total_count: int = Field(ge=0)
    capability_results: list[CapabilityResult]
    memberships: dict[str, float]
    method: str
    limitation: str


class SourceScope(BaseModel):
    supported_total: int = Field(ge=1)
    usable_count: int = Field(ge=0)
    usable: list[str]
    partial: list[str]
    failed: list[str]
    not_supplied: list[str]


class GitHubPortfolioRecency(BaseModel):
    availability: Literal["available", "not_assessed"]
    window_days: int = Field(gt=0)
    owned_public_non_fork_repository_count: int | None = Field(default=None, ge=0)
    recently_pushed_owned_repository_count: int | None = Field(default=None, ge=0)
    last_owned_repository_push_at: str | None = None
    limitation: str


class Assessment(BaseModel):
    benchmark_evidence: BenchmarkEvidence
    source_scope: SourceScope
    github_portfolio_recency: GitHubPortfolioRecency


class AnalyzeResponseV2(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[2] = 2
    benchmark_version: str
    planner_version: str
    benchmark_identity: str
    visibility_level: Visibility
    github_username: str | None = None
    digital_identity_profile: dict[str, Any]
    benchmark_comparison: dict[str, Any]
    gap_analysis: GapAnalysisV2
    visibility_assessment: dict[str, Any]
    recommendations: list[Recommendation]
    explanation_summary: dict[str, Any]
    github_warning: str | None = None
    source_statuses: dict[str, SourceStatus]
    evidence: list[EvidenceV2]
    suggested_plan: Plan
    clarification_requests: list[str]


class AnalyzeResponseV3(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[3] = 3
    benchmark_version: str
    planner_version: str
    benchmark_identity: str
    visibility_level: Visibility
    github_username: str | None = None
    digital_identity_profile: dict[str, Any]
    benchmark_comparison: dict[str, Any]
    assessment: Assessment
    visibility_assessment: dict[str, Any]
    recommendations: list[Recommendation]
    explanation_summary: dict[str, Any]
    github_warning: str | None = None
    source_statuses: dict[str, SourceStatus]
    evidence: list[EvidenceV3]
    suggested_plan: Plan
    clarification_requests: list[str]


AnalyzeRequest = Annotated[Union[AnalyzeResponseV2, AnalyzeResponseV3], Field(discriminator="schema_version")]


class SavedReportV2(AnalyzeResponseV2):
    id: int
    created_at: str


class SavedReportV3(AnalyzeResponseV3):
    id: int
    created_at: str


SavedReport = Annotated[Union[SavedReportV2, SavedReportV3], Field(discriminator="schema_version")]


class ReportHistoryItem(BaseModel):
    id: int
    benchmark_identity: str
    visibility_level: str
    github_username: str | None = None
    created_at: str
    schema_version: int | None = None


# Current-response aliases used by internal callers and tests.
AnalyzeResponse = AnalyzeResponseV3
Evidence = EvidenceV3
