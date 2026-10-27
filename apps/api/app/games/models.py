from sqlalchemy import Column, ForeignKey, String, UniqueConstraint, Uuid

from app.database.base import Base, Record


class Game(Record, Base):
    __tablename__ = "games"
    slug = Column(String(100), nullable=False, unique=True)
    name = Column(String(160), nullable=False)


class Character(Record, Base):
    __tablename__ = "characters"
    game_id = Column(Uuid, ForeignKey("games.id"), nullable=False, index=True)
    slug = Column(String(100), nullable=False)
    name = Column(String(120), nullable=False)
    # Stock icon from start.gg, shown next to player names.
    image_url = Column(String(400))
    __table_args__ = (UniqueConstraint("game_id", "slug"),)
