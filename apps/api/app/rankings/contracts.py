from typing import Protocol
from uuid import UUID

from pydantic import BaseModel


class RankingScope(BaseModel):
    community_id: UUID
    game_id: UUID
    season_id: UUID
    team_size: int = 1


class RankingCalculator(Protocol):
    def calculate(self, scope: RankingScope) -> list[dict]: ...
