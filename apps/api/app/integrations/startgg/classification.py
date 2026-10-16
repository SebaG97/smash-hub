"""Separate observed state, resolution and eligibility without inventing results."""

NORMALIZATION_VERSION = 2


def score_values(result):
    return [
        (((slot.standing or {}).get("stats") or {}).get("score") or {}).get("value")
        for slot in result.slots
    ]


def unused_reset(result, event_sets):
    """Evidence: invalid, unstarted DE successor of both outcomes of a resolved final.

    No event/tournament completion or name alone can classify a reset as unused.
    """
    if (
        result.state != 5
        or result.winnerId is not None
        or result.completedAt is not None
        or result.startedAt is not None
        or any(v is not None for v in score_values(result))
        or result.hasPlaceholder is True
        or len(result.slots) != 2
    ):
        return False
    group = result.phaseGroup or {}
    if not group.get("id") or group.get("bracketType") != "DOUBLE_ELIMINATION":
        return False
    a, b = result.slots
    if (
        a.prereqType != "set"
        or b.prereqType != "set"
        or not a.prereqId
        or a.prereqId != b.prereqId
        or {a.prereqPlacement, b.prereqPlacement} != {1, 2}
    ):
        return False
    parent = event_sets.get(a.prereqId)
    if not parent or parent.state != 3 or parent.winnerId is None:
        return False
    if (
        parent.round is None
        or parent.round <= 0
        or result.round not in {parent.round, parent.round + 1}
        or str((parent.phaseGroup or {}).get("id")) != str(group.get("id"))
    ):
        return False
    opponents = {slot.entrant.id for slot in parent.slots if slot.entrant}
    return len(opponents) == 2 and str(parent.winnerId) in opponents


def classify(result, legacy_status, event_sets):
    lifecycle = {
        1: "pending",
        2: "in_progress",
        3: "completed",
        4: "pending",
        6: "pending",
        7: "pending",
    }.get(result.state, "unknown")
    resolution, reason = "unresolved", "awaiting_result"
    real = [slot for slot in result.slots if slot.entrant]
    no_result = (
        result.winnerId is None
        and result.completedAt is None
        and result.startedAt is None
        and all(v is None for v in score_values(result))
    )
    if unused_reset(result, event_sets):
        lifecycle, resolution, reason = (
            "not_played",
            "conditional_unused",
            "invalid_double_elimination_reset",
        )
    elif result.hasPlaceholder is True:
        resolution, reason = "placeholder", "provider_placeholder"
        if result.state != 3:
            lifecycle = "not_played"
    elif result.state != 3 and no_result and len(real) < 2:
        lifecycle, resolution = "not_played", "placeholder"
        reason = (
            "empty_bye_slots"
            if result.slots and all(s.prereqType == "bye" for s in result.slots)
            else "opponents_not_assigned"
        )
    elif result.state == 3:
        resolution = {"completed": "played", "dq": "dq", "bye": "bye"}.get(
            legacy_status, "unresolved"
        )
        reason = {
            "played": "final_two_opponents_valid_scores",
            "dq": "explicit_dq_label_and_score",
            "bye": "explicit_bye_with_winner",
        }.get(resolution, "final_result_insufficient")
    elif lifecycle == "unknown":
        reason = "unknown_or_invalid_source_state"
    stats = lifecycle == "completed" and resolution == "played" and legacy_status == "completed"
    return {
        "lifecycle_status": lifecycle,
        "resolution": resolution,
        "classification_reason": reason,
        "normalization_version": NORMALIZATION_VERSION,
        "round_number": result.round,
        "stats_eligible": stats,
        "ranking_eligible": stats and result.completedAt is not None,
    }
