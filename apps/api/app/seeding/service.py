"""Seeding projects: dataset storage, calculation runs, manual overrides and audit."""

import asyncio
import csv
import io
import logging
import threading
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.integrations.startgg.client import ImportFailure, StartGGClient
from app.rankings.policy import utc
from app.seeding import startgg
from app.seeding.engine import ALGORITHM, Parameters, apply_overrides, compute
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


def recalculate(session, project, actor, *, window_start=None, window_end=None, parameters=None):
    start = utc(window_start) if window_start else utc(project.window_start)
    end = utc(window_end) if window_end else utc(project.event_date)
    if start < utc(project.window_start):
        raise InvalidRequest(
            "La fecha desde es anterior a los datos descargados: activa 'bajar datos nuevos'."
        )
    if end <= start or end > utc(project.event_date):
        raise InvalidRequest("La ventana debe terminar después de empezar y no después del evento.")
    params = parameters or Parameters()
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
    )
    return run


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
    return run, apply_overrides(rows, _overrides(session, project))


def set_override(session, project, player_id, seed, reason, actor):
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
        event_id, videogame, event_date = (
            project.startgg_event_id,
            project.startgg_videogame_id,
            project.event_date,
        )
    entrants = await startgg.fetch_entrants(client, event_id)
    nodes = []
    for i, entrant in enumerate(entrants):
        _progress(engine, project_id, step="sets", done=i, total=len(entrants))
        nodes += await startgg.fetch_player_sets(client, entrant["startgg_player_id"], start)
    cutoff = datetime.now(UTC)
    rows, excluded = startgg.normalize(
        nodes,
        videogame_id=videogame,
        own_event_id=event_id,
        start=start,
        end=min(cutoff, utc(event_date)),
    )
    return entrants, rows, excluded, cutoff


def run_refresh(engine, project_id, token, actor, start):
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
            run = recalculate(session, project, actor)
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


def start_refresh(engine, slug, actor, token, window_start=None, *, runner=None):
    if token is None or not token.get_secret_value().strip():
        raise InvalidRequest("La API no tiene STARTGG_API_TOKEN configurado.")
    project_id, start = claim_refresh(engine, slug, actor, window_start)
    args = (engine, project_id, token, actor, start)
    if runner is not None:
        runner(*args)
    else:
        threading.Thread(target=run_refresh, args=args, daemon=True, name="seeding-refresh").start()
