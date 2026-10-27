"""Most used characters per player, from per-game start.gg selections (Mission 06)."""

from collections import defaultdict

from sqlalchemy import func, select

from app.competitions.models import (
    EntrantMember,
    Event,
    Set,
    SetSelection,
    Tournament,
    TournamentParticipant,
)
from app.games.models import Character


def player_mains(session, player_ids, *, limit=3):
    """{player_id: [{character, games, share}]} over singles games of eligible sets."""
    ids = list(player_ids)
    if not ids:
        return {}
    games = func.count(SetSelection.id)
    rows = session.execute(
        select(TournamentParticipant.player_id, Character.name, Character.image_url, games)
        .select_from(SetSelection)
        .join(Set, Set.id == SetSelection.set_id)
        .join(EntrantMember, EntrantMember.entrant_id == SetSelection.entrant_id)
        .join(TournamentParticipant, TournamentParticipant.id == EntrantMember.participant_id)
        .join(Event, Event.id == SetSelection.event_id)
        .join(Tournament, Tournament.id == Event.tournament_id)
        .join(Character, Character.id == SetSelection.character_id)
        .where(
            TournamentParticipant.player_id.in_(ids),
            Tournament.published.is_(True),
            Event.team_size == 1,
            Set.stats_eligible.is_(True),
        )
        .group_by(TournamentParticipant.player_id, Character.name, Character.image_url)
    ).all()
    counts = defaultdict(list)
    for player_id, name, icon, n in rows:
        counts[player_id].append((name, icon, n))
    result = {}
    for player_id, items in counts.items():
        total = sum(n for _, _, n in items)
        ranked = sorted(items, key=lambda x: (-x[2], x[0]))[:limit]
        result[player_id] = [
            {"character": name, "icon": icon, "games": n, "share": round(100 * n / total, 1)}
            for name, icon, n in ranked
        ]
    return result


def mains_by_startgg_player(session, startgg_player_ids, *, limit=2):
    """Same as player_mains, keyed by start.gg player id (seeding and ranking rows)."""
    from app.players.models import ExternalIdentity

    external = {f"player:{pid}": pid for pid in startgg_player_ids if pid}
    if not external:
        return {}
    links = dict(
        session.execute(
            select(ExternalIdentity.player_id, ExternalIdentity.external_id).where(
                ExternalIdentity.external_id.in_(list(external))
            )
        ).all()
    )
    mains = player_mains(session, list(links), limit=limit)
    return {external[ext]: mains[pid] for pid, ext in links.items() if pid in mains}
