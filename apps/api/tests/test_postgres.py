from datetime import UTC, datetime

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.communities.service import bootstrap
from app.core.config import Settings
from app.database.base import Base
from app.database.models import (
    Community,
    Country,
    DataSource,
    EntrantMember,
    Event,
    EventEntrant,
    ExternalMapping,
    Game,
    Player,
    Set,
    SetSide,
    Tournament,
    TournamentParticipant,
)
from app.main import create_app


def fixture_competition(session, team_size=1):
    ids = bootstrap(session)
    tournament = Tournament(
        community_id=ids["community"], slug="isolated-test", name="Test fixture"
    )
    session.add(tournament)
    session.flush()
    event = Event(
        tournament_id=tournament.id,
        game_id=ids["game"],
        slug="test-event",
        name="Test fixture",
        team_size=team_size,
    )
    session.add(event)
    session.flush()
    entrants = []
    for side in range(2):
        entrant = EventEntrant(
            event_id=event.id, tournament_id=tournament.id, name=f"Fixture {side}"
        )
        session.add(entrant)
        session.flush()
        for position in range(1, team_size + 1):
            player = Player(tag="Non-unique tag")
            session.add(player)
            session.flush()
            participant = TournamentParticipant(
                tournament_id=tournament.id, player_id=player.id, tag_snapshot=player.tag
            )
            session.add(participant)
            session.flush()
            session.add(
                EntrantMember(
                    entrant_id=entrant.id,
                    event_id=event.id,
                    tournament_id=tournament.id,
                    participant_id=participant.id,
                    position=position,
                )
            )
        entrants.append(entrant)
    session.flush()
    return ids, event, entrants


def test_bootstrap_idempotent(db):
    with Session(db) as s, s.begin():
        first = bootstrap(s)
    with Session(db) as s, s.begin():
        assert bootstrap(s) == first
        for model in [Country, Game, Community, DataSource]:
            assert s.scalar(select(func.count()).select_from(model)) == 1
        assert s.scalar(select(func.count()).select_from(Player)) == 0


def test_real_readiness(db):
    with TestClient(
        create_app(Settings(_env_file=None, database_url="postgresql://u:p@localhost/x"), engine=db)
    ) as c:
        assert c.get("/api/v1/health/ready").status_code == 200


@pytest.mark.parametrize("size", [1, 2, 3])
def test_singles_doubles_and_larger_rosters(db, size):
    with Session(db) as s, s.begin():
        fixture_competition(s, size)


@pytest.mark.parametrize("status", ["completed", "dq", "bye", "pending"])
def test_valid_results(db, status):
    with Session(db) as s, s.begin():
        ids, event, entrants = fixture_competition(s)
        match = Set(
            event_id=event.id,
            status=status,
            best_of=5,
            completed_at=None if status == "pending" else datetime.now(UTC),
        )
        s.add(match)
        s.flush()
        for side, entrant in enumerate(entrants[:1] if status == "bye" else entrants, 1):
            s.add(
                SetSide(
                    set_id=match.id,
                    event_id=event.id,
                    entrant_id=entrant.id,
                    side=side,
                    is_winner=status != "pending" and side == 1,
                    score=(3 if side == 1 else 1) if status == "completed" else None,
                )
            )


@pytest.mark.parametrize(
    "case",
    [
        "two_winners",
        "wrong_score",
        "empty_result",
        "pending_winner",
        "bad_roster",
        "duplicate_mapping",
        "wrong_event",
    ],
)
def test_invalid_competitive_states(db, case):
    with pytest.raises(IntegrityError), Session(db) as s, s.begin():
        ids, event, entrants = fixture_competition(s)
        match = Set(
            event_id=event.id,
            status="pending" if case == "pending_winner" else "completed",
            best_of=5,
            completed_at=None if case == "pending_winner" else datetime.now(UTC),
        )
        s.add(match)
        s.flush()
        if case == "bad_roster":
            s.execute(
                text("DELETE FROM entrant_members WHERE entrant_id=:id"), {"id": entrants[0].id}
            )
        if case == "empty_result":
            return
        other = event
        if case == "wrong_event":
            other = Event(
                tournament_id=event.tournament_id, game_id=event.game_id, slug="other", name="Other"
            )
            s.add(other)
            s.flush()
        for side, entrant in enumerate(entrants, 1):
            s.add(
                SetSide(
                    set_id=match.id,
                    event_id=other.id,
                    entrant_id=entrant.id,
                    side=side,
                    is_winner=(side == 1 or case == "two_winners"),
                    score=None
                    if case == "pending_winner"
                    else (1 if case == "wrong_score" else (3 if side == 1 else 1)),
                )
            )
        if case == "duplicate_mapping":
            for _i in range(2):
                s.add(
                    ExternalMapping(
                        data_source_id=ids["source"],
                        entity_type="set",
                        external_id="same-provider-set",
                        set_id=match.id,
                        synced_at=datetime.now(UTC),
                    )
                )


def test_multi_game_and_community(db):
    with Session(db) as s, s.begin():
        ids, event, _ = fixture_competition(s)
        game = Game(slug="other-game", name="Other game")
        s.add(game)
        s.flush()
        s.add(Event(tournament_id=event.tournament_id, game_id=game.id, slug="other", name="Other"))
        s.add(Community(slug="another-community", name="Another community"))


def test_schema_matches_metadata(db):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    with db.connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []


def test_migration_roundtrip(db):
    cfg = Config("alembic.ini")
    command.downgrade(cfg, "base")
    assert inspect(db).get_table_names() == ["alembic_version"]
    command.upgrade(cfg, "head")
    assert set(inspect(db).get_table_names()) == set(Base.metadata.tables) | {"alembic_version"}
