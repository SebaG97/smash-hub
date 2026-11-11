"""The first superadministrator (ADR-021, docs/security/accounts.md).

    python -m app.cli.superadmin promote --username seba
    python -m app.cli.superadmin create --username seba --email seba@example.com

`promote` is preferred: the person signs up on the web first, so their password never
goes through a terminal. `create` asks for the password interactively (twice, hidden);
it is never accepted as an argument or an environment variable. Both refuse while an
active superadmin exists, unless `--additional` says that is intended (recovery); after
the first one, superadmins are named from the web. Every run is audited as "cli".
"""

import argparse
import getpass
import sys

from sqlalchemy import func, select

from app.auth import passwords, service
from app.auth.models import User
from app.core.config import get_settings
from app.database import models  # noqa: F401
from app.database.session import build_engine, session_factory


class Refused(Exception):
    pass


def active_superadmins(s):
    return s.scalar(
        select(func.count())
        .select_from(User)
        .where(User.role == "superadmin", User.disabled_at.is_(None))
    )


def _guard(s, additional):
    if active_superadmins(s) and not additional:
        raise Refused(
            "Ya hay un superadministrador activo. Nombrá a los siguientes desde la web "
            "(/admin/usuarios) o usá --additional si es una recuperación deliberada."
        )


def promote(s, username, *, additional=False):
    _guard(s, additional)
    user = s.scalar(
        select(User).where(User.username == service.normalize_username(username)).with_for_update()
    )
    if user is None:
        raise Refused("No existe esa cuenta. Registrala primero en la web.")
    if user.password_hash is None:
        raise Refused("Esa cuenta no puede ingresar con contraseña.")
    before = user.role
    user.role, user.disabled_at = "superadmin", None
    closed = service.revoke_all(s, user.id)
    service.audit(
        s,
        "role_changed",
        None,
        actor_name="cli",
        target=user,
        before=before,
        after="superadmin",
        closed_sessions=closed,
        additional=additional,
    )
    return user


def create(s, username, email, password, *, display_name=None, additional=False):
    _guard(s, additional)
    try:
        user = service.register(
            s, username=username, email=email, password=password, display_name=display_name
        )
    except service.AuthError as exc:
        raise Refused(str(exc)) from None
    user.role = "superadmin"
    service.audit(
        s,
        "role_changed",
        None,
        actor_name="cli",
        target=user,
        before="user",
        after="superadmin",
        additional=additional,
    )
    return user


def _ask_password(username, email):
    if not sys.stdin.isatty():
        raise Refused("La contraseña se pide de forma interactiva: ejecutá el comando en una TTY.")
    first = getpass.getpass("Contraseña nueva: ")
    reason = passwords.problem(first, username=username, email=email)
    if reason:
        raise Refused(reason)
    if getpass.getpass("Repetila: ") != first:
        raise Refused("Las contraseñas no coinciden.")
    return first


def main(argv=None):
    parser = argparse.ArgumentParser(description="Name the first Smash Hub superadministrator")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("promote", help="Promote an account already registered on the web")
    p.add_argument("--username", required=True)
    p.add_argument("--additional", action="store_true")
    c = sub.add_parser("create", help="Create the account here (asks for the password)")
    c.add_argument("--username", required=True)
    c.add_argument("--email", required=True)
    c.add_argument("--display-name")
    c.add_argument("--additional", action="store_true")
    args = parser.parse_args(argv)
    engine = build_engine(get_settings())
    try:
        with session_factory(engine).begin() as s:
            if args.command == "promote":
                user = promote(s, args.username, additional=args.additional)
            else:
                _guard(s, args.additional)
                password = _ask_password(
                    service.normalize_username(args.username), service.normalize_email(args.email)
                )
                user = create(
                    s,
                    args.username,
                    args.email,
                    password,
                    display_name=args.display_name,
                    additional=args.additional,
                )
        print(f"Listo: {user.username} es superadministrador. Ingresá en /ingresar.")
    except Refused as exc:
        print(f"No se hizo ningún cambio: {exc}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
