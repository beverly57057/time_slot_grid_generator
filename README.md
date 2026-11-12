# time_slot_grid_generator

Generates evenly spaced datetime slots between two bounds at a fixed minute interval, skipping any slot that overlaps a blackout range.

```python
from datetime import datetime, timezone
from time_slot_grid_generator import generate_slots, parse_iso_datetime

start = parse_iso_datetime("2024-01-01T09:00:00Z")
end = parse_iso_datetime("2024-01-01T12:00:00Z")
blackouts = [(parse_iso_datetime("2024-01-01T10:00:00Z"),
              parse_iso_datetime("2024-01-01T11:00:00Z"))]

slots = generate_slots(start, end, 30, blackouts=blackouts)
for slot in slots:
    print(slot.index, slot.start.isoformat(), "->", slot.end.isoformat())
```

Output:

```
0 2024-01-01T09:00:00+00:00 -> 2024-01-01T09:30:00+00:00
1 2024-01-01T09:30:00+00:00 -> 2024-01-01T10:00:00+00:00
2 2024-01-01T11:00:00+00:00 -> 2024-01-01T11:30:00+00:00
3 2024-01-01T11:30:00+00:00 -> 2024-01-01T12:00:00+00:00
```

## Why this exists

Scheduling code often needs a clean list of candidate start times, but real calendars have busy blocks. Doing this with a loop over `timedelta` is easy to get subtly wrong: naive datetimes, partial trailing intervals, and blackout ranges that only partly overlap a slot all produce off-by-one bugs. This library makes the rules explicit and testable: slots are half-open `[start, end)`, blackouts are half-open `[start, end)`, and any slot that overlaps a blackout is skipped. The trade-off is that we do not try to clip or split slots around a blackout; a partly unavailable slot is dropped whole, because a scheduler usually wants whole candidate slots rather than fragments.

## API

- `Slot(start, end, index)` — frozen dataclass. `start` is inclusive, `end` is exclusive, `index` is the zero-based position after blackout filtering.
- `generate_slots(start, end, interval_minutes, blackouts=None) -> list[Slot]` — both bounds must be timezone-aware. `interval_minutes` must be a positive `int`. `blackouts` is an iterable of `(start, end)` aware datetime pairs.
- `parse_iso_datetime(value) -> datetime` — parses an ISO-8601 string into an aware UTC datetime. A trailing `Z` is accepted, and a string with no offset is treated as UTC rather than local time.

## Edge cases

All datetimes are timezone-aware. Passing a naive datetime raises `ValueError`; the library will not guess a timezone. The last slot may end exactly at `end`, but a partial trailing interval is dropped. Blackouts that overlap each other are merged, and adjacent blackouts are not merged, so a slot starting exactly at the end of one blackout and the start of the next is still generated.
