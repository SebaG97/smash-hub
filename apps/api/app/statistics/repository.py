"""SQL read models: one row per set, before any aggregation/pagination."""

from sqlalchemy import any_, case, func, literal, select
from sqlalchemy.orm import aliased

from app.competitions.models import (
    EntrantMember,
    Event,
    EventEntrant,
    Set,
    SetSide,
    Tournament,
    TournamentParticipant,
)
from app.integrations.models import DataSource, ExternalMapping
from app.players.models import Player
from app.statistics.policy import eligibility


def scoped_events(filters):
    size = 1 if filters.mode == "singles" else 2
    stmt = (
        select(Event.id)
        .join(Tournament)
        .where(
            Tournament.published.is_(True),
            Event.game_id == filters.game_id,
            Event.team_size == size,
            Event.competition_type == size,
        )
    )
    if filters.tournament_id:
        stmt = stmt.where(Tournament.id == filters.tournament_id)
    if filters.community_id:
        stmt = stmt.where(Tournament.community_id == filters.community_id)
    return stmt.cte("scoped_events")


def apply_dates(stmt, column, filters):
    if filters.date_from:
        stmt = stmt.where(column >= filters.date_from)
    if filters.date_to:
        stmt = stmt.where(column < filters.date_to)
    return stmt


def rosters(scoped):
    return (
        select(
            EntrantMember.entrant_id,
            func.array_agg(TournamentParticipant.player_id).label("players"),
            func.count().label("size"),
            func.count(func.distinct(TournamentParticipant.player_id)).label("unique_players"),
        )
        .join(TournamentParticipant, TournamentParticipant.id == EntrantMember.participant_id)
        .where(EntrantMember.event_id.in_(select(scoped.c.id)))
        .group_by(EntrantMember.entrant_id)
        .cte("rosters")
    )


def eligible_sets(session, filters):
    scoped = scoped_events(filters)
    roster = rosters(scoped)
    a, b = aliased(SetSide), aliased(SetSide)
    ra, rb = roster.alias("roster_a"), roster.alias("roster_b")
    # Only the verified start.gg source may create a provider link. Its mapping
    # uniqueness guarantees this outer join never multiplies a set.
    source = (
        select(ExternalMapping.set_id, ExternalMapping.manual_locked)
        .join(DataSource)
        .where(DataSource.slug == "start-gg", ExternalMapping.entity_type == "set")
        .cte("source")
    )
    size = 1 if filters.mode == "singles" else 2
    stmt = (
        select(
            Set.id,
            Set.event_id,
            Event.name.label("event_name"),
            Tournament.id.label("tournament_id"),
            Tournament.name.label("tournament_name"),
            Tournament.slug.label("tournament_slug"),
            Set.completed_at,
            Set.round_number,
            Set.round_label,
            case(
                (Set.stats_eligible.is_(True), Set.classification_reason),
                else_="final_two_opponents_winner_without_scores",
            ).label("eligibility_reason"),
            a.entrant_id.label("entrant_a"),
            b.entrant_id.label("entrant_b"),
            ra.c.players.label("players_a"),
            rb.c.players.label("players_b"),
            a.is_winner.label("a_won"),
            a.score.label("score_a"),
            b.score.label("score_b"),
            case((source.c.set_id.is_not(None), literal("start.gg"))).label("source"),
        )
        .select_from(Set)
        .join(Event, Event.id == Set.event_id)
        .join(Tournament, Tournament.id == Event.tournament_id)
        .join(a, (a.set_id == Set.id) & (a.side == 1))
        .join(b, (b.set_id == Set.id) & (b.side == 2))
        .join(ra, ra.c.entrant_id == a.entrant_id)
        .join(rb, rb.c.entrant_id == b.entrant_id)
        .outerjoin(source, source.c.set_id == Set.id)
        .where(
            Set.event_id.in_(select(scoped.c.id)),
            eligibility(session, scoped),
            source.c.manual_locked.is_not(True),
            a.is_winner != b.is_winner,
            ra.c.size == size,
            rb.c.size == size,
            ra.c.unique_players == size,
            rb.c.unique_players == size,
            ~ra.c.players.op("&&")(rb.c.players),
        )
    )
    return apply_dates(stmt, Set.completed_at, filters).cte("eligible_sets")


def perspective(universe, player_id, opponent_id=None):
    c = universe.c
    is_a = literal(player_id) == any_(c.players_a)
    stmt = select(
        c.id,
        c.event_id,
        c.event_name,
        c.tournament_id,
        c.tournament_name,
        c.tournament_slug,
        c.completed_at,
        c.round_number,
        c.round_label,
        c.eligibility_reason,
        c.source,
        case((is_a, c.players_b), else_=c.players_a).label("opponent_ids"),
        case((is_a, c.entrant_b), else_=c.entrant_a).label("opponent_entrant_id"),
        case((is_a, c.a_won), else_=~c.a_won).label("won"),
        case((is_a, c.score_a), else_=c.score_b).label("score"),
        case((is_a, c.score_b), else_=c.score_a).label("opponent_score"),
        case((c.a_won, c.entrant_a), else_=c.entrant_b).label("winner_entrant_id"),
    ).where(is_a | (literal(player_id) == any_(c.players_b)))
    p = stmt.cte("player_sets")
    if opponent_id is not None:
        return select(p).where(literal(opponent_id) == any_(p.c.opponent_ids)).cte("h2h_sets")
    return p


def summary(session, matches):
    c = matches.c
    return (
        session.execute(
            select(
                func.count().label("sets_played"),
                func.count().filter(c.won).label("wins"),
                func.count().filter(~c.won).label("losses"),
                func.count(func.distinct(c.tournament_id)).label("tournaments_played"),
                func.min(c.completed_at).label("first_set_at"),
                func.max(c.completed_at).label("last_set_at"),
            ).select_from(matches)
        )
        .mappings()
        .one()
    )


def ordered_matches(matches, ascending=False):
    time = matches.c.completed_at
    return select(matches).order_by(
        (time.asc() if ascending else time.desc()).nullslast(), matches.c.id
    )


def opponents(matches):
    return (
        select(
            Player.id,
            Player.tag,
            func.count().label("sets_played"),
            func.count().filter(matches.c.won).label("wins"),
            func.count().filter(~matches.c.won).label("losses"),
            func.max(matches.c.completed_at).label("last_encounter_at"),
        )
        .select_from(matches)
        .join(EntrantMember, EntrantMember.entrant_id == matches.c.opponent_entrant_id)
        .join(TournamentParticipant, TournamentParticipant.id == EntrantMember.participant_id)
        .join(Player, Player.id == TournamentParticipant.player_id)
        .group_by(Player.id, Player.tag)
        .order_by(func.count().desc(), Player.id)
    )


def registrations(filters, player_id):
    scoped = scoped_events(filters)
    stmt = (
        select(
            EventEntrant.id.label("entrant_id"),
            EventEntrant.placement,
            Tournament.id.label("tournament_id"),
            Tournament.name.label("tournament_name"),
            Tournament.starts_at.label("tournament_starts_at"),
            Event.id.label("event_id"),
            Event.name.label("event_name"),
        )
        .select_from(EntrantMember)
        .join(TournamentParticipant, TournamentParticipant.id == EntrantMember.participant_id)
        .join(EventEntrant, EventEntrant.id == EntrantMember.entrant_id)
        .join(Event, Event.id == EventEntrant.event_id)
        .join(Tournament, Tournament.id == Event.tournament_id)
        .where(TournamentParticipant.player_id == player_id, Event.id.in_(select(scoped.c.id)))
    )
    # Registration/placement have no individual timestamps in the current schema.
    return apply_dates(stmt, Tournament.starts_at, filters)


def placements(filters, player_id):
    rows = registrations(filters, player_id).subquery()
    return (
        select(rows)
        .where(rows.c.placement.is_not(None), rows.c.placement > 0)
        .order_by(
            rows.c.tournament_starts_at.desc().nullslast(), rows.c.event_id, rows.c.entrant_id
        )
    )


def page(session, stmt, page_number, page_size):
    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = session.execute(stmt.offset((page_number - 1) * page_size).limit(page_size)).mappings()
    return list(rows), total
