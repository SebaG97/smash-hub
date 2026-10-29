"""Seeding and ranking projects: dataset storage, calculation runs, overrides and audit."""

import asyncio
import csv
import io
import logging
import re
import threading
import unicodedata
from datetime import UTC, datetime, timedelta

from pydantic import ValidationError
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.integrations.startgg.client import ImportFailure, StartGGClient
from app.players.mains import costumes_by_startgg_player, mains_by_startgg_player, with_costume
from app.rankings.policy import utc
from app.seeding import startgg
from app.seeding.engine import ALGORITHM, METHODS, Parameters, apply_overrides, compute
from app.seeding.models import (
    SeedingAuditEntry,
    SeedingEntrant,
    SeedingOverride,
    SeedingProject,
    SeedingResult,
    SeedingRun,
    SeedingSet,
)

STALE_REFRESH = timedelta(minutes=45)
log = logging.getLogger("app")


class ProjectNotFound(Exception):
    pass


class InvalidRequest(Exception):
    pass


class RefreshBusy(Exception):
    pass


RESERVED_SLUGS = {"session"}
EVENT_PATH = re.compile(r"tournament/[A-Za-z0-9-]{1,150}/event/[A-Za-z0-9-]{1,150}")


class SlugTaken(Exception):
    pass


def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80]


def event_path(value):
    """start.gg event link or path -> 'tournament/<t>/event/<e>' (nothing else is accepted)."""
    match = EVENT_PATH.search(value or "")
    if not match or ("://" in value and not re.match(r"https://(www\.)?start\.gg/", value)):
        raise InvalidRequest(
            "Pega el link del evento de start.gg (…/tournament/<torneo>/event/<evento>)."
        )
    return match.group(0)


def create_project(
    session, actor, *, kind, name, slug, window_start, end, event=None, country=None
):
    """Create a seeding (needs the start.gg event dict) or a ranking (needs a country)."""
    slug = slugify(slug or name)
    if not slug or slug in RESERVED_SLUGS:
        raise InvalidRequest("Elige otro nombre corto (slug).")
    if session.scalar(select(SeedingProject.id).where(SeedingProject.slug == slug)):
        raise SlugTaken
    if utc(end) <= utc(window_start):
        raise InvalidRequest("El período debe terminar después de empezar.")
    common = dict(
        slug=slug,
        name=name.strip()[:200],
        window_start=window_start,
        event_date=end,
        merges={},
        duplicates={},
    )
    if kind == "seeding":
        project = SeedingProject(
            kind="seeding",
            startgg_event_id=str(event["id"]),
            startgg_event_slug=event.get("slug"),
            startgg_videogame_id=str((event.get("videogame") or {}).get("id") or "1386"),
            **common,
        )
    else:
        project = SeedingProject(
            kind="ranking",
            country_code=country.upper(),
            startgg_videogame_id="1386",
            published=True,
            **common,
        )
    session.add(project)
    session.flush()
    audit(
        session,
        project,
        "create",
        actor,
        kind=kind,
        startgg_event_id=project.startgg_event_id,
        country=project.country_code,
    )
    return project


def _entrant_ids(session, project):
    return set(
        session.scalars(
            select(SeedingEntrant.startgg_player_id).where(SeedingEntrant.project_id == project.id)
        )
    )


def _recalculate_if_loaded(session, project, actor):
    if project.current_run_id is not None and project.refresh_status != "RUNNING":
        session.flush()
        recalculate(session, project, actor)


def set_merge(session, project, source, target, actor):
    entrants = _entrant_ids(session, project)
    merges = dict(project.merges or {})
    if source == target:
        raise InvalidRequest("Un ID no se puede fusionar consigo mismo.")
    if target not in entrants:
        raise InvalidRequest("El ID de destino tiene que ser un jugador de la lista.")
    if target in merges or source in merges.values():
        raise InvalidRequest("No se pueden encadenar fusiones; fusiona directo al ID final.")
    if project.kind == "seeding" and source in entrants:
        raise InvalidRequest("Los dos son inscritos: márcalo como inscripción duplicada.")
    merges[source] = target
    project.merges = merges
    audit(session, project, "merge", actor, source=source, target=target)
    _recalculate_if_loaded(session, project, actor)


def clear_merge(session, project, source, actor):
    merges = dict(project.merges or {})
    if merges.pop(source, None) is None:
        raise InvalidRequest("Esa fusión no existe.")
    project.merges = merges
    audit(session, project, "unmerge", actor, source=source)
    _recalculate_if_loaded(session, project, actor)


def set_duplicate(session, project, player, keep, actor):
    if project.kind != "seeding":
        raise InvalidRequest("Las inscripciones duplicadas solo existen en un seeding.")
    entrants = _entrant_ids(session, project)
    if player == keep or player not in entrants or keep not in entrants:
        raise InvalidRequest("Elige dos inscritos distintos.")
    duplicates = dict(project.duplicates or {})
    if keep in duplicates:
        raise InvalidRequest("La inscripción que se conserva ya está marcada como duplicada.")
    duplicates[player] = keep
    project.duplicates = duplicates
    audit(session, project, "duplicate", actor, player=player, keep=keep)
    _recalculate_if_loaded(session, project, actor)


def clear_duplicate(session, project, player, actor):
    duplicates = dict(project.duplicates or {})
    if duplicates.pop(player, None) is None:
        raise InvalidRequest("Esa inscripción no está marcada como duplicada.")
    project.duplicates = duplicates
    audit(session, project, "unduplicate", actor, player=player)
    _recalculate_if_loaded(session, project, actor)


def _tag_key(name):
    tag = (name or "").split(" | ")[-1]
    tag = unicodedata.normalize("NFKD", tag).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", tag.lower())


def merge_candidates(project, entrants, sets, limit=40):
    """IDs whose tag matches a listed player's tag: likely the same person (never merged
    automatically, ADR-006). Seeding only looks at non-entrants; rankings at everyone."""
    by_key = {}
    for e in entrants:
        by_key.setdefault(_tag_key(e.gamer_tag), []).append(e)
    listed = {e.startgg_player_id for e in entrants}
    merges, duplicates = project.merges or {}, project.duplicates or {}
    seen = {}
    for s in sets:
        for pid, tag in ((s.p1_player_id, s.p1_tag), (s.p2_player_id, s.p2_tag)):
            if not pid or pid in merges or pid in duplicates:
                continue
            if project.kind == "seeding" and pid in listed:
                continue
            for target in by_key.get(_tag_key(tag), []):
                if target.startgg_player_id == pid or target.startgg_player_id in merges:
                    continue
                key = (pid, target.startgg_player_id)
                item = seen.setdefault(
                    key,
                    dict(
                        source=pid,
                        source_tag=tag,
                        target=target.startgg_player_id,
                        target_tag=target.gamer_tag,
                        sets=0,
                        counted_sets=0,
                    ),
                )
                item["sets"] += 1
                item["counted_sets"] += int(s.counted)
    ranked = sorted(seen.values(), key=lambda c: (-c["counted_sets"], -c["sets"], c["source"]))
    if project.kind == "ranking":
        # Each pair appears in both directions; keep the side with fewer sets as the source.
        counts = {}
        for s in sets:
            for pid in (s.p1_player_id, s.p2_player_id):
                counts[pid] = counts.get(pid, 0) + int(s.counted)
        unique = {}
        for c in ranked:
            pair = frozenset((c["source"], c["target"]))
            if pair not in unique:
                if counts.get(c["source"], 0) > counts.get(c["target"], 0):
                    c = dict(
                        c,
                        source=c["target"],
                        source_tag=c["target_tag"],
                        target=c["source"],
                        target_tag=c["source_tag"],
                    )
                unique[pair] = c
        ranked = list(unique.values())
    return ranked[:limit]


def project_by_slug(session, slug, *, lock=False):
    query = select(SeedingProject).where(SeedingProject.slug == slug)
    project = session.scalar(query.with_for_update() if lock else query)
    if project is None:
        raise ProjectNotFound
    return project


def audit(session, project, action, actor, **details):
    session.add(
        SeedingAuditEntry(project_id=project.id, action=action, actor=actor, details=details)
    )


def _columns(model, row):
    return {c.name: row[c.name] for c in model.__table__.columns if c.name in row}


def replace_dataset(session, project, entrants, sets, *, cutoff):
    session.execute(delete(SeedingSet).where(SeedingSet.project_id == project.id))
    session.execute(delete(SeedingEntrant).where(SeedingEntrant.project_id == project.id))
    session.flush()
    session.add_all(
        SeedingEntrant(project_id=project.id, **_columns(SeedingEntrant, e)) for e in entrants
    )
    session.add_all(SeedingSet(project_id=project.id, **_columns(SeedingSet, s)) for s in sets)
    project.data_cutoff = cutoff


def default_parameters(session, project):
    """The last run's parameters (so a refresh keeps the chosen method), else kind defaults."""
    if project.current_run_id is not None:
        run = session.get(SeedingRun, project.current_run_id)
        try:
            return Parameters.model_validate(run.parameters)
        except ValidationError:
            pass  # Runs from an older algorithm version.
    return Parameters(min_sets=10) if project.kind == "ranking" else Parameters()


def recalculate(
    session,
    project,
    actor,
    *,
    window_start=None,
    window_end=None,
    parameters=None,
    method=None,
):
    start = utc(window_start) if window_start else utc(project.window_start)
    end = utc(window_end) if window_end else utc(project.event_date)
    if start < utc(project.window_start):
        raise InvalidRequest(
            "La fecha desde es anterior a los datos descargados: activa 'bajar datos nuevos'."
        )
    if end <= start or end > utc(project.event_date):
        raise InvalidRequest("La ventana debe terminar después de empezar y no después del evento.")
    params = parameters or default_parameters(session, project)
    if method is not None:
        params = params.model_copy(update={"method": method})
    entrants = [
        dict(player_id=e.startgg_player_id, gamer_tag=e.gamer_tag)
        for e in session.scalars(
            select(SeedingEntrant).where(SeedingEntrant.project_id == project.id)
        )
    ]
    if not entrants:
        raise InvalidRequest("El proyecto no tiene inscritos cargados.")
    sets = [
        {c.name: getattr(s, c.name) for c in SeedingSet.__table__.columns}
        for s in session.scalars(select(SeedingSet).where(SeedingSet.project_id == project.id))
    ]
    if project.kind == "ranking":
        allowed = ranked_events(session)
        sets = [s for s in sets if s["startgg_event_id"] in allowed]
    rows, summary = compute(
        entrants,
        sets,
        merges=project.merges or {},
        duplicates=project.duplicates or {},
        window_start=start,
        window_end=end,
        parameters=params,
    )
    run = SeedingRun(
        project_id=project.id,
        algorithm_version=ALGORITHM,
        parameters=params.model_dump(),
        window_start=start,
        window_end=end,
        data_cutoff=project.data_cutoff,
        actor=actor,
        set_count=summary["set_count"],
        event_count=summary["event_count"],
        offline_event_count=summary["offline_event_count"],
        player_count=summary["player_count"],
    )
    session.add(run)
    session.flush()
    keep = {"player_id", "gamer_tag", "seed_algorithm", "reasons", "flags"}
    session.add_all(
        SeedingResult(
            run_id=run.id,
            startgg_player_id=r["player_id"],
            gamer_tag=r["gamer_tag"],
            seed_algorithm=r["seed_algorithm"],
            reasons=r["reasons"],
            flags=r["flags"],
            metrics={k: v for k, v in r.items() if k not in keep},
        )
        for r in rows
    )
    project.current_run_id = run.id
    audit(
        session,
        project,
        "recalculate",
        actor,
        run_id=str(run.id),
        window_start=start.isoformat(),
        window_end=end.isoformat(),
        sets=summary["set_count"],
        method=params.method,
    )
    return run


def ranked_events(session):
    """start.gg event ids that feed rankings (Mission 20): only hub events that are their
    tournament's main bracket, in tournaments an organizer left checked for rankings."""
    from app.competitions.models import Event, Tournament
    from app.competitions.roles import event_roles
    from app.integrations.models import ExternalMapping

    main = {e for e, is_main in event_roles(session).items() if is_main}
    return {
        external
        for external, event in session.execute(
            select(ExternalMapping.external_id, Event.id)
            .join(Event, Event.id == ExternalMapping.event_id)
            .join(Tournament, Tournament.id == Event.tournament_id)
            .where(ExternalMapping.entity_type == "event", Tournament.counts_for_ranking.is_(True))
        )
        if event in main
    }


def excluded_tournaments(session, sets):
    """Brackets in this dataset that do not count: unchecked tournaments, secondary events
    (amateur, ladder…) and tournaments never imported into the hub."""
    from app.competitions.models import Event, Tournament
    from app.integrations.models import ExternalMapping

    allowed = ranked_events(session)
    # Secondary brackets of checked tournaments are named with their event.
    secondary = {
        external: name
        for external, name, counts in session.execute(
            select(ExternalMapping.external_id, Event.name, Tournament.counts_for_ranking)
            .join(Event, Event.id == ExternalMapping.event_id)
            .join(Tournament, Tournament.id == Event.tournament_id)
            .where(ExternalMapping.entity_type == "event")
        )
        if counts
    }
    found = set()
    for s in sets:
        if s.counted and s.startgg_event_id not in allowed:
            event = secondary.get(s.startgg_event_id)
            found.add(
                s.tournament_name
                if event is None or event == s.tournament_name
                else f"{s.tournament_name} · {event}"
            )
    return sorted(found)


def _overrides(session, project):
    return [
        dict(
            player_id=o.startgg_player_id,
            seed=o.seed,
            reason=o.reason,
            actor=o.actor,
            updated_at=o.updated_at.isoformat() if o.updated_at else None,
        )
        for o in session.scalars(
            select(SeedingOverride).where(SeedingOverride.project_id == project.id)
        )
    ]


def final_seeding(session, project):
    if project.current_run_id is None:
        return None, []
    run = session.get(SeedingRun, project.current_run_id)
    results = session.scalars(
        select(SeedingResult)
        .where(SeedingResult.run_id == run.id)
        .order_by(SeedingResult.seed_algorithm)
    )
    rows = [
        dict(
            r.metrics,
            player_id=r.startgg_player_id,
            gamer_tag=r.gamer_tag,
            seed_algorithm=r.seed_algorithm,
            reasons=r.reasons,
            flags=r.flags,
        )
        for r in results
    ]
    mains = mains_by_startgg_player(session, [r["player_id"] for r in rows])
    # Seeding entrants carry their recent picks from start.gg (foreign players included);
    # otherwise use what the hub's imported tournaments say.
    recent = dict(
        session.execute(
            select(SeedingEntrant.startgg_player_id, SeedingEntrant.mains).where(
                SeedingEntrant.project_id == project.id, SeedingEntrant.mains.is_not(None)
            )
        ).all()
    )
    costumes = costumes_by_startgg_player(session, [r["player_id"] for r in rows])
    for r in rows:
        picks = recent.get(r["player_id"]) or mains.get(r["player_id"], [])
        r["mains"] = with_costume([dict(m) for m in picks[:2]], costumes.get(r["player_id"]))
    return run, apply_overrides(rows, _overrides(session, project))


def set_override(session, project, player_id, seed, reason, actor):
    if project.kind == "ranking":
        raise InvalidRequest("Los rankings no admiten ajustes manuales: salen solo del cálculo.")
    run, rows = final_seeding(session, project)
    if not any(r["player_id"] == player_id for r in rows):
        raise InvalidRequest("Ese jugador no está en el seeding actual.")
    if seed > len(rows):
        raise InvalidRequest(f"El seed debe estar entre 1 y {len(rows)}.")
    current = session.scalar(
        select(SeedingOverride).where(
            SeedingOverride.project_id == project.id, SeedingOverride.startgg_player_id == player_id
        )
    )
    before = next(r["seed"] for r in rows if r["player_id"] == player_id)
    if current is None:
        session.add(
            SeedingOverride(
                project_id=project.id,
                startgg_player_id=player_id,
                seed=seed,
                reason=reason,
                actor=actor,
            )
        )
    else:
        current.seed, current.reason, current.actor = seed, reason, actor
    audit(
        session,
        project,
        "move",
        actor,
        player_id=player_id,
        from_seed=before,
        to_seed=seed,
        reason=reason,
    )


def clear_override(session, project, player_id, actor):
    found = session.execute(
        delete(SeedingOverride).where(
            SeedingOverride.project_id == project.id, SeedingOverride.startgg_player_id == player_id
        )
    )
    if found.rowcount:
        audit(session, project, "reset", actor, player_id=player_id)
    return bool(found.rowcount)


def view(session, project):
    run, rows = final_seeding(session, project)
    sets = session.scalars(select(SeedingSet).where(SeedingSet.project_id == project.id)).all()
    entrants = session.scalars(
        select(SeedingEntrant).where(SeedingEntrant.project_id == project.id)
    ).all()
    tags = {e.startgg_player_id: e.gamer_tag for e in entrants}
    classifications = {}
    for s in sets:
        classifications[s.classification] = classifications.get(s.classification, 0) + 1
    return dict(
        slug=project.slug,
        name=project.name,
        kind=project.kind,
        published=project.published,
        public=False,
        country_code=project.country_code,
        method=(run.parameters or {}).get("method", "combined") if run else None,
        methods=[dict(id=k, **v) for k, v in METHODS.items()],
        startgg_event_slug=project.startgg_event_slug,
        event_date=project.event_date,
        window_start=project.window_start,
        data_cutoff=project.data_cutoff,
        refresh=dict(
            status=project.refresh_status,
            started_at=project.refresh_started_at,
            progress=project.refresh_progress,
            error=project.refresh_error,
        ),
        dataset=dict(
            entrants=len(entrants),
            sets=len(sets),
            counted_sets=sum(s.counted for s in sets),
            events=len({s.startgg_event_id for s in sets}),
            offline_events=len({s.startgg_event_id for s in sets if not s.online}),
            classifications=classifications,
        ),
        merges=[
            dict(from_player_id=k, to_player_id=v, tag=tags.get(v))
            for k, v in (project.merges or {}).items()
        ],
        merge_candidates=merge_candidates(project, entrants, sets),
        excluded_tournaments=excluded_tournaments(session, sets)
        if project.kind == "ranking"
        else [],
        duplicates=[
            dict(player_id=k, kept_player_id=v, tag=tags.get(v))
            for k, v in (project.duplicates or {}).items()
        ],
        run=None
        if run is None
        else dict(
            id=run.id,
            created_at=run.created_at,
            actor=run.actor,
            algorithm_version=run.algorithm_version,
            parameters=run.parameters,
            window_start=run.window_start,
            window_end=run.window_end,
            data_cutoff=run.data_cutoff,
            set_count=run.set_count,
            event_count=run.event_count,
            offline_event_count=run.offline_event_count,
            player_count=run.player_count,
        ),
        seeds=rows,
    )


def audit_log(session, project, limit=100):
    entries = session.scalars(
        select(SeedingAuditEntry)
        .where(SeedingAuditEntry.project_id == project.id)
        .order_by(SeedingAuditEntry.created_at.desc())
        .limit(limit)
    )
    return [
        dict(at=e.created_at, action=e.action, actor=e.actor, details=e.details) for e in entries
    ]


EXPORT_FIELDS = [
    "seed",
    "seed_algorithm",
    "gamer_tag",
    "startgg_player_id",
    "manual",
    "manual_reason",
    "main_circuit",
    "confidence",
    "rating",
    "rd",
    "conservative",
    "placement_score",
    "elo",
    "bradley_terry",
    "points",
    "win_rate",
    "wilson",
    "wins",
    "losses",
    "sets",
    "offline_sets",
    "last_event",
    "flags",
    "reasons",
]


def export_csv(session, project):
    _, rows = final_seeding(session, project)
    if project.kind == "ranking":
        rows = [r for r in rows if r.get("eligible", True)]
    out = io.StringIO()
    writer = csv.DictWriter(out, EXPORT_FIELDS)
    writer.writeheader()
    for r in rows:
        o = r["override"]
        writer.writerow(
            dict(
                seed=r["seed"],
                seed_algorithm=r["seed_algorithm"],
                gamer_tag=r["gamer_tag"],
                startgg_player_id=r["player_id"],
                manual="sí" if o else "",
                manual_reason=o["reason"] if o else "",
                main_circuit=r.get("main_circuit") or "",
                confidence=r.get("confidence") or "",
                rating=r.get("rating"),
                rd=r.get("rd"),
                conservative=r.get("conservative"),
                placement_score=r.get("placement_score"),
                elo=r.get("elo"),
                bradley_terry=r.get("bradley_terry"),
                points=r.get("points"),
                win_rate=r.get("win_rate"),
                wilson=r.get("wilson"),
                wins=r.get("wins"),
                losses=r.get("losses"),
                sets=r.get("sets"),
                offline_sets=r.get("offline_sets"),
                last_event=r.get("last_event") or "",
                flags="; ".join(r["flags"]),
                reasons=" ".join(r["reasons"]),
            )
        )
    return "﻿" + out.getvalue()


# ---------------------------------------------------------------- start.gg refresh


def claim_refresh(engine, slug, actor, window_start):
    with Session(engine) as session:
        project = project_by_slug(session, slug, lock=True)
        now = datetime.now(UTC)
        if (
            project.refresh_status == "RUNNING"
            and project.refresh_started_at
            and now - utc(project.refresh_started_at) < STALE_REFRESH
        ):
            raise RefreshBusy
        start = utc(window_start) if window_start else utc(project.window_start)
        if start >= utc(project.event_date):
            raise InvalidRequest("La fecha desde debe ser anterior al evento.")
        project.refresh_status, project.refresh_started_at = "RUNNING", now
        project.refresh_progress, project.refresh_error = (
            dict(step="inscritos", done=0, total=None),
            None,
        )
        audit(session, project, "refresh_started", actor, window_start=start.isoformat())
        session.commit()
        return project.id, start


def _progress(engine, project_id, **values):
    with Session(engine) as session:
        session.execute(
            update(SeedingProject)
            .where(SeedingProject.id == project_id)
            .values(refresh_progress=values)
        )
        session.commit()


async def _download(engine, project_id, client, start):
    with Session(engine) as session:
        project = session.get(SeedingProject, project_id)
        kind, country = project.kind, project.country_code
        event_id, videogame, event_date = (
            project.startgg_event_id,
            project.startgg_videogame_id,
            project.event_date,
        )
    end = utc(event_date)
    if kind == "ranking":
        nodes, tags, _events = await startgg.fetch_country_sets(
            client,
            country=country,
            videogame_id=videogame,
            start=start,
            end=end,
            progress=lambda i, n: _progress(engine, project_id, step="torneos", done=i, total=n),
        )
    else:
        entrants = await startgg.fetch_entrants(client, event_id)
        nodes = []
        for i, entrant in enumerate(entrants):
            _progress(engine, project_id, step="sets", done=i, total=len(entrants))
            nodes += await startgg.fetch_player_sets(client, entrant["startgg_player_id"], start)
        for i, entrant in enumerate(entrants):
            _progress(engine, project_id, step="personajes", done=i, total=len(entrants))
            try:
                entrant["mains"] = await startgg.fetch_player_mains(
                    client, entrant["startgg_player_id"], videogame
                )
            except ImportFailure:
                entrant["mains"] = None  # Cosmetic: never fail the refresh for icons.
    cutoff = datetime.now(UTC)
    rows, excluded = startgg.normalize(
        nodes,
        videogame_id=videogame,
        own_event_id=event_id,
        start=start,
        end=min(cutoff, end),
    )
    if kind == "ranking":
        # The circuit's players are everyone with at least one counted set.
        players = sorted(
            {s[k] for s in rows if s["counted"] for k in ("p1_player_id", "p2_player_id") if s[k]}
        )
        entrants = [
            dict(
                startgg_entrant_id=f"p{pid}",
                startgg_player_id=pid,
                gamer_tag=(tags.get(pid) or pid)[:120],
            )
            for pid in players
        ]
    return entrants, rows, excluded, cutoff


def run_refresh(engine, project_id, token, actor, start, method=None):
    async def main():
        async with StartGGClient(token, interval=0.9) as client:
            return await _download(engine, project_id, client, start)

    try:
        entrants, rows, excluded, cutoff = asyncio.run(main())
        with Session(engine) as session:
            project = session.get(SeedingProject, project_id, with_for_update=True)
            replace_dataset(session, project, entrants, rows, cutoff=cutoff)
            project.window_start = start
            session.flush()
            run = recalculate(session, project, actor, method=method)
            project.refresh_status, project.refresh_progress = "IDLE", None
            audit(
                session,
                project,
                "refresh_completed",
                actor,
                entrants=len(entrants),
                sets=len(rows),
                excluded=excluded,
                run_id=str(run.id),
            )
            session.commit()
    except Exception as exc:
        code = str(exc) if isinstance(exc, ImportFailure) else type(exc).__name__
        log.error("Seeding refresh failed: %s", code)
        with Session(engine) as session:
            project = session.get(SeedingProject, project_id)
            project.refresh_status, project.refresh_error = "FAILED", code[:80]
            audit(session, project, "refresh_failed", actor, error=code[:80])
            session.commit()


def start_refresh(engine, slug, actor, token, window_start=None, *, method=None, runner=None):
    if token is None or not token.get_secret_value().strip():
        raise InvalidRequest("La API no tiene STARTGG_API_TOKEN configurado.")
    project_id, start = claim_refresh(engine, slug, actor, window_start)
    args = (engine, project_id, token, actor, start, method)
    if runner is not None:
        runner(*args)
    else:
        threading.Thread(target=run_refresh, args=args, daemon=True, name="seeding-refresh").start()


def set_published(session, project, published, actor):
    project.published = published
    audit(session, project, "publish" if published else "unpublish", actor)


PUBLIC_ROW = {
    "seeding": ("seed", "gamer_tag", "mains"),
    "ranking": ("seed", "gamer_tag", "mains", "wins", "losses", "sets", "last_event"),
}


def _public_prefixes(session, rows, seeds):
    """Approved team prefix of each row (Mission 22), matched by start.gg player id."""
    from app.players.models import ExternalIdentity
    from app.teams import service as teams

    keys = {f"player:{r['player_id']}": i for i, r in enumerate(rows)}
    hub = dict(
        session.execute(
            select(ExternalIdentity.external_id, ExternalIdentity.player_id).where(
                ExternalIdentity.external_id.in_(list(keys))
            )
        ).all()
    )
    shown = teams.display(session, set(hub.values())) if hub else {}
    for key, i in keys.items():
        seeds[i]["prefix"] = (shown.get(hub.get(key)) or {}).get("prefix")


def public_view(session, project):
    """What a reader sees: the official order, mains and (rankings) the official reasons."""
    full = view(session, project)
    run = full["run"]
    method = full["method"]
    rows = full["seeds"]
    if project.kind == "ranking":
        rows = [r for r in rows if r.get("eligible", True)]
    seeds = []
    for place, r in enumerate(rows, 1):
        item = {k: r.get(k) for k in PUBLIC_ROW[project.kind]}
        if project.kind == "ranking":
            item["seed"] = place
            item["score"] = (r.get("scores") or {}).get(method)
            item["reasons"] = (r.get("reasons_by_method") or {}).get(method, r.get("reasons"))
        seeds.append(item)
    _public_prefixes(session, rows, seeds)
    label = next((m["label"] for m in full["methods"] if m["id"] == method), method)
    return dict(
        slug=full["slug"],
        name=full["name"],
        kind=full["kind"],
        country_code=full["country_code"],
        published=project.published,
        public=True,
        method=method,
        method_label=label,
        startgg_event_slug=full["startgg_event_slug"],
        event_date=full["event_date"],
        window_start=full["window_start"],
        data_cutoff=full["data_cutoff"],
        run=None
        if run is None
        else dict(
            window_start=run["window_start"],
            window_end=run["window_end"],
            set_count=run["set_count"],
            event_count=run["event_count"],
            parameters={"min_sets": (run["parameters"] or {}).get("min_sets", 0)},
        ),
        seeds=seeds,
    )


def clear_all_overrides(session, project, actor):
    """Drop every manual move so the order is the calculation's again."""
    removed = session.execute(
        delete(SeedingOverride).where(SeedingOverride.project_id == project.id)
    ).rowcount
    if removed:
        audit(session, project, "reset_all", actor, removed=removed)
    return removed
