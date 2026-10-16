import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.communities.models import Community
from app.competitions.models import (
    EntrantMember,
    Event,
    EventEntrant,
    Set,
    SetSide,
    Tournament,
    TournamentParticipant,
)
from app.games.models import Game
from app.integrations.models import DataSource, ExternalMapping, ImportJob
from app.integrations.startgg.classification import classify
from app.integrations.startgg.client import ImportFailure, parse_slug
from app.integrations.startgg.snapshot import Snapshot
from app.players.models import ExternalIdentity, Player, PlayerAlias


def now():
    return datetime.now(UTC)


def timestamp(value):
    return datetime.fromtimestamp(value, UTC) if value is not None else None


def digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def validate(payload):
    try:
        snapshot = Snapshot.model_validate(payload)
        snapshot.validate_complete()
        return snapshot
    except (ValidationError, ValueError, OverflowError):
        raise ImportFailure("invalid_provider_snapshot") from None


def normalized_result(result, entrants, event_sets=None):
    raw = result.model_dump()
    slots = []
    scores = []
    for slot in result.slots:
        score = (((slot.standing or {}).get("stats") or {}).get("score") or {}).get("value")
        # Float scores occur for non head-to-head games; do not round them.
        if score is not None and (isinstance(score, bool) or not isinstance(score, (int, float))):
            score = None
        scores.append(score)
        slots.append(
            {
                "entrant_id": entrants[slot.entrant.id].id if slot.entrant else None,
                "score": None,
                "is_winner": False,
            }
        )
    ids = [s.entrant.id for s in result.slots if s.entrant]
    winner = str(result.winnerId) if result.winnerId is not None else None
    status = "pending"
    if result.state == 3:
        status = "incomplete"
        if winner in ids:
            # DQ requires both the source label and its sentinel score.
            if len(ids) == 2 and -1 in scores and "DQ" in (result.displayScore or "").upper():
                status = "dq"
            elif len(ids) == 1 and "BYE" in (result.displayScore or "").upper():
                status = "bye"
            elif (
                len(ids) == 2
                and len(scores) == 2
                and all(type(s) is int and s >= 0 for s in scores)
            ):
                wi = next(
                    i for i, s in enumerate(result.slots) if s.entrant and s.entrant.id == winner
                )
                if scores[wi] > scores[1 - wi]:
                    status = "completed"
            for i, slot in enumerate(result.slots):
                slots[i]["is_winner"] = bool(slot.entrant and slot.entrant.id == winner)
                if (
                    slot.entrant
                    and status in {"completed", "incomplete"}
                    and type(scores[i]) is int
                    and scores[i] >= 0
                ):
                    slots[i]["score"] = scores[i]
    return {
        "status": status,
        "round_label": result.fullRoundText,
        "completed_at": timestamp(result.completedAt) if result.state == 3 else None,
        **classify(result, status, event_sets or {}),
        "source_result": raw,
    }, slots


class Persister:
    def __init__(self, session, source_id, community_id):
        self.s, self.source_id, self.community_id = session, source_id, community_id
        self.counts = Counter(created=0, updated=0, skipped=0)
        self.conflicts = []

    def conflict(self, code, external_id):
        self.conflicts.append({"code": code, "external_id": str(external_id)})

    def mapped(self, kind, external_id, model, values, payload):
        column = {
            "tournament": "tournament_id",
            "event": "event_id",
            "entrant": "entrant_id",
            "set": "set_id",
        }[kind]
        mapping = self.s.scalar(
            select(ExternalMapping).where(
                ExternalMapping.data_source_id == self.source_id,
                ExternalMapping.entity_type == kind,
                ExternalMapping.external_id == external_id,
            )
        )
        hashed = digest(payload)
        if mapping:
            row = self.s.get(model, getattr(mapping, column))
            if mapping.manual_locked or getattr(row, "manual_locked", False):
                if mapping.payload_hash != hashed:
                    self.conflict("manual_correction_preserved", external_id)
                    if kind == "set":
                        self.conflicts[-1]["proposed_result"] = payload
                self.counts["skipped"] += 1
                return row, False
            needs_normalization = kind == "set" and row.normalization_version != values.get(
                "normalization_version"
            )
            if mapping.payload_hash == hashed and not needs_normalization:
                self.counts["skipped"] += 1
                mapping.synced_at = now()
                return row, False
            for key, value in values.items():
                setattr(row, key, value)
            self.counts["updated"] += 1
        else:
            row = model(**values)
            self.s.add(row)
            self.s.flush()
            mapping = ExternalMapping(
                data_source_id=self.source_id,
                entity_type=kind,
                external_id=external_id,
                **{column: row.id},
            )
            self.s.add(mapping)
            self.counts["created"] += 1
        mapping.synced_at, mapping.payload_hash = now(), hashed
        return row, True

    def participant(self, tournament, person, observed_at):
        scoped = f"tournament:{tournament.id}:participant:{person.id}"
        participant = self.s.scalar(
            select(TournamentParticipant).where(TournamentParticipant.external_id == scoped)
        )
        identity = None
        external_id = f"player:{person.player.id}" if person.player else None
        if external_id:
            identity = self.s.scalar(
                select(ExternalIdentity).where(
                    ExternalIdentity.data_source_id == self.source_id,
                    ExternalIdentity.external_id == external_id,
                )
            )
        if participant and identity and participant.player_id != identity.player_id:
            self.conflict("identity_conflict", person.id)
            raise ImportFailure("identity_conflict")
        player = (
            self.s.get(Player, participant.player_id)
            if participant
            else (self.s.get(Player, identity.player_id) if identity else None)
        )
        if player is None:
            player = Player(tag=person.gamerTag)
            self.s.add(player)
            self.s.flush()
            self.counts["created"] += 1
        if external_id and not identity:
            other = self.s.scalar(
                select(ExternalIdentity).where(
                    ExternalIdentity.player_id == player.id,
                    ExternalIdentity.data_source_id == self.source_id,
                )
            )
            if other:
                self.conflict("identity_conflict", person.id)
                raise ImportFailure("identity_conflict")
            identity = ExternalIdentity(
                player_id=player.id,
                data_source_id=self.source_id,
                external_id=external_id,
                synced_at=now(),
            )
            self.s.add(identity)
        if identity:
            identity.synced_at = now()
        if participant is None:
            existing = self.s.scalar(
                select(TournamentParticipant).where(
                    TournamentParticipant.tournament_id == tournament.id,
                    TournamentParticipant.player_id == player.id,
                )
            )
            if existing:
                self.conflict("multiple_participants_same_identity", person.id)
                raise ImportFailure("identity_conflict")
            participant = TournamentParticipant(
                tournament_id=tournament.id,
                player_id=player.id,
                tag_snapshot=person.gamerTag,
                external_id=scoped,
            )
            self.s.add(participant)
            self.counts["created"] += 1
        elif participant.tag_snapshot != person.gamerTag:
            # First imported tournament tag is historical evidence, never silently rewritten.
            self.conflict("historical_tag_preserved", person.id)
            self.counts["skipped"] += 1
        else:
            self.counts["skipped"] += 1
        latest_observation = self.s.scalar(
            select(func.max(PlayerAlias.valid_from)).where(PlayerAlias.player_id == player.id)
        )
        if not player.manual_locked and (
            latest_observation is None or observed_at > latest_observation
        ):
            if player.tag != person.gamerTag:
                player.tag = person.gamerTag
                self.counts["updated"] += 1
        if not self.s.scalar(
            select(PlayerAlias.id).where(
                PlayerAlias.player_id == player.id, PlayerAlias.tag == person.gamerTag
            )
        ):
            self.s.add(
                PlayerAlias(player_id=player.id, tag=person.gamerTag, valid_from=observed_at)
            )
            self.counts["created"] += 1
        self.s.flush()
        return participant

    def persist(self, snapshot):
        t = snapshot.tournament
        tournament, _ = self.mapped(
            "tournament",
            t.id,
            Tournament,
            {
                "community_id": self.community_id,
                "slug": parse_slug(t.slug),
                "name": t.name,
                "starts_at": timestamp(t.startAt),
                "ends_at": timestamp(t.endAt),
                "status": {1: "CREATED", 2: "ACTIVE", 3: "COMPLETED"}.get(
                    t.state, str(t.state) if t.state is not None else None
                ),
                "location": {"city": t.city, "country_code": t.countryCode},
            },
            t.model_dump(),
        )
        if tournament.community_id != self.community_id:
            raise ImportFailure("tournament_community_conflict")
        people = {
            p.id: self.participant(tournament, p, timestamp(t.startAt) or now())
            for p in snapshot.participants
        }
        for e in snapshot.events:
            game_slug = (
                "super-smash-bros-ultimate"
                if e.videogame.id == "1386"
                else f"startgg-{e.videogame.id}"
            )
            game = self.s.scalar(select(Game).where(Game.slug == game_slug))
            if not game:
                game = Game(slug=game_slug, name=e.videogame.name)
                self.s.add(game)
                self.s.flush()
            event, _ = self.mapped(
                "event",
                e.id,
                Event,
                {
                    "tournament_id": tournament.id,
                    "game_id": game.id,
                    "slug": f"startgg-{e.id}",
                    "name": e.name,
                    "team_size": e.team_size(),
                    "competition_type": e.type,
                    "status": e.state,
                    "num_entrants": e.numEntrants,
                },
                e.model_dump(exclude={"entrants", "standings", "sets"}),
            )
            if event.tournament_id != tournament.id:
                raise ImportFailure("event_scope_conflict")
            placements = {
                s.entrant.id: s.placement for s in e.standings if s.entrant and s.isFinal is True
            }
            entrants = {}
            # Seeds may swap during corrections; clear unlocked seeds before assigning final state.
            for item in e.entrants:
                mapping = self.s.scalar(
                    select(ExternalMapping).where(
                        ExternalMapping.data_source_id == self.source_id,
                        ExternalMapping.entity_type == "entrant",
                        ExternalMapping.external_id == item.id,
                    )
                )
                if mapping and not mapping.manual_locked:
                    self.s.get(EventEntrant, mapping.entrant_id).seed = None
            self.s.flush()
            for item in e.entrants:
                entrant, changed = self.mapped(
                    "entrant",
                    item.id,
                    EventEntrant,
                    {
                        "event_id": event.id,
                        "tournament_id": tournament.id,
                        "name": item.name,
                        "seed": item.initialSeedNum,
                        "placement": placements.get(item.id),
                    },
                    {**item.model_dump(), "placement": placements.get(item.id)},
                )
                if entrant.event_id != event.id:
                    raise ImportFailure("entrant_scope_conflict")
                entrants[item.id] = entrant
                # Restore unchanged seed cleared above.
                mapping = self.s.scalar(
                    select(ExternalMapping).where(ExternalMapping.entrant_id == entrant.id)
                )
                if not mapping.manual_locked:
                    entrant.seed = item.initialSeedNum
                if changed:
                    self.s.execute(
                        delete(EntrantMember).where(EntrantMember.entrant_id == entrant.id)
                    )
                    for position, person in enumerate(item.participants, 1):
                        self.s.add(
                            EntrantMember(
                                entrant_id=entrant.id,
                                event_id=event.id,
                                tournament_id=tournament.id,
                                participant_id=people[person.id].id,
                                position=position,
                            )
                        )
            self.s.flush()
            event_sets = {result.id: result for result in e.sets}
            for result in e.sets:
                values, sides = normalized_result(result, entrants, event_sets)
                old_mapping = self.s.scalar(
                    select(ExternalMapping).where(
                        ExternalMapping.data_source_id == self.source_id,
                        ExternalMapping.entity_type == "set",
                        ExternalMapping.external_id == result.id,
                    )
                )
                old = self.s.get(Set, old_mapping.set_id) if old_mapping else None
                if (
                    old_mapping
                    and old_mapping.source_updated_at
                    and result.updatedAt is not None
                    and timestamp(result.updatedAt) < old_mapping.source_updated_at
                ):
                    self.conflict("stale_source_result", result.id)
                    self.counts["skipped"] += 1
                    continue
                previous = old.source_result if old else None
                classification_fields = (
                    "lifecycle_status",
                    "resolution",
                    "classification_reason",
                    "normalization_version",
                    "stats_eligible",
                    "ranking_eligible",
                    "round_number",
                )
                previous_classification = (
                    {k: getattr(old, k) for k in classification_fields} if old else None
                )
                replacement_classification = {k: values[k] for k in classification_fields}
                history = list(old.result_history or []) if old else []
                match, changed = self.mapped(
                    "set",
                    result.id,
                    Set,
                    {"event_id": event.id, **values},
                    {"source": result.model_dump(), "classification": replacement_classification},
                )
                if match.event_id != event.id:
                    raise ImportFailure("set_scope_conflict")
                if changed:
                    if previous is not None and (
                        previous != values["source_result"]
                        or previous_classification != replacement_classification
                    ):
                        history.append(
                            {
                                "observed_at": now().isoformat(),
                                "kind": "source_or_classification_change",
                                "previous": previous,
                                "replacement": values["source_result"],
                                "previous_classification": previous_classification,
                                "replacement_classification": replacement_classification,
                            }
                        )
                    match.result_history = history
                    existing_sides = self.s.scalars(
                        select(SetSide).where(SetSide.set_id == match.id).order_by(SetSide.side)
                    ).all()
                    original_sides = [
                        {k: getattr(side, k) for k in ("entrant_id", "score", "is_winner")}
                        for side in existing_sides
                    ]
                    # Enrich/reclassify without rewriting real results or side UUIDs.
                    if original_sides != sides:
                        self.s.execute(delete(SetSide).where(SetSide.set_id == match.id))
                        for side, side_values in enumerate(sides, 1):
                            self.s.add(
                                SetSide(
                                    set_id=match.id, event_id=event.id, side=side, **side_values
                                )
                            )
                    old_mapping = self.s.scalar(
                        select(ExternalMapping).where(ExternalMapping.set_id == match.id)
                    )
                    old_mapping.source_updated_at = timestamp(result.updatedAt)
        tournament.published, tournament.synced_at = True, now()
        self.s.flush()
        return {
            "tournament_id": str(tournament.id),
            "counts": dict(self.counts),
            "conflicts": self.conflicts,
        }


async def run_import(engine, client, value, *, community_slug="smash-paraguay", dry_run=False):
    slug = parse_slug(value)
    if dry_run:
        snapshot = validate(await client.download(slug))
        return {
            "preview": True,
            "name": snapshot.tournament.name,
            "events": len(snapshot.events),
            "participants": len(snapshot.participants),
            "entrants": sum(len(e.entrants) for e in snapshot.events),
            "sets": sum(len(e.sets) for e in snapshot.events),
        }
    # Hold one dedicated connection: the session lock survives job commits and rollback.
    with engine.connect() as conn:
        acquired = conn.scalar(
            text("SELECT pg_try_advisory_lock(hashtextextended(:key,0))"),
            {"key": "startgg:" + slug},
        )
        conn.commit()
        if not acquired:
            raise ImportFailure("tournament_import_already_running")
        provider_lock = conn.scalar(
            text("SELECT pg_try_advisory_lock(hashtextextended('startgg:provider',0))")
        )
        conn.commit()
        if not provider_lock:
            conn.execute(
                text("SELECT pg_advisory_unlock(hashtextextended(:key,0))"),
                {"key": "startgg:" + slug},
            )
            conn.commit()
            raise ImportFailure("startgg_import_busy")
        job_id, persister = None, None
        try:
            with Session(bind=conn, expire_on_commit=False) as s:
                with s.begin():
                    source = s.scalar(select(DataSource).where(DataSource.slug == "start-gg"))
                    community = s.scalar(select(Community).where(Community.slug == community_slug))
                    if not source or not community:
                        raise ImportFailure("bootstrap_or_community_missing")
                    source_id, community_id = source.id, community.id
                    job = ImportJob(data_source_id=source_id, idempotency_key=f"{slug}:{uuid4()}")
                    s.add(job)
                    job.status, job.started_at, job.finished_at = "running", now(), None
                    job.error_code, job.counts, job.conflicts = None, None, []
                    s.flush()
                    job_id = job.id
                snapshot = validate(await client.download(slug))
                with s.begin():
                    # Serialize identity reconciliation across different tournaments too.
                    s.execute(
                        text(
                            "SELECT pg_advisory_xact_lock(hashtextextended('startgg:identities',0))"
                        )
                    )
                    persister = Persister(s, source_id, community_id)
                    summary = persister.persist(snapshot)
                    job = s.get(ImportJob, job_id)
                    job.status, job.finished_at = "completed", now()
                    job.counts, job.conflicts = summary["counts"], summary["conflicts"]
                return summary
        except Exception as exc:
            code = (
                str(exc) if isinstance(exc, ImportFailure) else "import_validation_or_storage_error"
            )
            if job_id:
                with Session(bind=conn) as s, s.begin():
                    job = s.get(ImportJob, job_id)
                    job.status, job.finished_at, job.error_code = "failed", now(), code
                    job.counts = {"created": 0, "updated": 0, "skipped": 0}
                    job.conflicts = persister.conflicts if persister else []
            raise ImportFailure(code) from None
        finally:
            conn.rollback()
            conn.execute(text("SELECT pg_advisory_unlock(hashtextextended('startgg:provider',0))"))
            conn.execute(
                text("SELECT pg_advisory_unlock(hashtextextended(:key,0))"),
                {"key": "startgg:" + slug},
            )
            conn.commit()
