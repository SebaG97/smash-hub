"""Linking Smash Hub accounts to competitive player records (ADR-021).

Two ways in: the person asks and an administrator approves after checking the account
is really theirs, or an administrator links them directly. Either way the administrator
writes down how they checked; a username that looks like a tag proves nothing. Nobody
approves or links their own account. Unlinking keeps the row (and never touches Prode
predictions or achievements, which belong to the account).
"""

import secrets

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.auth.models import User
from app.auth.service import AuthError, audit, now
from app.links.models import PlayerLink, PlayerLinkRequest
from app.players.models import ExternalIdentity, Player

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _code():
    return "SH-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))


def _clean(text, limit):
    return " ".join((text or "").split())[:limit]


def active_link(s, user_id):
    return s.scalar(
        select(PlayerLink).where(PlayerLink.user_id == user_id, PlayerLink.unlinked_at.is_(None))
    )


def active_player(s, user_id):
    row = s.execute(
        select(Player.id, Player.tag)
        .join(PlayerLink, PlayerLink.player_id == Player.id)
        .where(PlayerLink.user_id == user_id, PlayerLink.unlinked_at.is_(None))
    ).first()
    return dict(id=str(row.id), tag=row.tag) if row else None


def users_for_player(s, player_id):
    """Active accounts linked to a hub player (at most one, by the unique index)."""
    return list(
        s.scalars(
            select(PlayerLink.user_id)
            .join(User, User.id == PlayerLink.user_id)
            .where(
                PlayerLink.player_id == player_id,
                PlayerLink.unlinked_at.is_(None),
                User.disabled_at.is_(None),
            )
        )
    )


def startgg_ids_for_users(s, user_ids):
    """{account id: start.gg player id} through the active link and the hub's identity."""
    if not user_ids:
        return {}
    rows = s.execute(
        select(PlayerLink.user_id, ExternalIdentity.external_id)
        .join(ExternalIdentity, ExternalIdentity.player_id == PlayerLink.player_id)
        .where(
            PlayerLink.user_id.in_(list(user_ids)),
            PlayerLink.unlinked_at.is_(None),
            ExternalIdentity.external_id.like("player:%"),
        )
    ).all()
    return {user_id: external.removeprefix("player:") for user_id, external in rows}


def search_players(s, q, limit=20):
    q = _clean(q, 60)
    if len(q) < 2:
        return []
    pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    players = list(
        s.scalars(
            select(Player)
            .where(Player.tag.ilike(pattern, escape="\\"))
            .order_by(func.length(Player.tag), func.lower(Player.tag))
            .limit(limit)
        )
    )
    linked = set(
        s.scalars(
            select(PlayerLink.player_id).where(
                PlayerLink.player_id.in_([p.id for p in players]),
                PlayerLink.unlinked_at.is_(None),
            )
        )
    )
    return [dict(id=str(p.id), tag=p.tag, linked=p.id in linked) for p in players]


def _player(s, player_id):
    player = s.get(Player, player_id)
    if player is None:
        raise AuthError("No existe esa ficha de jugador.", 404)
    return player


def _not_self(staff, user_id):
    if staff.id == user_id:
        raise AuthError(
            "No podés aprobar ni vincular tu propia cuenta: pedíselo a otro administrador.", 403
        )


# Requests from the person.


def create_request(s, user, player_id, evidence):
    player = _player(s, player_id)
    evidence = _clean(evidence, 1000)
    if len(evidence) < 10:
        raise AuthError(
            "Contanos cómo podemos comprobar que sos ese jugador (por ejemplo, tu perfil de "
            "start.gg o tu usuario de Discord).",
            422,
        )
    if active_link(s, user.id) is not None:
        raise AuthError("Tu cuenta ya está vinculada a un jugador.", 409)
    if s.scalar(
        select(PlayerLink.id).where(
            PlayerLink.player_id == player.id, PlayerLink.unlinked_at.is_(None)
        )
    ):
        raise AuthError(
            "Esa ficha ya está vinculada a otra cuenta. Si es tuya, hablá con un administrador.",
            409,
        )
    pending = s.scalar(
        select(PlayerLinkRequest.id).where(
            PlayerLinkRequest.user_id == user.id, PlayerLinkRequest.status == "pending"
        )
    )
    if pending:
        raise AuthError("Ya tenés una solicitud pendiente. Cancelala para pedir otra.", 409)
    request = PlayerLinkRequest(
        user_id=user.id, player_id=player.id, code=_code(), evidence=evidence
    )
    s.add(request)
    try:
        s.flush()
    except IntegrityError:
        raise AuthError("Ya tenés una solicitud pendiente.", 409) from None
    audit(s, "link_requested", user, target=user, player_id=str(player.id), request=str(request.id))
    return request


def cancel_request(s, user, request_id):
    request = s.get(PlayerLinkRequest, request_id, with_for_update=True)
    if request is None or request.user_id != user.id:
        raise AuthError("No existe esa solicitud.", 404)
    if request.status != "pending":
        raise AuthError("Esa solicitud ya fue revisada.", 409)
    request.status = "cancelled"
    audit(s, "link_request_cancelled", user, target=user, request=str(request.id))
    return request


def describe_requests(s, requests, *, staff=False):
    players = {
        p.id: p.tag
        for p in s.scalars(select(Player).where(Player.id.in_({r.player_id for r in requests})))
    }
    users = (
        {u.id: u for u in s.scalars(select(User).where(User.id.in_({r.user_id for r in requests})))}
        if staff
        else {}
    )
    out = []
    for r in requests:
        row = dict(
            id=str(r.id),
            player=dict(id=str(r.player_id), tag=players.get(r.player_id, "?")),
            status=r.status,
            code=r.code,
            evidence=r.evidence,
            created_at=r.created_at.isoformat() if r.created_at else None,
            reviewed_at=r.reviewed_at.isoformat() if r.reviewed_at else None,
            review_note=r.review_note,
        )
        if staff:
            user = users.get(r.user_id)
            row["user"] = dict(
                id=str(r.user_id),
                username=user.username if user else "?",
                display_name=user.display_name if user else "?",
            )
            row["reviewed_by"] = r.reviewed_by_name
        out.append(row)
    return out


def requests_of(s, user):
    return list(
        s.scalars(
            select(PlayerLinkRequest)
            .where(PlayerLinkRequest.user_id == user.id)
            .order_by(PlayerLinkRequest.created_at.desc())
            .limit(20)
        )
    )


def requests_by_status(s, status):
    query = select(PlayerLinkRequest).order_by(PlayerLinkRequest.created_at.asc())
    if status:
        query = query.where(PlayerLinkRequest.status == status)
    return list(s.scalars(query.limit(200)))


# Administrators.


def _verification(text):
    text = _clean(text, 500)
    if len(text) < 10:
        raise AuthError(
            "Anotá cómo comprobaste que la cuenta es de ese jugador (al menos 10 caracteres).",
            422,
        )
    return text


def link(s, staff, user_id, player_id, verification, *, replace=False, reason=None, request=None):
    """Link an account to a player. A conflict needs `replace` and a reason, and every
    link it ends stays in history with that reason."""
    verification = _verification(verification)
    if request is None:
        _not_self(staff, user_id)
    user = s.get(User, user_id)
    if user is None:
        raise AuthError("No existe esa cuenta.", 404)
    if user.disabled_at is not None:
        raise AuthError("Esa cuenta está desactivada.", 409)
    player = _player(s, player_id)
    conflicts = list(
        s.scalars(
            select(PlayerLink)
            .where(
                PlayerLink.unlinked_at.is_(None),
                (PlayerLink.user_id == user.id) | (PlayerLink.player_id == player.id),
            )
            .with_for_update()
        )
    )
    if any(c.user_id == user.id and c.player_id == player.id for c in conflicts):
        raise AuthError("Esa cuenta ya está vinculada a ese jugador.", 409)
    if conflicts:
        reason = _clean(reason, 500)
        if not replace:
            raise AuthError(
                "La cuenta o la ficha ya tienen otra vinculación. Para reemplazarla, "
                "confirmá el reemplazo e indicá el motivo.",
                409,
            )
        if len(reason) < 10:
            raise AuthError("Indicá el motivo del reemplazo (al menos 10 caracteres).", 422)
        for c in conflicts:
            _end(s, staff, c, f"Reemplazada: {reason}")
            audit(
                s,
                "link_replaced",
                staff,
                link=str(c.id),
                user=str(c.user_id),
                player_id=str(c.player_id),
                reason=reason,
            )
        s.flush()
    row = PlayerLink(
        user_id=user.id,
        player_id=player.id,
        method="request" if request is not None else "admin",
        request_id=request.id if request is not None else None,
        verification=verification,
        linked_by=staff.id,
        linked_by_name=staff.username,
    )
    s.add(row)
    try:
        s.flush()
    except IntegrityError:
        raise AuthError(
            "Otra persona cambió esta vinculación recién. Recargá y probá.", 409
        ) from None
    audit(
        s,
        "link_created",
        staff,
        target=user,
        link=str(row.id),
        player_id=str(player.id),
        method=row.method,
        verification=verification,
    )
    return row


def _end(s, staff, row, reason):
    row.unlinked_at = now()
    row.unlinked_by = staff.id
    row.unlinked_by_name = staff.username
    row.unlink_reason = reason[:500]


def unlink(s, staff, link_id, reason):
    row = s.get(PlayerLink, link_id, with_for_update=True)
    if row is None or row.unlinked_at is not None:
        raise AuthError("No existe esa vinculación activa.", 404)
    reason = _clean(reason, 500)
    if len(reason) < 5:
        raise AuthError("Indicá el motivo de la desvinculación.", 422)
    _end(s, staff, row, reason)
    audit(
        s,
        "link_removed",
        staff,
        target=s.get(User, row.user_id),
        link=str(row.id),
        player_id=str(row.player_id),
        reason=reason,
    )
    return row


def approve(s, staff, request_id, verification):
    request = s.get(PlayerLinkRequest, request_id, with_for_update=True)
    if request is None:
        raise AuthError("No existe esa solicitud.", 404)
    if request.status != "pending":
        raise AuthError("Esa solicitud ya fue revisada.", 409)
    _not_self(staff, request.user_id)
    row = link(s, staff, request.user_id, request.player_id, verification, request=request)
    request.status = "approved"
    request.reviewed_by, request.reviewed_by_name = staff.id, staff.username
    request.reviewed_at, request.review_note = now(), row.verification
    return row


def reject(s, staff, request_id, note):
    request = s.get(PlayerLinkRequest, request_id, with_for_update=True)
    if request is None:
        raise AuthError("No existe esa solicitud.", 404)
    if request.status != "pending":
        raise AuthError("Esa solicitud ya fue revisada.", 409)
    _not_self(staff, request.user_id)
    note = _clean(note, 500)
    if len(note) < 5:
        raise AuthError("Contale a la persona por qué se rechaza.", 422)
    request.status = "rejected"
    request.reviewed_by, request.reviewed_by_name = staff.id, staff.username
    request.reviewed_at, request.review_note = now(), note
    audit(
        s,
        "link_request_rejected",
        staff,
        target=s.get(User, request.user_id),
        request=str(request.id),
        note=note,
    )
    return request


def active_links(s, q=None, limit=100):
    query = (
        select(PlayerLink, User, Player.tag)
        .join(User, User.id == PlayerLink.user_id)
        .join(Player, Player.id == PlayerLink.player_id)
        .where(PlayerLink.unlinked_at.is_(None))
        .order_by(PlayerLink.created_at.desc())
        .limit(limit)
    )
    q = _clean(q, 60).lower()
    if q:
        pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.where(
            User.username.ilike(pattern, escape="\\") | Player.tag.ilike(pattern, escape="\\")
        )
    return [
        dict(
            id=str(link.id),
            user=dict(id=str(user.id), username=user.username, display_name=user.display_name),
            player=dict(id=str(link.player_id), tag=tag),
            method=link.method,
            verification=link.verification,
            linked_by=link.linked_by_name,
            linked_at=link.created_at.isoformat() if link.created_at else None,
        )
        for link, user, tag in s.execute(query).all()
    ]
