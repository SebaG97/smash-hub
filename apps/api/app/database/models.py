# Import all modules to register metadata for migrations and tests.
from app.communities.models import Community, CommunityGame, Country, Region
from app.competitions.models import (
    EntrantMember,
    Event,
    EventEntrant,
    Set,
    SetSide,
    Tournament,
    TournamentParticipant,
)
from app.games.models import Character, Game
from app.integrations.models import DataSource, ExternalMapping, ImportJob
from app.players.models import ExternalIdentity, Player, PlayerAlias
from app.rankings.models import (
    RankingSnapshot,
    RatingCalculationRun,
    RatingPeriod,
    RatingPolicy,
    RatingPool,
    RatingSnapshot,
)
from app.seeding.models import (
    SeedingAuditEntry,
    SeedingEntrant,
    SeedingOverride,
    SeedingProject,
    SeedingResult,
    SeedingRun,
    SeedingSet,
)

__all__ = [
    "SeedingAuditEntry",
    "SeedingEntrant",
    "SeedingOverride",
    "SeedingProject",
    "SeedingResult",
    "SeedingRun",
    "SeedingSet",
    "RatingPolicy",
    "RatingPool",
    "RatingPeriod",
    "RatingSnapshot",
    "RankingSnapshot",
    "RatingCalculationRun",
    "Community",
    "CommunityGame",
    "Country",
    "Region",
    "EntrantMember",
    "Event",
    "EventEntrant",
    "Set",
    "SetSide",
    "Tournament",
    "TournamentParticipant",
    "Character",
    "Game",
    "DataSource",
    "ExternalMapping",
    "ImportJob",
    "ExternalIdentity",
    "Player",
    "PlayerAlias",
]
