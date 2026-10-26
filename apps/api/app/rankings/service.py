"""Offline calculation and atomic, versioned publication. Never called by HTTP."""

import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.competitions.models import Event, Tournament
from app.rankings.glicko2 import ALGORITHM, Rating, inactive, update
from app.rankings.models import (
    RankingSnapshot, RatingCalculationRun, RatingPeriod, RatingPolicy, RatingPool, RatingSnapshot,
)
from app.rankings.policy import Policy, period_start, ranking_status, utc
from app.statistics.contracts import Filters
from app.statistics.repository import eligible_sets


class CalculationBusy(Exception):
    pass


def pool_inputs(session, pool):
    if pool.mode != "singles":
        raise ValueError("Doubles require a validated team rating policy; individual ratings unsupported")
    event_ids = {UUID(x) for x in pool.event_ids}
    valid = set(session.scalars(
        select(Event.id).join(Tournament).where(
            Event.id.in_(event_ids), Event.game_id == pool.game_id,
            Event.team_size == 1, Event.competition_type == 1,
            Tournament.community_id == pool.community_id, Tournament.published.is_(True),
        )
    ))
    if valid != event_ids:
        raise ValueError("Pool allowlist contains unpublished or incompatible events")
    universe = eligible_sets(session, Filters(game_id=pool.game_id, community_id=pool.community_id))
    rows = session.execute(select(universe).where(universe.c.event_id.in_(event_ids))).mappings()
    allowed = None if pool.player_ids is None else {UUID(x) for x in pool.player_ids}
    return [dict(r) for r in rows if allowed is None or
            set(r["players_a"] + r["players_b"]).issubset(allowed)]


def calculate(rows, policy, end):
    """Only populated periods plus final closed period; gaps advanced in O(1)."""
    end = period_start(end, policy)
    width = timedelta(days=policy.period_days)
    periods = defaultdict(list)
    for row in rows:
        if row["completed_at"] is not None and utc(row["completed_at"]) < end:
            periods[period_start(row["completed_at"], policy)].append(row)
    if not periods:
        return []
    periods[end - width]  # Materialize final inactivity/status view, never future/open sets.
    states, totals, last, previous = {}, Counter(), {}, {}
    result = []
    for start, encounters in sorted(periods.items()):
        matches = defaultdict(list)
        for row in sorted(encounters, key=lambda r: str(r["id"])):
            a, b = row["players_a"][0], row["players_b"][0]
            for player in (a, b):
                if player not in states:
                    states[player] = Rating(policy.initial_rating, policy.initial_rd, policy.initial_volatility)
                    previous[player] = start
                last[player] = max(last.get(player, utc(row["completed_at"])), utc(row["completed_at"]))
            matches[a].append((b, int(row["a_won"])))
            matches[b].append((a, int(not row["a_won"])))
        before = {
            player: inactive(state, (start - previous[player]) // width)
            for player, state in states.items()
        }
        after = {}
        for player in sorted(before, key=str):
            after[player] = update(before[player], [(before[op], score) for op, score in matches[player]],
                                   tau=policy.tau, epsilon=policy.epsilon,
                                   max_iterations=policy.max_iterations)
            totals[player] += len(matches[player])
            previous[player] = start + width
        states = after
        snapshots = [dict(player_id=p, rating=s.rating, rd=s.rd, volatility=s.volatility,
                          period_sets=len(matches[p]), cumulative_sets=totals[p],
                          last_activity=last[p], status=ranking_status(totals[p], last[p], start + width, policy))
                     for p, s in states.items()]
        positions = Counter()
        for row in sorted(snapshots, key=lambda r: (-r["rating"], str(r["player_id"]))):
            positions[row["status"]] += 1
            row["position"] = positions[row["status"]]
        result.append((start, start + width, snapshots))
    return result


def recalculate(engine, pool_id, *, as_of, dry_run=False, from_period=None, before_publish=None):
    """A requested suffix currently replays origin for exact correction propagation."""
    pool_id = UUID(str(pool_id))
    lock_key = int.from_bytes(hashlib.sha256(pool_id.bytes).digest()[:8], "big", signed=True)
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
        locked = conn.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": lock_key})
        conn.commit()
        if not locked:
            raise CalculationBusy("An incompatible calculation is running for this pool")
        run_id = uuid4()
        run_data = None
        try:
            with Session(bind=conn, expire_on_commit=False) as session:
                pool = session.get(RatingPool, pool_id)
                if pool is None:
                    raise ValueError("Unknown pool")
                record = session.get(RatingPolicy, pool.policy_id)
                policy = Policy.model_validate(record.parameters)
                end = period_start(as_of, policy)
                requested = utc(from_period) if from_period is not None else None
                if requested is not None and (period_start(requested, policy) != requested or requested >= end):
                    raise ValueError("from-period must be a closed period boundary before as-of")
                rows = pool_inputs(session, pool)
                dated = [r for r in rows if r["completed_at"] is not None and utc(r["completed_at"]) < end]
                payload = {
                    "algorithm": ALGORITHM, "parameters": policy.model_dump(mode="json"),
                    "policy_version": record.version, "policy_id": str(record.id),
                    "game": str(pool.game_id), "community": str(pool.community_id), "mode": pool.mode,
                    "events": sorted(pool.event_ids),
                    "players": sorted(pool.player_ids) if pool.player_ids is not None else None,
                    "end": end.isoformat(),
                    "undated": sorted(str(r["id"]) for r in rows if r["completed_at"] is None),
                    "sets": [
                        [str(r["id"]), utc(r["completed_at"]).isoformat(), str(r["players_a"][0]),
                         str(r["players_b"][0]), r["a_won"]]
                        for r in sorted(dated, key=lambda r: str(r["id"]))],
                }
                fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
                existing = session.scalar(select(RatingCalculationRun).where(
                    RatingCalculationRun.pool_id == pool_id, RatingCalculationRun.input_hash == fingerprint,
                    RatingCalculationRun.status == "COMPLETED"))
                if existing is not None:
                    if not dry_run:
                        pool.published_run_id = existing.id
                        session.commit()
                    return {"run_id": str(existing.id), "reused": True, "sets": existing.set_count,
                            "players": existing.player_count, "dry_run": dry_run}
                now = datetime.now(UTC)
                run_data = dict(id=run_id, pool_id=pool_id, policy_id=record.id,
                                policy_version=record.version, algorithm_version=ALGORITHM,
                                parameters=payload, status="RUNNING", started_at=now,
                                interval_start=min((period_start(r["completed_at"], policy) for r in dated), default=None),
                                interval_end=end, requested_from=requested,
                                excluded_undated=sum(r["completed_at"] is None for r in rows))
                computed = calculate(dated, policy, end)
                report = {"run_id": str(run_id), "reused": False, "sets": len(dated),
                          "players": len(computed[-1][2]) if computed else 0,
                          "excluded_undated": run_data["excluded_undated"], "dry_run": dry_run}
                if dry_run:
                    return report
                run = RatingCalculationRun(**run_data, input_hash=fingerprint,
                                           player_count=report["players"], set_count=len(dated))
                session.add(run)
                session.flush()
                for start, stop, snapshots in computed:
                    period = session.scalar(select(RatingPeriod).where(
                        RatingPeriod.pool_id == pool_id, RatingPeriod.starts_at == start,
                        RatingPeriod.ends_at == stop))
                    if period is None:
                        period = RatingPeriod(pool_id=pool_id, starts_at=start, ends_at=stop)
                        session.add(period)
                        session.flush()
                    for row in snapshots:
                        rating = RatingSnapshot(run_id=run_id, pool_id=pool_id, period_id=period.id,
                                                calculated_at=now, policy_version=record.version,
                                                **{k: v for k, v in row.items() if k not in {"status", "position"}})
                        session.add(rating)
                        session.flush()
                        session.add(RankingSnapshot(rating_snapshot_id=rating.id, run_id=run_id,
                                                    pool_id=pool_id, period_id=period.id,
                                                    status=row["status"], position=row["position"]))
                if before_publish:
                    before_publish(session)
                run.status, run.finished_at = "COMPLETED", datetime.now(UTC)
                pool.published_run_id = run_id
                session.commit()
                return report
        except Exception as exc:
            conn.rollback()
            if run_data is not None and not dry_run:
                with Session(bind=conn) as failure:
                    # Store error class only: database exceptions may contain private bind values.
                    failure.add(RatingCalculationRun(**{**run_data, "status": "FAILED"},
                                                     finished_at=datetime.now(UTC), error=type(exc).__name__))
                    failure.commit()
            raise
        finally:
            conn.rollback()
            conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key})
            conn.commit()
