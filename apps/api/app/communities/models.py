from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    Uuid,
)

from app.database.base import Base, Record


class Country(Record, Base):
    __tablename__ = "countries"
    iso_code = Column(String(2), nullable=False, unique=True)
    name = Column(String(120), nullable=False)
    __table_args__ = (CheckConstraint("iso_code ~ '^[A-Z]{2}$'", name="iso_code"),)


class Region(Record, Base):
    __tablename__ = "regions"
    country_id = Column(Uuid, ForeignKey("countries.id"), nullable=False, index=True)
    code = Column(String(50), nullable=False)
    name = Column(String(120), nullable=False)
    __table_args__ = (UniqueConstraint("country_id", "code"), UniqueConstraint("id", "country_id"))


class Community(Record, Base):
    __tablename__ = "communities"
    slug = Column(String(100), nullable=False, unique=True)
    name = Column(String(160), nullable=False)
    country_id = Column(Uuid, ForeignKey("countries.id"), index=True)
    region_id = Column(Uuid, index=True)
    __table_args__ = (
        ForeignKeyConstraint(["region_id", "country_id"], ["regions.id", "regions.country_id"]),
        CheckConstraint("region_id IS NULL OR country_id IS NOT NULL", name="region_country"),
    )


class CommunityGame(Record, Base):
    __tablename__ = "community_games"
    community_id = Column(Uuid, ForeignKey("communities.id"), nullable=False, index=True)
    game_id = Column(Uuid, ForeignKey("games.id"), nullable=False, index=True)
    __table_args__ = (UniqueConstraint("community_id", "game_id"),)
