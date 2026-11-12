import unittest
from datetime import datetime, timedelta, timezone

from time_slot_grid_generator import Slot, generate_slots, parse_iso_datetime


UTC = timezone.utc


def dt(hour: int, minute: int = 0, tz=UTC) -> datetime:
    return datetime(2024, 1, 1, hour, minute, tzinfo=tz)


class ParseIsoDatetimeTests(unittest.TestCase):
    def test_parses_z_suffix_as_utc(self):
        self.assertEqual(parse_iso_datetime("2024-01-01T09:00:00Z"), dt(9))

    def test_parses_explicit_offset(self):
        value = parse_iso_datetime("2024-01-01T10:00:00+01:00")
        self.assertEqual(value, dt(9))
        self.assertEqual(value.tzinfo, UTC)

    def test_naive_string_is_treated_as_utc(self):
        self.assertEqual(parse_iso_datetime("2024-01-01T09:00:00"), dt(9))

    def test_non_string_raises_type_error(self):
        with self.assertRaises(TypeError):
            parse_iso_datetime(123)  # type: ignore[arg-type]


class GenerateSlotsTests(unittest.TestCase):
    def test_evenly_spaced_slots(self):
        slots = generate_slots(dt(9), dt(10), 30)
        self.assertEqual(len(slots), 2)
        self.assertEqual(slots[0], Slot(dt(9), dt(9, 30), 0))
        self.assertEqual(slots[1], Slot(dt(9, 30), dt(10), 1))

    def test_trailing_partial_interval_is_dropped(self):
        slots = generate_slots(dt(9), dt(10), 45)
        self.assertEqual(len(slots), 1)
        self.assertEqual(slots[0].start, dt(9))
        self.assertEqual(slots[0].end, dt(9, 45))

    def test_empty_when_interval_larger_than_range(self):
        self.assertEqual(generate_slots(dt(9), dt(9, 10), 30), [])

    def test_blackout_fully_covering_a_slot_skips_it(self):
        slots = generate_slots(
            dt(9), dt(11), 30, blackouts=[(dt(9, 30), dt(10))]
        )
        self.assertEqual([s.start for s in slots], [dt(9), dt(10), dt(10, 30)])

    def test_blackout_starting_inside_slot_skips_it(self):
        slots = generate_slots(
            dt(9), dt(11), 30, blackouts=[(dt(9, 45), dt(10, 15))]
        )
        self.assertEqual([s.start for s in slots], [dt(9), dt(10, 30)])

    def test_blackout_ending_inside_slot_skips_it(self):
        slots = generate_slots(
            dt(9), dt(11), 30, blackouts=[(dt(8, 45), dt(9, 15))]
        )
        self.assertEqual([s.start for s in slots], [dt(9, 30), dt(10), dt(10, 30)])

    def test_indices_are_contiguous_after_blackouts(self):
        slots = generate_slots(
            dt(9), dt(11), 30, blackouts=[(dt(9, 30), dt(10))]
        )
        self.assertEqual([s.index for s in slots], [0, 1, 2])

    def test_overlapping_blackouts_are_merged(self):
        slots = generate_slots(
            dt(9),
            dt(11),
            30,
            blackouts=[(dt(9, 15), dt(9, 45)), (dt(9, 30), dt(10, 15))],
        )
        self.assertEqual([s.start for s in slots], [dt(10, 30)])

    def test_adjacent_blackouts_do_not_merge_into_a_gap(self):
        slots = generate_slots(
            dt(9),
            dt(11),
            30,
            blackouts=[(dt(9), dt(9, 30)), (dt(9, 30), dt(10))],
        )
        self.assertEqual([s.start for s in slots], [dt(10), dt(10, 30)])

    def test_naive_start_raises(self):
        with self.assertRaises(ValueError):
            generate_slots(datetime(2024, 1, 1, 9), dt(10), 30)

    def test_end_before_start_raises(self):
        with self.assertRaises(ValueError):
            generate_slots(dt(10), dt(9), 30)

    def test_zero_interval_raises(self):
        with self.assertRaises(ValueError):
            generate_slots(dt(9), dt(10), 0)

    def test_bool_interval_raises(self):
        with self.assertRaises(TypeError):
            generate_slots(dt(9), dt(10), True)  # type: ignore[arg-type]

    def test_blackout_with_end_before_start_raises(self):
        with self.assertRaises(ValueError):
            generate_slots(dt(9), dt(10), 30, blackouts=[(dt(9, 30), dt(9))])

    def test_timezone_conversion_is_preserved(self):
        tz = timezone(timedelta(hours=2))
        start = datetime(2024, 1, 1, 10, tzinfo=tz)
        end = datetime(2024, 1, 1, 11, tzinfo=tz)
        slots = generate_slots(start, end, 30)
        self.assertEqual(slots[0].start, dt(8))
        self.assertEqual(slots[0].end, dt(8, 30))


if __name__ == "__main__":
    unittest.main()
