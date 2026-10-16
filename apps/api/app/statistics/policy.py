"""Consume 02.1 classification; never reclassify administrative results."""

from sqlalchemy import and_, or_, select

from app.competitions.models import Set
from app.integrations.startgg.classification import scoreless_statistics_evidence


def eligibility(session, scoped):
    # Exceptional legacy 'incomplete' results retain their imported classification.
    # Only this narrow subset needs source evidence, never the normal played universe.
    missing = session.execute(
        select(Set.id, Set.source_result).where(
            Set.event_id.in_(select(scoped.c.id)),
            Set.lifecycle_status == "completed",
            Set.resolution == "unresolved",
            Set.status == "incomplete",
            Set.classification_reason == "final_result_insufficient",
            Set.normalization_version >= 2,
            Set.manual_locked.is_(False),
        )
    ).all()
    verified = [id for id, source in missing if scoreless_statistics_evidence(source)]
    return and_(
        Set.manual_locked.is_(False),
        Set.lifecycle_status == "completed",
        or_(
            and_(Set.stats_eligible.is_(True), Set.resolution == "played"),
            Set.id.in_(verified),
        ),
    )
