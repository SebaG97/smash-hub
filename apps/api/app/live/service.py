"""A tournament being played, straight from start.gg (Mission 27).

Read only and never stored: the official results still come from the import. `fetch` reads
start.gg and `build` is pure, so it can be tested without either start.gg or a database.
"""

import re
from collections import Counter
from datetime import UTC, datetime

from app.brackets.layout import arrange
from app.competitions.roles import SECONDARY
from app.insights.preview import ULTIMATE
from app.integrations.startgg.client import ImportFailure
from app.integrations.startgg.images import tournament_images

RECENT_HOURS = 36  # a tournament stays listed this long after it starts
RUNNING = {2, 6}  # start.gg set states: in progress, called to a station


def singles(tournament):
    """Offline Ultimate singles events, the main one first."""
    events = [
        e
        for e in tournament.get("events") or []
        if str((e.get("videogame") or {}).get("id")) == ULTIMATE
        and not e.get("isOnline")
        and ((e.get("teamRosterSize") or {}).get("maxPlayers") or 1) <= 1
    ]
    return sorted(
        events,
        key=lambda e: (bool(SECONDARY.search(e.get("name") or "")), -(e.get("numEntrants") or 0)),
    )


def listed(nodes, now):
    """Tournaments under way or that started in the last hours, newest first."""
    items = []
    for t in nodes:
        events = singles(t)
        started = t.get("startAt")
        if t.get("isOnline") or not events or not started or started > now:
            continue
        active = any(e.get("state") == "ACTIVE" for e in events)
        if not active and now - started > RECENT_HOURS * 3600:
            continue
        items.append(
            dict(
                name=t["name"],
                slug=t["slug"].removeprefix("tournament/"),
                url=f"https://www.start.gg/{t['slug']}",
                starts_at=datetime.fromtimestamp(started, UTC).isoformat(),
                city=t.get("city"),
                images=tournament_images(t.get("images")),
                active=active,
            )
        )
    return items


async def fetch(client, tournament_slug, event_id=None):
    """Raw start.gg data of one event: phases in order of play, its sets and standings."""
    tournament = (await client.query("upcoming_tournament", {"slug": tournament_slug})).get(
        "tournament"
    )
    events = singles(tournament or {})
    if not events:
        raise ImportFailure("startgg_tournament_not_found")
    event = next((e for e in events if str(e["id"]) == str(event_id)), events[0])
    phases = ((await client.query("event_phases", {"id": event["id"]})).get("event") or {}).get(
        "phases"
    ) or []
    # start.gg's phaseOrder does not always follow play: bigger phases come first.
    phases = sorted(
        phases,
        key=lambda p: (
            -(((p.get("seeds") or {}).get("pageInfo") or {}).get("total") or 0),
            p.get("phaseOrder") or 0,
        ),
    )
    groups = []
    for phase in phases:
        nodes = (phase.get("phaseGroups") or {}).get("nodes") or []
        for node in sorted(nodes, key=lambda n: str(n.get("displayIdentifier") or "")):
            name = phase.get("name") or "Bracket"
            if len(nodes) > 1:
                name = f"{name} · {node.get('displayIdentifier') or ''}".strip(" ·")
            sets = await client.pages("live_sets", "phaseGroup", "sets", str(node["id"]))
            groups.append(
                dict(
                    id=str(node["id"]),
                    name=name,
                    type=phase.get("bracketType") or "DOUBLE_ELIMINATION",
                    sets=sets,
                )
            )
    standings = (await client.query("live_standings", {"id": event["id"]})).get("event") or {}
    return dict(
        tournament=tournament, events=events, event=event, groups=groups, standings=standings
    )


def person(entrant, seed, approve):
    parts = entrant.get("participants") or []
    part = parts[0] if parts else {}
    startgg_id = str((part.get("player") or {}).get("id") or "") or None
    return dict(
        tag=part.get("gamerTag") or entrant.get("name"),
        prefix=approve(part.get("prefix")),
        startgg_player_id=startgg_id,
        seed=seed,
    )


def score_of(slot):
    value = (((slot.get("standing") or {}).get("stats") or {}).get("score") or {}).get("value")
    return value if type(value) is int else None


def status_of(result):
    if result.get("state") == 3:
        scores = [score_of(slot) for slot in result.get("slots") or []]
        return "dq" if -1 in scores else "played"
    if result.get("state") == 6:
        return "called"  # called to a setup, not started yet
    return "live" if result.get("state") == 2 else "pending"


def shown(result):
    """Byes and an unused grand final reset are not sets anybody plays."""
    present = [s for s in result.get("slots") or [] if s.get("entrant")]
    if result.get("state") == 3 and len(present) < 2:
        return False
    return bool(present) or result.get("fullRoundText") != "Grand Final Reset"


def best_of(group_name, result):
    """3 or 5 from the phase name ("Pools (BO3)"), else from a decisive score; None when
    unknown. start.gg's totalGames says 5 even where organizers play best of 3."""
    found = re.search(r"\bBO\s?(\d+)\b", group_name or "", re.IGNORECASE)
    if found:
        return int(found[1])
    scores = [s for s in (score_of(slot) for slot in result.get("slots") or []) if s]
    if scores and max(scores) >= 3:
        return 5
    if result.get("state") == 3 and scores and max(scores) == 2:
        return 3
    return None


def set_view(result, approve, hub, *, group_name=None, known_mains=None):
    slots = (result.get("slots") or [])[:2]
    slots += [{}] * (2 - len(slots))
    ids = [str((s.get("entrant") or {}).get("id") or "") for s in slots]
    games = sorted(result.get("games") or [], key=lambda g: g.get("orderNum") or 0)
    detail, used = [], [[], []]
    for number, game in enumerate(games, 1):
        picks = {
            str((p.get("entrant") or {}).get("id")): (p.get("character") or {}).get("name")
            for p in game.get("selections") or []
        }
        names = [picks.get(i) for i in ids]
        for side, name in enumerate(names):
            if name and name not in used[side]:
                used[side].append(name)
        winner = str(game.get("winnerId") or "")
        detail.append(
            dict(
                number=number,
                winner=ids.index(winner) + 1 if winner and winner in ids else None,
                characters=[dict(name=n, icon=None) if n else None for n in names],
            )
        )
    sides = []
    winner = str(result.get("winnerId") or "")
    for i, slot in enumerate(slots):
        entrant = slot.get("entrant")
        seed = (slot.get("seed") or {}).get("seedNum")
        found = (
            person(entrant, seed, approve)
            if entrant
            else dict(tag=None, prefix=None, startgg_player_id=None, seed=seed)
        )
        score = score_of(slot)
        startgg_id = found.pop("startgg_player_id")
        player = hub.get(startgg_id)
        known = (known_mains or {}).get(startgg_id) or []
        sides.append(
            dict(
                **found,
                id=str(player) if player else None,
                score=score if score is not None and score >= 0 else None,
                winner=bool(entrant) and winner == ids[i],
                characters=[dict(name=n, icon=None) for n in used[i]],
                # The character picked last in this set, else the player's usual main.
                main=used[i][-1] if used[i] else (known[0]["character"] if known else None),
            )
        )
    completed = result.get("completedAt")
    stream = result.get("stream") or {}
    return dict(
        status=status_of(result),
        best_of=best_of(group_name, result),
        station=(result.get("station") or {}).get("number"),
        stream=dict(name=stream["streamName"], source=stream.get("streamSource"))
        if stream.get("streamName")
        else None,
        completed_at=datetime.fromtimestamp(completed, UTC).isoformat() if completed else None,
        sides=sides,
        games=detail,
    )


def decided(groups, event_state):
    """Is the top final? start.gg may take a while to close an event after grand finals."""
    if event_state == "COMPLETED":
        return True
    results = [s for g in groups for s in g["sets"]]
    rounds = {str(s["id"]): s.get("round") or 0 for s in results}
    done = {s.get("fullRoundText"): s for s in results if s.get("state") == 3}
    if "Grand Final Reset" in done:
        return True
    final = done.get("Grand Final")
    if not final:
        return False
    # The player coming from winners has one loss to spare: if they lost, a reset is due.
    for slot in final.get("slots") or []:
        if str((slot.get("entrant") or {}).get("id")) == str(final.get("winnerId")):
            return rounds.get(str(slot.get("prereqId")), 0) > 0
    return False


def played_mains(groups, startgg_id):
    """Characters a player used in these sets, most picked first, like `mains`."""
    counts = Counter()
    for group in groups:
        for result in group["sets"]:
            entrant = next(
                (
                    str(s["entrant"]["id"])
                    for s in result.get("slots") or []
                    if s.get("entrant")
                    and any(
                        str((p.get("player") or {}).get("id")) == startgg_id
                        for p in s["entrant"].get("participants") or []
                    )
                ),
                None,
            )
            if not entrant:
                continue
            for game in result.get("games") or []:
                for pick in game.get("selections") or []:
                    name = (pick.get("character") or {}).get("name")
                    if name and str((pick.get("entrant") or {}).get("id")) == entrant:
                        counts[name] += 1
    total = sum(counts.values())
    return [
        dict(character=name, icon=None, games=n, share=round(100 * n / total, 1))
        for name, n in sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:3]
    ]


def build(raw, *, approve, hub, known_mains=None, costumes=None):
    """The live payload. `approve` gives a prefix's approved label or None; `hub` maps
    start.gg player ids to hub players; `known_mains` fills in for characters not reported."""
    known_mains, costumes = known_mains or {}, costumes or {}
    tournament, event = raw["tournament"], raw["event"]
    state = raw["standings"].get("state") or event.get("state")
    final = decided(raw["groups"], state)
    groups = []
    current = None
    for group in raw["groups"]:
        results = group["sets"]
        if not any(s.get("entrant") for r in results for s in r.get("slots") or []):
            continue  # a phase nobody has reached yet
        nodes = []
        for r in results:
            visible = shown(r)
            node = dict(
                id=str(r["id"]),
                round=r.get("round"),
                label=r.get("fullRoundText"),
                shown=visible,
                prereqs=[
                    (str(s["prereqId"]), s.get("prereqPlacement"))
                    for s in r.get("slots") or []
                    if s.get("prereqType") == "set" and s.get("prereqId")
                ],
            )
            if visible:
                node.update(
                    set_view(r, approve, hub, group_name=group["name"], known_mains=known_mains)
                )
            nodes.append(node)
        groups.append(
            dict(
                id=group["id"],
                name=group["name"],
                type=group["type"],
                **arrange(nodes, group["type"]),
            )
        )
        if any(s.get("state") in RUNNING for s in results):
            current = current or group["id"]
    played = [
        g["id"]
        for g in groups
        if any(s["status"] == "played" for c in g["winners"] + g["losers"] for s in c["sets"])
    ]
    top = []
    for node in (raw["standings"].get("standings") or {}).get("nodes") or []:
        entrant = node.get("entrant")
        if not entrant or not node.get("placement"):
            continue
        found = person(entrant, entrant.get("initialSeedNum"), approve)
        startgg_id = found.pop("startgg_player_id")
        player = hub.get(startgg_id)
        mains = played_mains(raw["groups"], startgg_id) or list(known_mains.get(startgg_id) or [])
        for main in mains:
            main["costume"] = (costumes.get(startgg_id) or {}).get(main["character"], 1)
        top.append(
            dict(
                found,
                placement=node["placement"],
                id=str(player) if player else None,
                mains=mains,
            )
        )
    return dict(
        tournament=dict(
            name=tournament["name"],
            slug=tournament["slug"].removeprefix("tournament/"),
            url=f"https://www.start.gg/{tournament['slug']}",
            starts_at=datetime.fromtimestamp(tournament["startAt"], UTC).isoformat()
            if tournament.get("startAt")
            else None,
            city=tournament.get("city"),
            images=tournament_images(tournament.get("images")),
        ),
        events=[
            dict(id=str(e["id"]), name=e["name"], entrants=e.get("numEntrants"))
            for e in raw["events"]
        ],
        event=dict(id=str(event["id"]), name=event["name"], entrants=event.get("numEntrants")),
        final=final,
        top=top,
        projected=False,
        groups=groups,
        # The tab to open: where sets are being played, else the last one with results.
        current=current or (played[-1] if played else groups[0]["id"] if groups else None),
        updated_at=datetime.now(UTC).isoformat(),
    )


def matches(live, slug):
    """Sets being played or called to a setup, for the home page (Mission 33)."""
    found = []
    for group in live["groups"]:
        for column in group["winners"] + group["losers"]:
            for s in column["sets"]:
                if s["status"] in ("live", "called"):
                    found.append(
                        dict(
                            id=s["id"],
                            tournament=live["tournament"]["name"],
                            slug=slug,
                            group=group["name"],
                            round=column["label"],
                            status=s["status"],
                            best_of=s.get("best_of"),
                            station=s.get("station"),
                            stream=s.get("stream"),
                            sides=s["sides"],
                        )
                    )
    # Sets being played first, then the ones called, by setup.
    return sorted(found, key=lambda m: (m["status"] != "live", m["station"] or 999))
