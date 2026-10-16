from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.competitions.router import Page, PlayerView


class Filters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    game_id: UUID
    mode: Literal["singles", "doubles"] = "singles"
    tournament_id: UUID | None = None
    community_id: UUID | None = None
    date_from: AwareDatetime | None = None
    date_to: AwareDatetime | None = None

    @model_validator(mode="after")
    def ordered_dates(self):
        if self.date_from and self.date_to and self.date_from >= self.date_to:
            raise ValueError("date_from must precede date_to")
        return self


class ListingFilters(Filters):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class MatchView(BaseModel):
    id: UUID
    tournament_id: UUID
    tournament_name: str
    event_id: UUID
    event_name: str
    completed_at: datetime | None
    opponents: list[PlayerView]
    result: Literal["W", "L"]
    score: int | None
    opponent_score: int | None
    round_number: int | None
    round_label: str | None
    winner_entrant_id: UUID
    stats_eligible: Literal[True] = True
    eligibility_reason: str
    source: str | None
    source_url: str | None


class PlacementView(BaseModel):
    entrant_id: UUID
    tournament_id: UUID
    tournament_name: str
    event_id: UUID
    event_name: str
    tournament_starts_at: datetime | None
    placement: int
    confirmed: Literal[True] = True


class OpponentView(BaseModel):
    opponent: PlayerView
    sets_played: int
    wins: int
    losses: int
    win_rate: float | None
    last_encounter_at: datetime | None


class TournamentSummary(BaseModel):
    id: UUID
    name: str


class StatisticsView(BaseModel):
    player: PlayerView
    filters: Filters
    sets_played: int
    wins: int
    losses: int
    win_rate: float | None
    tournaments_played: int
    tournaments_registered: int
    first_set_at: datetime | None
    last_set_at: datetime | None
    latest_tournament: TournamentSummary | None
    best_final_placement: int | None
    unique_opponents: int


class MatchPage(Page[MatchView]):
    filters: Filters


class OpponentPage(Page[OpponentView]):
    filters: Filters


class PlacementPage(Page[PlacementView]):
    filters: Filters


class HeadToHeadView(BaseModel):
    player_a: PlayerView
    player_b: PlayerView
    filters: Filters
    encounters: int
    wins_a: int
    wins_b: int
    win_rate_a: float | None
    win_rate_b: float | None
    first_encounter_at: datetime | None
    last_encounter_at: datetime | None
    history: MatchPage
