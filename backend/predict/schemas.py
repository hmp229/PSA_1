"""Pydantic schemas with strict validation."""
from typing import Optional, List, Dict
from datetime import date, datetime, timedelta
from pydantic import BaseModel, Field, conint, field_validator


class RankingSnapshot(BaseModel):
    """Player ranking snapshot with validation."""
    rank: conint(ge=1, le=500) = Field(..., description="Player rank (1-500)")
    points: conint(ge=0, le=200_000) = Field(..., description="Ranking points")
    snapshot_date: date = Field(..., description="Snapshot date")
    sources: List[str] = Field(default_factory=list, description="Data sources")

    @field_validator('snapshot_date')
    @classmethod
    def validate_snapshot_date(cls, v):
        """Ensure snapshot is within 90 days."""
        if isinstance(v, str):
            v = datetime.strptime(v, "%Y-%m-%d").date()
        today = date.today()
        age_days = (today - v).days
        if age_days > 90:
            raise ValueError(f"Snapshot date {v} is too old (>{age_days} days)")
        return v


class EventInfo(BaseModel):
    """PSA event information."""
    name: str
    city: Optional[str] = None
    country: Optional[str] = None
    venue: Optional[str] = None
    tier: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    url: Optional[str] = None


class PlayerResolution(BaseModel):
    """Resolved player information."""
    canonical: str
    profile_url: str


class ProbabilityPair(BaseModel):
    """Probability pair for both players."""
    A: float = Field(ge=0, le=1)
    B: float = Field(ge=0, le=1)


class ConfidenceInterval(BaseModel):
    """95% confidence interval [low, high]."""
    A: List[float] = Field(min_length=2, max_length=2)
    B: List[float] = Field(min_length=2, max_length=2)


class PredictionSummary(BaseModel):
    """Prediction summary."""
    winner: str = Field(pattern="^[AB]$")
    proba: ProbabilityPair
    ci95: ConfidenceInterval


class ExplanationDriver(BaseModel):
    """Single prediction driver explanation."""
    feature: str
    impact: str
    note: str


class PredictionExplanation(BaseModel):
    """Explanation of prediction drivers."""
    drivers: List[ExplanationDriver]


class PredictionResponse(BaseModel):
    """Complete prediction response."""
    playerA: str
    playerB: str
    resolved: Dict[str, PlayerResolution]
    event: Optional[EventInfo] = None
    ranking: Dict[str, RankingSnapshot]
    summary: PredictionSummary
    explain: PredictionExplanation
    sources: List[str]
    warnings: List[str] = Field(default_factory=list)


class ErrorDetail(BaseModel):
    """Error detail."""
    code: str
    message: str
    suggestions: Optional[List[Dict[str, str]]] = None


class ErrorResponse(BaseModel):
    """Error response."""
    error: ErrorDetail


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"


class UpstreamParseError(Exception):
    """Error parsing upstream data."""
    pass


class UpstreamChangedTemplate(Exception):
    """Upstream HTML template changed."""
    pass