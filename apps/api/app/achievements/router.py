"""Achievements HTTP (SH-ACH-01): public catalog and profiles, the owner's showcase and
visibility, and the organizers' minimal panel. Reading never evaluates: it reads rows."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.achievements import catalog, runner, service
from app.auth.models import User
from app.auth.service import MaybeUser, Member, SignedUser, Superadmin
from app.core.admin import Admin
from app.insights import engine as insights
from app.players.models import Player
from app.players.summary import ranking_place

router = APIRouter(prefix="/api/v1/achievements", tags=["achievements"])
AchievementId = Annotated[str, Path(pattern=r"^[a-z0-9_]{1,40}$")]
RARITY_ORDER = {"legendario": 0, "epico": 1, "raro": 2, "comun": 3}


class ShowcaseItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["player", "prode"]
    achievement_id: str = Field(pattern=r"^[a-z0-9_]{1,40}$")


class Showcase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ShowcaseItem] = Field(default_factory=list, max_length=3)


class Visibility(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["player", "prode"]
    achievement_id: str = Field(pattern=r"^[a-z0-9_]{1,40}$")
    hidden: bool


class Subject(BaseModel):
    model_config = ConfigDict(extra="forbid")
    startgg_player_id: str = Field(pattern=r"^\d{1,20}$")
    consent: bool
    active: bool


class Grant(BaseModel):
    model_config = ConfigDict(extra="forbid")
    player_id: UUID
    achievement_id: str = Field(pattern=r"^[a-z0-9_]{1,40}$")
    reason: str = Field(min_length=5, max_length=500)


class Revoke(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=5, max_length=200)


def _session(request):
    return Session(request.app.state.engine)


def _fail(exc: service.AchievementError):
    raise HTTPException(exc.status, str(exc)) from None


def _owned(s, user):
    """{(source, id)} the reader holds, to reveal their secret achievements."""
    if user is None:
        return set()
    owned = {("prode", r.kind) for r, _, _ in service.prode_awards(s, user.id, include_hidden=True)}
    player = service.linked_player(s, user.id)
    if player:
        owned |= {
            ("player", r.achievement_id)
            for r in service.player_awards(s, player, include_hidden=True)
        }
    return owned


def _entry(entry, stats, gates, owned):
    view = catalog.view(entry, active_collections=gates)
    view["stats"] = service.stat_view(entry, stats.get(entry.id))
    view["mine"] = (entry.scope, entry.id) in owned
    if entry.secret and not view["mine"]:
        view.update(
            name="???",
            description="Logro secreto. Se revela al conseguirlo.",
            condition=None,
            revealed=False,
        )
    else:
        view["revealed"] = True
    return view


@router.get("/catalog")
def catalog_view(request: Request, user: MaybeUser):
    """Every achievement with its rarity, availability and statistics."""
    with _session(request) as s:
        gates = set(service.active_subjects(s))
        stats = service.stats_by_id(s)
        owned = _owned(s, user)
        progress, collections = service.collection_progress({i for _, i in owned}, gates)
        return dict(
            categories=catalog.CATEGORIES,
            rarities=catalog.RARITIES,
            universes=catalog.UNIVERSES,
            collections=collections,
            progress=progress if user else None,
            achievements=[_entry(a, stats, gates, owned) for a in catalog.ACHIEVEMENTS],
        )


@router.get("/me")
def mine(request: Request, user: Member):
    """Everything the account holds (hidden ones too), to manage showcase and visibility."""
    with _session(request) as s:
        player = service.linked_player(s, user.id)
        rows = service.player_awards(s, player, include_hidden=True) if player else []
        tags = service.tags_of(s, [r.opponent_player_id for r in rows])
        return dict(
            player_id=str(player) if player else None,
            achievements=[service.award_view(r, tags) for r in rows],
            prode=[
                service.prode_award_view(r, c, slug)
                for r, c, slug in service.prode_awards(s, user.id, include_hidden=True)
            ],
            showcase=service.showcase_of(s, user.id),
        )


@router.put("/me/showcase")
def set_showcase(request: Request, body: Showcase, user: SignedUser):
    with _session(request) as s, s.begin():
        try:
            items = service.set_showcase(s, user, [i.model_dump() for i in body.items])
        except service.AchievementError as exc:
            _fail(exc)
        return dict(showcase=items)


@router.put("/me/visibility")
def set_visibility(request: Request, body: Visibility, user: SignedUser):
    with _session(request) as s, s.begin():
        try:
            n = service.set_hidden(s, user, body.source, body.achievement_id, body.hidden)
        except service.AchievementError as exc:
            _fail(exc)
    runner.mark_dirty("visibility")  # first holders shown in statistics
    return dict(updated=n, hidden=body.hidden)


@router.get("/admin/status")
def admin_status(request: Request, actor: Admin):
    with _session(request) as s:
        return service.status(s, request.app.state.settings)


@router.post("/admin/recalculate", status_code=202)
def recalculate(request: Request, actor: Admin):
    started = runner.start(request.app.state.engine, "manual", actor)
    if not started:
        raise HTTPException(409, "Ya hay un recálculo en curso.")
    return dict(started=True)


@router.put("/admin/subjects/{key}")
def set_subject(
    request: Request,
    key: Annotated[str, Path(pattern=r"^[a-z]{1,20}$")],
    body: Subject,
    actor: Superadmin,
):
    with _session(request) as s, s.begin():
        try:
            service.set_subject(
                s,
                key,
                body.startgg_player_id,
                consent=body.consent,
                active=body.active,
                actor=actor.username,
            )
        except service.AchievementError as exc:
            _fail(exc)
    runner.mark_dirty("subject")
    with _session(request) as s:
        return dict(subjects=service.subjects_view(s))


@router.get("/admin/grants")
def grants(request: Request, actor: Admin):
    with _session(request) as s:
        return dict(
            grants=service.manual_grants(s),
            manual=[catalog.view(a) for a in catalog.ACHIEVEMENTS if a.status == "manual"],
        )


@router.post("/admin/grants", status_code=201)
def grant(request: Request, body: Grant, actor: Admin):
    with _session(request) as s, s.begin():
        try:
            row = service.grant(s, body.player_id, body.achievement_id, body.reason, actor)
        except service.AchievementError as exc:
            _fail(exc)
        award_id = str(row.id)
    runner.mark_dirty("grant")
    return dict(id=award_id)


@router.post("/admin/grants/{award_id}/revoke")
def revoke(request: Request, award_id: UUID, body: Revoke, actor: Admin):
    with _session(request) as s, s.begin():
        try:
            service.revoke(s, award_id, body.reason, actor)
        except service.AchievementError as exc:
            _fail(exc)
    runner.mark_dirty("revoke")
    return dict(revoked=True)


def _states(s, player_id):
    """Dynamic states (Líder, Nuevo, Especialista, Camaleón), computed live as before."""
    data = insights.cached(s)
    place = (ranking_place(s, player_id) or {}).get("place")
    states = {a.id for a in catalog.ACHIEVEMENTS if a.kind == "state"}
    return [
        dict(achievement_id=b["id"], name=b["name"], detail=b["why"])
        for b in insights.player_insights(data, player_id, place)["badges"]
        if b["id"] in states
    ]


def _showcase(s, user_id, views, stats):
    """The owner's three, else the three rarest (marked automatic)."""
    by_key = {(v["source"], v["achievement_id"]): v for v in views}
    if user_id:
        chosen = [
            by_key[(i["source"], i["achievement_id"])]
            for i in service.showcase_of(s, user_id)
            if (i["source"], i["achievement_id"]) in by_key
        ]
        if chosen:
            return dict(automatic=False, items=chosen)

    def rarest(v):
        stat = stats.get(v["achievement_id"])
        share = stat.holders / stat.universe if stat and stat.universe else 1
        return (RARITY_ORDER.get(v["rarity"], 9), share)

    unique = {}
    for v in sorted(views, key=rarest):
        unique.setdefault(v["achievement_id"], v)
    return dict(automatic=True, items=list(unique.values())[:3])


def _profile(s, player_id, user_id):
    stats = service.stats_by_id(s)
    gates = set(service.active_subjects(s))
    rows = service.player_awards(s, player_id) if player_id else []
    tags = service.tags_of(s, [r.opponent_player_id for r in rows])
    views = [service.award_view(r, tags) for r in rows]
    prode = (
        [service.prode_award_view(r, c, slug) for r, c, slug in service.prode_awards(s, user_id)]
        if user_id
        else []
    )
    owned = {v["achievement_id"] for v in views + prode}
    progress, collections = service.collection_progress(owned, gates)
    return dict(
        player_id=str(player_id) if player_id else None,
        user_id=str(user_id) if user_id else None,
        showcase=_showcase(s, user_id, views + prode, stats),
        achievements=views,
        prode=prode,
        progress=progress,
        collections=collections,
    )


@router.get("/players/{player_id}")
def player_profile(request: Request, player_id: UUID):
    with _session(request) as s:
        player = s.get(Player, player_id)
        if player is None:
            raise HTTPException(404, "No existe ese jugador.")
        user_id = service.linked_user(s, player_id)
        out = _profile(s, player_id, user_id)
        out["tag"] = player.tag
        out["states"] = _states(s, player_id)
        return out


@router.get("/users/{user_id}")
def user_profile(request: Request, user_id: UUID):
    with _session(request) as s:
        user = s.get(User, user_id)
        if user is None or user.disabled_at is not None:
            raise HTTPException(404, "No existe esa cuenta.")
        out = _profile(s, service.linked_player(s, user_id), user_id)
        out["name"] = user.display_name
        return out


@router.get("/{achievement_id}")
def detail(request: Request, achievement_id: AchievementId, user: MaybeUser):
    entry = catalog.get(achievement_id)
    if entry is None:
        raise HTTPException(404, "No existe ese logro.")
    with _session(request) as s:
        gates = set(service.active_subjects(s))
        stats = service.stats_by_id(s)
        owned = _owned(s, user)
        view = _entry(entry, stats, gates, owned)
        recent, mine = [], []
        if view["revealed"]:
            recent = service.recent_holders(s, entry)
            if user is not None and view["mine"]:
                mine = service.my_awards(s, user.id, entry)
        view["recent"] = recent
        view["my_awards"] = mine
        return view
