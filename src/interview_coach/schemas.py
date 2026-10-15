from operator import mul
from typing import Literal

from pydantic import BaseModel, Field

QuestionType = Literal["behavioral", "technical", "situational"]
Level = Literal["junior", "mid", "senior"]

DISCLAIMER = "Practice coaching estimate. Not a hiring decision."


class JobProfile(BaseModel):
    title: str
    seniority: Level
    required_skills: list[str]
    preferred_skills: list[str] = Field(default_factory=list)
    responsibilities: list[str]
    interview_themes: list[str]


class Experience(BaseModel):
    role: str
    company: str
    highlights: list[str]


class ResumeProfile(BaseModel):
    summary: str
    skills: list[str]
    experiences: list[Experience]
    projects: list[str] = Field(default_factory=list)
    evidence_points: list[str]


class PlannedQuestion(BaseModel):
    id: str
    category: QuestionType
    question: str
    target_skill: str
    rationale: str
    source_question_id: str


class InterviewPlan(BaseModel):
    role: str
    level: Level
    questions: list[PlannedQuestion] = Field(min_length=3, max_length=5)


class FollowUp(BaseModel):
    needed: bool
    text: str


class DimensionScore(BaseModel):
    name: str
    score: int = Field(ge=1, le=5)
    evidence: str
    suggestion: str


class AnswerEvaluation(BaseModel):
    question_id: str
    question_type: QuestionType
    dimension_scores: list[DimensionScore] = Field(min_length=1)
    overall_score: float = Field(ge=1, le=5)
    strengths: list[str]
    gaps: list[str]
    improvements: list[str]
    filler_word_count: int = Field(default=0, ge=0)
    disclaimer: str = DISCLAIMER


class FinalReport(BaseModel):
    overall_score: float = Field(ge=1, le=5)
    summary: str
    per_question: list[AnswerEvaluation]
    top_strengths: list[str]
    top_gaps: list[str]
    action_plan: list[str]
    approved: bool = False
    disclaimer: str = DISCLAIMER


def weighted_overall(scores: list[DimensionScore], weights: dict[str, float]) -> float:
    """Deterministic overall score from rubric weights, normalized to matched dimensions."""
    total_weight = sum(weights.get(s.name, 0.0) for s in scores)
    if total_weight == 0:
        raise ValueError("No scores match rubric dimensions")
    weighted = sum(mul(s.score, weights.get(s.name, 0.0)) for s in scores)
    return round(weighted / total_weight, 2)