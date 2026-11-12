"""Core time slot grid generation logic.

All datetimes are timezone-aware UTC. Naive datetimes are rejected to avoid
silent local-time interpretation. Blackout ranges are half-open [start, end)
so adjacent ranges do not overlap and a slot exactly at a blackout start is
skipped.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Slot:
    """A single generated time slot.

    ``start`` is the inclusive start instant and ``end`` is the exclusive end
    instant. ``index`` is the zero-based position in the generated sequence,
    counted after blackout filtering, so callers can label slots without
    recomputing.
    """

    start: datetime
    end: datetime
    index: int


def _ensure_aware(dt: datetime, name: str) -> datetime:
    """Return ``dt`` if it is timezone-aware, otherwise raise ValueError.

    Mixing naive and aware datetimes is a common source of off-by-one-hour
    bugs, so we refuse to guess a timezone.
    """
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return dt


def parse_iso_datetime(value: str) -> datetime:
    """Parse an ISO-8601 string into an aware UTC datetime.

    Accepts a trailing ``Z`` as UTC. A string without an offset is treated as
    UTC rather than local time; this keeps the library deterministic across
    machines.
    """
    if not isinstance(value, str):
        raise TypeError("value must be a string")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _normalize_blackouts(
    blackouts: Optional[Iterable[Tuple[datetime, datetime]]],
) -> List[Tuple[datetime, datetime]]:
    """Validate and sort blackout ranges.

    Sorting lets us merge overlapping ranges once, which keeps the per-slot
    check O(1) amortized for typical inputs and makes the half-open semantics
    obvious.
    """
    if blackouts is None:
        return []
    normalized: List[Tuple[datetime, datetime]] = []
    for i, (start, end) in enumerate(blackouts):
        start = _ensure_aware(start, f"blackout[{i}].start")
        end = _ensure_aware(end, f"blackout[{i}].end")
        if end <= start:
            raise ValueError(
                f"blackout[{i}] end must be strictly after start"
            )
        normalized.append((start, end))
    normalized.sort(key=lambda pair: pair[0])
    merged: List[Tuple[datetime, datetime]] = []
    for start, end in normalized:
        if merged and start <= merged[-1][1]:
            prev_start, prev_end = merged[-1]
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def _is_blacked_out(
    start: datetime,
    end: datetime,
    blackouts: Sequence[Tuple[datetime, datetime]],
) -> bool:
    """Return True if the half-open slot [start, end) touches any blackout.

    A slot is skipped when it overlaps a blackout at all, not only when it is
    fully contained; partial overlap would produce a slot that is partly
    unavailable, which is not useful for scheduling.
    """
    for b_start, b_end in blackouts:
        if start < b_end and b_start < end:
            return True
    return False


def generate_slots(
    start: datetime,
    end: datetime,
    interval_minutes: int,
    blackouts: Optional[Iterable[Tuple[datetime, datetime]]] = None,
) -> List[Slot]:
    """Generate evenly spaced slots in ``[start, end)``.

    Slots are produced at ``start``, ``start + interval``, ... while the slot
    end is less than or equal to ``end``. The last slot may end exactly at
    ``end``. Any slot that overlaps a blackout range is omitted.

    ``interval_minutes`` must be a positive integer. ``start`` must be before
    ``end``. Both bounds must be timezone-aware.
    """
    start = _ensure_aware(start, "start")
    end = _ensure_aware(end, "end")
    if end <= start:
        raise ValueError("end must be strictly after start")
    if not isinstance(interval_minutes, int) or isinstance(interval_minutes, bool):
        raise TypeError("interval_minutes must be an int")
    if interval_minutes <= 0:
        raise ValueError("interval_minutes must be positive")

    normalized_blackouts = _normalize_blackouts(blackouts)
    step = timedelta(minutes=interval_minutes)

    slots: List[Slot] = []
    cursor = start
    index = 0
    while cursor + step <= end:
        slot_end = cursor + step
        if not _is_blacked_out(cursor, slot_end, normalized_blackouts):
            slots.append(Slot(start=cursor, end=slot_end, index=index))
            index += 1
        cursor = slot_end
    return slots
