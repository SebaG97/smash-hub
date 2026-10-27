"""Character catalog and stock icons from start.gg (Mission 07)."""

import re

from sqlalchemy import select

from app.games.models import Character, Game

ICON_HOST = re.compile(r"^https://images\.start\.gg/")


async def sync_characters(client, session, *, videogame_id="1386"):
    """Upsert every character of the game with its stock icon. Returns how many changed."""
    data = await client.query("characters", {"id": str(videogame_id)})
    videogame = data.get("videogame") or {}
    slug = "super-smash-bros-ultimate" if str(videogame_id) == "1386" else f"startgg-{videogame_id}"
    game = session.scalar(select(Game).where(Game.slug == slug))
    if game is None:
        return 0
    existing = {
        c.slug: c for c in session.scalars(select(Character).where(Character.game_id == game.id))
    }
    changed = 0
    for item in videogame.get("characters") or []:
        icon = next(
            (
                i.get("url")
                for i in item.get("images") or []
                if i.get("type") == "stockIcon" and ICON_HOST.match(i.get("url") or "")
            ),
            None,
        )
        key = f"startgg-{item['id']}"
        row = existing.get(key)
        if row is None:
            session.add(
                Character(game_id=game.id, slug=key, name=str(item["name"])[:120], image_url=icon)
            )
            changed += 1
        elif row.image_url != icon or row.name != item["name"]:
            row.image_url, row.name = icon, str(item["name"])[:120]
            changed += 1
    session.flush()
    return changed
