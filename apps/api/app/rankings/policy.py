from datetime import UTC, datetime, timedelta

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    initial_rating: float = 1500
    initial_rd: float = Field(default=350, gt=0)
    initial_volatility: float = Field(default=0.06, gt=0)
    tau: float = Field(default=0.5, gt=0)
    epsilon: float = Field(default=1e-6, gt=0, le=1e-3)
    max_iterations: int = Field(default=100, ge=10, le=10000)
    period_days: int = Field(default=7, ge=1, le=366)
    anchor: AwareDatetime = datetime(1970, 1, 5, tzinfo=UTC)
    minimum_sets: int = Field(default=5, ge=1)
    activity_days: int = Field(default=90, ge=1)


def utc(value):
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp must include timezone")
    return value.astimezone(UTC)


def period_start(value, policy):
    anchor = utc(policy.anchor)
    width = timedelta(days=policy.period_days)
    return anchor + ((utc(value) - anchor) // width) * width


def ranking_status(sets, last_activity, at, policy):
    if sets < policy.minimum_sets:
        return "PROVISIONAL"
    if last_activity is None or utc(at) - utc(last_activity) > timedelta(days=policy.activity_days):
        return "INACTIVE"
    return "ACTIVE"
