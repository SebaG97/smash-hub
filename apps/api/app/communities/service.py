from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.communities.models import Community, CommunityGame, Country
from app.games.models import Game
from app.integrations.models import DataSource


def ensure(session: Session, model, key: dict, **values):
    stmt = insert(model).values(**key, **values)
    return session.execute(
        stmt.on_conflict_do_update(index_elements=list(key), set_=values or key).returning(model.id)
    ).scalar_one()


def bootstrap(session: Session) -> dict:
    country = ensure(session, Country, {"iso_code": "PY"}, name="Paraguay")
    community = ensure(
        session, Community, {"slug": "smash-paraguay"}, name="Smash Paraguay", country_id=country
    )
    game = ensure(
        session, Game, {"slug": "super-smash-bros-ultimate"}, name="Super Smash Bros. Ultimate"
    )
    source = ensure(
        session, DataSource, {"slug": "start-gg"}, name="start.gg", base_url="https://www.start.gg"
    )
    ensure(session, CommunityGame, {"community_id": community, "game_id": game})
    return {"country": country, "community": community, "game": game, "source": source}
