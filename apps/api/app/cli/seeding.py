"""Administrative seeding CLI. The start.gg write (push) lives only here, never in HTTP.

python -m app.cli.seeding create --slug center-stage-2026 --event-slug tournament/x/event/y \
    --event-date 2026-11-14T00:00:00-03:00 --window-start 2025-11-14T00:00:00-03:00
python -m app.cli.seeding load-phase2 --slug center-stage-2026 --dir /seeding
python -m app.cli.seeding merge --slug center-stage-2026 --from 5363782 --to 5570394
python -m app.cli.seeding duplicate --slug center-stage-2026 --player 5509432 --keep 5570394
python -m app.cli.seeding override --slug center-stage-2026 --player 70916 --seed 1 --reason "..."
python -m app.cli.seeding recalculate --slug center-stage-2026
python -m app.cli.seeding push --slug center-stage-2026 [--phase-id 123] [--confirm]
"""

import argparse
import asyncio
import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database import models  # noqa: F401
from app.database.session import build_engine
from app.integrations.startgg.client import ImportFailure, StartGGClient
from app.seeding import service, startgg
from app.seeding.models import SeedingProject

ACTOR = "cli"
PHASE2_TZ = timezone(timedelta(hours=-3))  # Phase 2 CSV dates are local Asunción days


def engine_for(settings, *, write):
    if write and settings.environment == "production":
        raise ImportFailure("production_seeding_writes_disabled")
    return build_engine(settings.model_copy(update={"db_pool_size": 1, "db_max_overflow": 0}))


def _int(value):
    return int(value) if value not in ("", None) else None


def phase2_rows(directory):
    """Read the Phase 2 CSVs (center_stage_2026_*.csv) into dataset rows."""
    directory = Path(directory)

    def read(suffix):
        matches = sorted(directory.glob(f"*_{suffix}.csv"))
        if len(matches) != 1:
            raise ImportFailure(f"phase2_{suffix}_csv_not_found")
        with matches[0].open(encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))

    entrants = [
        dict(
            startgg_entrant_id=e["entrant_id"],
            startgg_player_id=e["player_id"],
            gamer_tag=e["gamer_tag"] or e["entrant_name"],
            prefix=e["prefix"] or None,
            profile_country=e["country"] or None,
        )
        for e in read("entrants")
    ]
    sets = [
        dict(
            startgg_set_id=s["set_id"],
            played_at=datetime.fromisoformat(s["date"]).replace(hour=12, tzinfo=PHASE2_TZ),
            startgg_event_id=s["event_id"],
            tournament_name=s["tournament"],
            tournament_slug=None,
            event_entrants=_int(s["event_entrants"]),
            online=s["online"] == "True",
            country=s["country"] or None,
            p1_player_id=s["p1_player_id"] or None,
            p1_tag=s["p1_tag"] or None,
            p1_placement=_int(s["p1_placement"]),
            p2_player_id=s["p2_player_id"] or None,
            p2_tag=s["p2_tag"] or None,
            p2_placement=_int(s["p2_placement"]),
            winner_player_id=s["winner_player_id"] or None,
            classification=s["classification"],
            counted=s["counted_in_stats"] == "True",
        )
        for s in read("sets")
    ]
    return entrants, sets


async def create(args, settings):
    async with StartGGClient(settings.startgg_api_token) as client:
        event = await startgg.fetch_event(client, args.event_slug)
    engine = engine_for(settings, write=True)
    with Session(engine) as session:
        project = SeedingProject(
            slug=args.slug,
            name=args.name or f"{event['tournament']['name']} · {event['name']}",
            startgg_event_id=str(event["id"]),
            startgg_event_slug=event["slug"],
            startgg_videogame_id=str(event["videogame"]["id"]),
            event_date=datetime.fromisoformat(args.event_date),
            window_start=datetime.fromisoformat(args.window_start),
            merges={},
            duplicates={},
        )
        session.add(project)
        session.flush()
        service.audit(session, project, "create", ACTOR, startgg_event_id=project.startgg_event_id)
        session.commit()
    return {
        "status": "created",
        "slug": args.slug,
        "startgg_event_id": str(event["id"]),
        "phases": [dict(id=p["id"], name=p["name"]) for p in event.get("phases") or []],
    }


def write(args, settings, operation):
    engine = engine_for(settings, write=True)
    try:
        with Session(engine) as session:
            project = service.project_by_slug(session, args.slug, lock=True)
            result = operation(session, project)
            session.commit()
            return result
    finally:
        engine.dispose()


def load_phase2(args, settings):
    entrants, sets = phase2_rows(args.dir)
    cutoff = datetime.fromisoformat(args.cutoff) if args.cutoff else None

    def operation(session, project):
        service.replace_dataset(session, project, entrants, sets, cutoff=cutoff)
        service.audit(
            session, project, "load_phase2", ACTOR, entrants=len(entrants), sets=len(sets)
        )
        session.flush()
        run = service.recalculate(session, project, ACTOR)
        return {
            "status": "loaded",
            "entrants": len(entrants),
            "sets": len(sets),
            "run_id": str(run.id),
        }

    return write(args, settings, operation)


def mapping_change(field, key, value):
    def operation(session, project):
        current = dict(getattr(project, field) or {})
        current[key] = value
        setattr(project, field, current)
        service.audit(session, project, field[:-1], ACTOR, **{key: value})
        return {"status": "saved", field: current, "note": "recalculate to apply"}

    return operation


async def push(args, settings):
    engine = engine_for(settings, write=False)
    try:
        with Session(engine) as session:
            project = service.project_by_slug(session, args.slug)
            _, rows = service.final_seeding(session, project)
            event_slug = project.startgg_event_slug
    finally:
        engine.dispose()
    if not rows:
        raise ImportFailure("no_seeding_calculated")
    async with StartGGClient(settings.startgg_api_token) as client:
        event = await startgg.fetch_event(client, event_slug)
        phases = sorted(event.get("phases") or [], key=lambda p: p.get("phaseOrder") or 0)
        phase = (
            next((p for p in phases if str(p["id"]) == str(args.phase_id)), None)
            if args.phase_id
            else (phases[0] if phases else None)
        )
        if phase is None:
            raise ImportFailure("startgg_phase_not_found")
        seeds = await startgg.fetch_phase_seeds(client, str(phase["id"]))
        by_player = {}
        for seed in seeds:
            parts = (seed.get("entrant") or {}).get("participants") or []
            if len(parts) == 1 and (parts[0].get("player") or {}).get("id"):
                by_player[str(parts[0]["player"]["id"])] = str(seed["id"])
        mapping, missing = [], []
        for r in rows:
            if r["player_id"] in by_player:
                mapping.append(
                    {"seedId": by_player.pop(r["player_id"]), "seedNum": len(mapping) + 1}
                )
            else:
                missing.append(r["gamer_tag"])
        # Entrants in start.gg but not in our seeding keep the bottom seeds in their current order.
        for seed in seeds:
            if str(seed["id"]) in by_player.values():
                mapping.append({"seedId": str(seed["id"]), "seedNum": len(mapping) + 1})
        report = {
            "phase": dict(id=phase["id"], name=phase["name"]),
            "seeds": len(mapping),
            "not_in_startgg": missing,
            "only_in_startgg": len(by_player),
            "top": [r["gamer_tag"] for r in rows[:8]],
        }
        if not args.confirm:
            return {
                "status": "dry_run",
                **report,
                "next": "repeat with --confirm to write to start.gg",
            }
        await startgg.update_phase_seeding(client, str(phase["id"]), mapping)
    engine = engine_for(settings, write=False)
    try:
        with Session(engine) as session:
            project = service.project_by_slug(session, args.slug)
            service.audit(
                session,
                project,
                "push_startgg",
                ACTOR,
                phase_id=str(phase["id"]),
                seeds=len(mapping),
            )
            session.commit()
    finally:
        engine.dispose()
    return {"status": "pushed", **report}


def main():
    parser = argparse.ArgumentParser(description="Seeding de eventos (Misión 05)")
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("create")
    c.add_argument("--slug", required=True)
    c.add_argument("--event-slug", required=True, help="tournament/<t>/event/<e>")
    c.add_argument("--event-date", required=True, help="ISO 8601 con zona horaria")
    c.add_argument("--window-start", required=True, help="ISO 8601 con zona horaria")
    c.add_argument("--name")
    lp = sub.add_parser("load-phase2")
    lp.add_argument("--slug", required=True)
    lp.add_argument("--dir", required=True)
    lp.add_argument("--cutoff", help="Fecha de corte de la descarga, ISO 8601")
    m = sub.add_parser("merge")
    m.add_argument("--slug", required=True)
    m.add_argument("--from", dest="source", required=True)
    m.add_argument("--to", required=True)
    d = sub.add_parser("duplicate")
    d.add_argument("--slug", required=True)
    d.add_argument("--player", required=True)
    d.add_argument("--keep", required=True)
    o = sub.add_parser("override")
    o.add_argument("--slug", required=True)
    o.add_argument("--player", required=True)
    o.add_argument("--seed", type=int, required=True)
    o.add_argument("--reason", required=True)
    r = sub.add_parser("recalculate")
    r.add_argument("--slug", required=True)
    p = sub.add_parser("push")
    p.add_argument("--slug", required=True)
    p.add_argument("--phase-id")
    p.add_argument(
        "--confirm", action="store_true", help="Escribir en start.gg (sin esto, solo simula)"
    )
    args = parser.parse_args()
    try:
        settings = get_settings()
        if args.command == "create":
            result = asyncio.run(create(args, settings))
        elif args.command == "load-phase2":
            result = load_phase2(args, settings)
        elif args.command == "merge":
            result = write(args, settings, mapping_change("merges", args.source, args.to))
        elif args.command == "duplicate":
            result = write(args, settings, mapping_change("duplicates", args.player, args.keep))
        elif args.command == "override":
            result = write(
                args,
                settings,
                lambda s, pr: (
                    service.set_override(s, pr, args.player, args.seed, args.reason, ACTOR)
                    or {"status": "moved"}
                ),
            )
        elif args.command == "recalculate":
            result = write(
                args,
                settings,
                lambda s, pr: {
                    "status": "recalculated",
                    "run_id": str(service.recalculate(s, pr, ACTOR).id),
                },
            )
        else:
            result = asyncio.run(push(args, settings))
    except ImportFailure as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}))
        return 1
    except (service.ProjectNotFound, service.InvalidRequest) as exc:
        print(
            json.dumps(
                {"status": "failed", "error": type(exc).__name__, "detail": str(exc)},
                ensure_ascii=False,
            )
        )
        return 1
    except ValidationError:
        print('{"status":"failed","error":"invalid_configuration"}')
        return 1
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
