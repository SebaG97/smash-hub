from sqlalchemy import CheckConstraint, Column, DateTime, String, func

from app.database.base import Base


class TeamPrefix(Base):
    """Organizers' call on a start.gg prefix (Mission 22).

    Prefixes are free text typed at each registration, so jokes and insults show up too:
    a prefix without a row here is never shown. `team` prefixes get a team page, `alias`
    ones belong to another team's key (META and "Meta Gaming"), `shown` ones only appear
    next to the tag, and `hidden` ones never do.
    """

    __tablename__ = "team_prefixes"
    key = Column(String(80), primary_key=True)
    status = Column(String(10), nullable=False)
    name = Column(String(40), nullable=False)
    team = Column(String(80))
    actor = Column(String(60))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (
        CheckConstraint("status IN ('team','alias','shown','hidden')", name="status"),
        CheckConstraint("status <> 'alias' OR team IS NOT NULL", name="alias_team"),
    )
