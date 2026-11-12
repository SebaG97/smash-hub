# Import all modules to register metadata for migrations and tests.
from app.auth.models import AuthAuditEntry, PasswordResetToken, User, UserSession
from app.communities.models import Community, CommunityGame, Country, Region
from app.competitions.models import (
    EntrantMember,
    Event,
    EventEntrant,
    Set,
    SetSelection,
    SetSide,
    Tournament,
    TournamentParticipant,
)
from app.games.models import Character, Game
from app.integrations.models import DataSource, ExternalMapping, ImportJob
from app.links.models import PlayerLink, PlayerLinkRequest
from app.players.models import ExternalIdentity, Player, PlayerAlias
from app.prode.models import (
    ProdeAchievement,
    ProdeAuditEntry,
    ProdeCandidate,
    ProdeContest,
    ProdePrediction,
    ProdePredictionHistory,
    ProdeQuestion,
    ProdeScore,
)
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
from app.sync.models import (
    StartggEntrant,
    StartggEntrantMember,
    StartggEvent,
    StartggSyncRun,
    StartggTournament,
)
from app.teams.models import TeamPrefix

__all__ = [
    "StartggEntrant",
    "StartggEntrantMember",
    "StartggEvent",
    "StartggSyncRun",
    "StartggTournament",
    "AuthAuditEntry",
    "PasswordResetToken",
    "PlayerLink",
    "PlayerLinkRequest",
    "User",
    "UserSession",
    "ProdeAchievement",
    "ProdeAuditEntry",
    "ProdeCandidate",
    "ProdeContest",
    "ProdePrediction",
    "ProdePredictionHistory",
    "ProdeQuestion",
    "ProdeScore",
    "TeamPrefix",
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
    "SetSelection",
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
