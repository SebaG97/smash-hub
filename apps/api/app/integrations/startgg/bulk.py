"""Background import of a country's tournaments with the Mission 02 importer (Mission 06).

Each tournament goes through ``run_import`` (validation, identity reconciliation,
classification and its own job row); one failing tournament never stops the rest.
Progress lives in process memory: there is a single API instance (ADR-011).
"""

import asyncio
import logging
import re
import threading
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.communities.service import bootstrap
from app.games.icons import sync_characters
from app.integrations.startgg.client import ImportFailure, StartGGClient, parse_slug
from app.integrations.startgg.service import run_import
from app.seeding import startgg as seeding_startgg

log = logging.getLogger("app")
_lock = threading.Lock()
_state = {"status": "idle"}


class ImportBusy(Exception):
    pass


def status():
    with _lock:
        return {**_state, "results": list(_state.get("results", []))}


def _update(**values):
    with _lock:
        _state.update(values)


def _record(result):
    with _lock:
        _state.setdefault("results", []).append(result)
        _state["done"] = _state.get("done", 0) + 1


async def discover(client, *, country, start, end, videogame_id="1386"):
    """Offline tournaments of the country with at least one singles event of the game."""
    tournaments = await seeding_startgg.paged(
        client,
        "seeding_country_tournaments",
        "tournaments",
        "nodes",
        {
            "country": country,
            "videogame": str(videogame_id),
            "after": int(start.timestamp()),
            "before": int(end.timestamp()),
        },
        per_page=20,
        connection_is_root=True,
    )
    return [
        dict(slug=t["slug"], name=t["name"], start_at=t.get("startAt"))
        for t in tournaments
        if not t.get("isOnline")
        and (t.get("countryCode") or "").upper() == country.upper()
        and any(seeding_startgg._is_offline_singles(e, videogame_id) for e in t.get("events") or [])
    ]


def _run(engine, token, actor, *, country=None, start=None, end=None, slugs=None):
    async def main():
        async with StartGGClient(token) as client:
            try:
                with Session(engine) as session, session.begin():
                    await sync_characters(client, session)
            except ImportFailure:
                pass  # Icons are cosmetic; never block the import.
            if slugs is None:
                found = await discover(client, country=country, start=start, end=end)
            else:
                found = [dict(slug=s, name=s, start_at=None) for s in slugs]
            found.sort(key=lambda t: t["start_at"] or 0)
            _update(status="importing", total=len(found), done=0)
            for item in found:
                _update(current=item["name"])
                try:
                    summary = await run_import(engine, client, item["slug"])
                    _record(
                        dict(
                            slug=item["slug"],
                            name=item["name"],
                            status="completed",
                            counts=summary["counts"],
                            conflicts=len(summary["conflicts"]),
                        )
                    )
                except ImportFailure as exc:
                    _record(
                        dict(slug=item["slug"], name=item["name"], status="failed", error=str(exc))
                    )

    try:
        with Session(engine) as session, session.begin():
            bootstrap(session)  # Idempotent: community, game and data source must exist.
        asyncio.run(main())
        _update(status="completed", current=None, finished_at=datetime.now(UTC).isoformat())
        from app.insights.engine import invalidate

        invalidate()  # Records and badges must see the new tournaments.
    except Exception as exc:
        code = str(exc) if isinstance(exc, ImportFailure) else type(exc).__name__
        log.error("Bulk import failed: %s", code)
        _update(status="failed", error=code[:80], current=None)


def tournament_slug(value):
    """Any start.gg tournament page (details, events, brackets) -> tournament slug."""
    value = value.strip()
    match = re.match(
        r"https://(www\.)?start\.gg/tournament/([A-Za-z0-9][A-Za-z0-9-]{0,149})", value
    )
    if match:
        return parse_slug(match.group(2))
    return parse_slug(value)


def start(engine, token, actor, *, country=None, start=None, end=None, urls=None, runner=None):
    if token is None or not token.get_secret_value().strip():
        raise ImportFailure("startgg_token_missing")
    slugs = None if urls is None else [tournament_slug(u) for u in urls]
    with _lock:
        if _state.get("status") in ("discovering", "importing"):
            raise ImportBusy
        _state.clear()
        _state.update(
            status="discovering",
            actor=actor,
            country=country,
            started_at=datetime.now(UTC).isoformat(),
            done=0,
            total=None,
            results=[],
        )
    kwargs = dict(country=country, start=start, end=end, slugs=slugs)
    if runner is not None:
        runner(engine, token, actor, **kwargs)
    else:
        threading.Thread(
            target=_run, args=(engine, token, actor), kwargs=kwargs, daemon=True, name="bulk-import"
        ).start()
