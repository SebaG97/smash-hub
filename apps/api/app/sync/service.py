"""Syncing start.gg into the local copy (SH-SYNC-01, ADR-022).

One sync at a time per database: a run is claimed under an advisory lock, and none starts
while another run, a seeding download or the tournament importer is using start.gg, so the
token stays under its rate limit (80 requests a minute) whatever the number of API
instances. Each part of an event (registrations, then pools, then sets) is committed as
soon as it is complete, so a failure halfway keeps everything already copied.
"""

import asyncio
import logging
from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from app.integrations.startgg.client import ImportFailure, StartGGClient, parse_slug
from app.sync import store
from app.sync.models import StartggEvent, StartggSyncRun, StartggTournament

log = logging.getLogger(__name__)

ULTIMATE = "1386"
# A run still "running" after this long died with its process: it no longer blocks.
STALE_RUN = timedelta(minutes=20)
GATE = "startgg:sync"
# Tournaments are still synced (daily) this long after they end, then left alone.
FINISHED_DAYS = 3
# Failed slugs never stored (a seeding's tournament start.gg cannot find) wait this long.
RETRY_UNKNOWN = timedelta(hours=1)
MAX_PER_TICK = 10
ENTRANTS_PER_PAGE = 40


class SyncBusy(Exception):
    """Another sync, a seeding download or the importer is using start.gg right now."""


def now_utc():
    return datetime.now(UTC)


def _aware(value):
    return value if value is None or value.tzinfo else value.replace(tzinfo=UTC)


# ------------------------------------------------------------------ claiming and logging


def claim(engine, *, kind, trigger, actor, slug=None, now=None):
    """Open a run, or raise SyncBusy. Returns the run id."""
    from app.seeding.models import SeedingProject
    from app.seeding.service import STALE_REFRESH

    now = now or now_utc()
    with Session(engine) as s:
        s.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": GATE})
        # The importer holds this lock for its whole run (integrations.startgg.service).
        if not s.scalar(
            text("SELECT pg_try_advisory_xact_lock(hashtextextended('startgg:provider', 0))")
        ):
            raise SyncBusy("importer")
        for run in s.scalars(select(StartggSyncRun).where(StartggSyncRun.status == "running")):
            if now - _aware(run.started_at) < STALE_RUN:
                raise SyncBusy("sync")
            run.status, run.finished_at, run.error_code = "failed", now, "abandoned"
        if s.scalar(
            select(SeedingProject.id)
            .where(
                SeedingProject.refresh_status == "RUNNING",
                SeedingProject.refresh_started_at > now - STALE_REFRESH,
            )
            .limit(1)
        ):
            raise SyncBusy("seeding")
        tournament_id = None
        if slug:
            tournament_id = s.scalar(
                select(StartggTournament.id).where(StartggTournament.slug == slug)
            )
        run = StartggSyncRun(
            kind=kind,
            trigger=trigger,
            actor=actor[:60],
            slug=slug,
            tournament_id=tournament_id,
            status="running",
            started_at=now,
        )
        s.add(run)
        s.commit()
        return run.id


def _close(session, run_id, counts, warnings, error, now):
    run = session.get(StartggSyncRun, run_id)
    run.status = "failed" if error else "completed"
    run.finished_at = now
    run.counts = dict(counts)
    run.warnings = warnings[:50]
    run.error_code = error[:80] if error else None
    return run


def _error(exc):
    return str(exc) if isinstance(exc, ImportFailure) else type(exc).__name__


# ------------------------------------------------------------------ schedule


def tier(tournament, now):
    """How close a tournament is: far, week, day, live or finished (ADR-022)."""
    start, end = _aware(tournament.start_at), _aware(tournament.end_at)
    if end is None and start is not None:
        end = start + timedelta(days=1)
    if tournament.state == 3 or (end is not None and now > end + timedelta(hours=6)):
        return "finished"
    if tournament.state == 2 or (start is not None and now >= start - timedelta(hours=2)):
        return "live"
    if start is None or start - now > timedelta(days=7):
        return "far"
    if start - now > timedelta(days=1):
        return "week"
    return "day"


def next_sync(tournament, now, settings, *, failed):
    """When to sync this tournament again; None once it is long finished."""
    name = tier(tournament, now)
    if name == "finished":
        ended = _aware(tournament.end_at or tournament.start_at)
        if ended is None or now - ended > timedelta(days=FINISHED_DAYS):
            return None
    seconds = getattr(settings, f"startgg_sync_{name}_seconds")
    if failed:
        # Back off on repeated failures (5 min, 10, 20 ... up to 6 h), never faster
        # than the tournament's own frequency.
        backoff = 300 * 2 ** min(max(tournament.failures - 1, 0), 6)
        seconds = max(seconds, min(backoff, 21600))
    return now + timedelta(seconds=seconds)


# ------------------------------------------------------------------ one tournament


def detailed_events(session, tournament):
    """Events whose registrations, pools and sets are copied: the main offline Ultimate
    singles event (the one previews show) and any event a seeding is made for."""
    from app.insights.preview import singles_event
    from app.seeding.models import SeedingProject
    from app.sync.read import _events, provider_tournament

    events = _events(session, tournament.id)
    chosen = singles_event(provider_tournament(tournament, events))
    seeded = set(
        session.scalars(
            select(SeedingProject.startgg_event_slug).where(
                SeedingProject.kind == "seeding",
                SeedingProject.startgg_event_slug.like(f"tournament/{tournament.slug}/event/%"),
            )
        )
    )
    return [e.id for e in events if (chosen and e.id == chosen["id"]) or e.slug in seeded]


async def _sync(engine, client, slug, run_id, counts, warnings, reason):
    node = (await client.query("sync_tournament", {"slug": slug})).get("tournament")
    if not node:
        raise ImportFailure("startgg_tournament_not_found")
    with Session(engine) as s:
        row = store.tournament(s, node, now_utc(), counts, reason=reason, events_limit=50)
        if reason == "manual":
            row.tracked = True  # an administrator asked for it: keep it fresh from now on
        s.get(StartggSyncRun, run_id).tournament_id = row.id
        s.commit()
        targets = detailed_events(s, row)
    for event_id in targets:
        nodes = await client.pages(
            "sync_entrants", "event", "entrants", event_id, per_page=ENTRANTS_PER_PAGE
        )
        with Session(engine) as s:
            store.entrants(s, s.get(StartggEvent, event_id), nodes, now_utc(), counts, warnings)
            s.commit()


def run_tournament(engine, settings, run_id, slug, *, reason="manual", client_factory=None):
    """Sync one tournament (by slug) under an already claimed run; never raises."""
    counts, warnings, error = Counter(), [], None
    factory = client_factory or (
        lambda: StartGGClient(
            settings.startgg_api_token, interval=settings.startgg_sync_request_interval
        )
    )

    async def main():
        async with factory() as client:
            await _sync(engine, client, slug, run_id, counts, warnings, reason)

    try:
        asyncio.run(main())
    except Exception as exc:  # recorded on the run; the local copy keeps what it had
        error = _error(exc)
        log.warning("start.gg sync of %s failed: %s", slug, error)
    now = now_utc()
    with Session(engine) as s:
        run = _close(s, run_id, counts, warnings, error, now)
        row = s.get(StartggTournament, run.tournament_id) if run.tournament_id else None
        if row is not None:
            row.last_attempt_at, row.last_error = now, run.error_code
            row.last_status = run.status
            if error:
                row.failures += 1
            else:
                row.failures, row.last_success_at = 0, now
            row.next_sync_at = next_sync(row, now, settings, failed=bool(error))
        s.commit()
    return error


# ------------------------------------------------------------------ discovery


async def _discover(engine, client, country, run_id, counts):
    data = await client.query("upcoming_tournaments", {"country": country, "videogame": ULTIMATE})
    nodes = (data.get("tournaments") or {}).get("nodes")
    if not isinstance(nodes, list):
        raise ImportFailure("startgg_invalid_response")
    now = now_utc()
    with Session(engine) as s:
        listed = set()
        for node in nodes:
            if node.get("isOnline") or not str(node.get("slug") or "").startswith("tournament/"):
                continue
            row = store.tournament(s, node, now, counts, reason="calendar", events_limit=20)
            row.in_calendar = True
            listed.add(row.id)
        for row in s.scalars(
            select(StartggTournament).where(StartggTournament.in_calendar.is_(True))
        ):
            if row.id not in listed:
                row.in_calendar = False
                counts["calendar_left"] += 1
        counts["calendar"] = len(listed)
        s.commit()


def run_discovery(engine, settings, run_id, *, client_factory=None):
    counts, error = Counter(), None
    factory = client_factory or (
        lambda: StartGGClient(
            settings.startgg_api_token, interval=settings.startgg_sync_request_interval
        )
    )

    async def main():
        async with factory() as client:
            await _discover(engine, client, settings.startgg_sync_country, run_id, counts)

    try:
        asyncio.run(main())
    except Exception as exc:
        error = _error(exc)
        log.warning("start.gg discovery failed: %s", error)
    with Session(engine) as s:
        _close(s, run_id, counts, [], error, now_utc())
        s.commit()
    return error


# ------------------------------------------------------------------ what is due


def _seeding_slugs(session, now):
    """Tournament slugs of seedings for events not long past."""
    from app.seeding.models import SeedingProject

    slugs = set()
    for path in session.scalars(
        select(SeedingProject.startgg_event_slug).where(
            SeedingProject.kind == "seeding",
            SeedingProject.startgg_event_slug.is_not(None),
            SeedingProject.event_date > now - timedelta(days=FINISHED_DAYS),
        )
    ):
        try:
            slugs.add(parse_slug(path.split("/event/")[0]))
        except ImportFailure:
            continue
    return slugs


def due(engine, settings, now=None):
    """[(slug, reason)] to sync now: seedings' tournaments not stored yet, then tracked
    tournaments whose time came, most overdue first."""
    now = now or now_utc()
    with Session(engine) as s:
        known = set(s.scalars(select(StartggTournament.slug)))
        failed_recently = set(
            s.scalars(
                select(StartggSyncRun.slug).where(
                    StartggSyncRun.kind == "tournament",
                    StartggSyncRun.tournament_id.is_(None),
                    StartggSyncRun.started_at > now - RETRY_UNKNOWN,
                )
            )
        )
        items = [
            (slug, "seeding") for slug in sorted(_seeding_slugs(s, now) - known - failed_recently)
        ]
        items += [
            (slug, "scheduled")
            for slug in s.scalars(
                select(StartggTournament.slug)
                .where(
                    StartggTournament.tracked.is_(True),
                    StartggTournament.next_sync_at <= now,
                )
                .order_by(StartggTournament.next_sync_at)
            )
        ]
        return items


def discovery_due(engine, settings, now=None):
    now = now or now_utc()
    with Session(engine) as s:
        last = s.scalar(
            select(StartggSyncRun.started_at)
            .where(StartggSyncRun.kind == "discovery")
            .order_by(StartggSyncRun.started_at.desc())
            .limit(1)
        )
    return last is None or now - _aware(last) >= timedelta(
        seconds=settings.startgg_sync_discovery_seconds
    )


def tick(engine, settings, stop=None, *, client_factory=None):
    """One scheduler pass: discovery when due, then every due tournament, one by one."""
    try:
        if discovery_due(engine, settings):
            run_id = claim(engine, kind="discovery", trigger="auto", actor="sistema")
            run_discovery(engine, settings, run_id, client_factory=client_factory)
        for slug, reason in due(engine, settings)[:MAX_PER_TICK]:
            if stop is not None and stop.is_set():
                return
            run_id = claim(engine, kind="tournament", trigger="auto", actor="sistema", slug=slug)
            run_tournament(
                engine,
                settings,
                run_id,
                slug,
                reason="seeding" if reason == "seeding" else "calendar",
                client_factory=client_factory,
            )
    except SyncBusy as busy:
        log.info("start.gg sync waits: %s busy", busy)


# ------------------------------------------------------------------ administrators


def status(session, limit=30):
    now = now_utc()
    tournaments = session.scalars(
        select(StartggTournament)
        .where(
            or_(
                StartggTournament.tracked.is_(True),
                StartggTournament.in_calendar.is_(True),
            )
        )
        .order_by(StartggTournament.start_at.desc().nulls_last())
    ).all()
    runs = session.scalars(
        select(StartggSyncRun).order_by(StartggSyncRun.started_at.desc()).limit(limit)
    ).all()

    def iso(value):
        return _aware(value).isoformat() if value else None

    return dict(
        tournaments=[
            dict(
                slug=t.slug,
                name=t.name,
                starts_at=iso(t.start_at),
                tracked=t.tracked,
                reason=t.track_reason,
                in_calendar=t.in_calendar,
                tier=tier(t, now),
                next_sync_at=iso(t.next_sync_at),
                last_attempt_at=iso(t.last_attempt_at),
                last_success_at=iso(t.last_success_at),
                last_status=t.last_status,
                last_error=t.last_error,
                failures=t.failures,
            )
            for t in tournaments
        ],
        runs=[
            dict(
                id=str(r.id),
                kind=r.kind,
                slug=r.slug,
                trigger=r.trigger,
                actor=r.actor,
                status=r.status,
                started_at=iso(r.started_at),
                finished_at=iso(r.finished_at),
                counts=r.counts or {},
                warnings=r.warnings or [],
                error=r.error_code,
            )
            for r in runs
        ],
    )


def set_tracked(session, slug, tracked, now=None):
    row = session.scalar(select(StartggTournament).where(StartggTournament.slug == slug))
    if row is None:
        return None
    row.tracked = tracked
    row.next_sync_at = (now or now_utc()) if tracked else None
    return row
