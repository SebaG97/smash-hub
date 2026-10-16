from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, Field


class ExternalReference(BaseModel):
    source: str
    entity_type: str
    external_id: str = Field(min_length=1, max_length=200)
    synced_at: datetime
    source_updated_at: datetime | None = None


class CompetitionProvider(Protocol):
    def fetch_tournament(self, external_id: str) -> dict: ...
