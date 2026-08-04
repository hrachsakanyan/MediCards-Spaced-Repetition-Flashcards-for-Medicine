"""Tests for the Leitner scheduling logic."""

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import scheduler

TODAY = date(2026, 8, 2)


class BoxArithmeticTests(unittest.TestCase):
    def test_promote_moves_one_box_up(self):
        self.assertEqual(scheduler.promote(1), 2)
        self.assertEqual(scheduler.promote(4), 5)

    def test_promote_stops_at_the_last_box(self):
        self.assertEqual(scheduler.promote(5), 5)

    def test_demote_always_returns_to_box_one(self):
        for box in range(1, 6):
            self.assertEqual(scheduler.demote(box), 1)

    def test_clamp_box_handles_out_of_range_values(self):
        self.assertEqual(scheduler.clamp_box(0), 1)
        self.assertEqual(scheduler.clamp_box(99), 5)

    def test_intervals_grow_with_the_box_number(self):
        intervals = [scheduler.interval_for(box) for box in range(1, 6)]
        self.assertEqual(intervals, sorted(intervals))
        self.assertEqual(intervals[0], 1)

    def test_next_review_adds_the_box_interval(self):
        self.assertEqual(scheduler.next_review(3, TODAY), TODAY + timedelta(days=4))


class ApplyReviewTests(unittest.TestCase):
    def test_first_correct_answer_creates_a_box_two_card(self):
        state = scheduler.apply_review(None, True, TODAY)
        self.assertEqual(state["box"], 2)
        self.assertEqual(state["due"], scheduler.to_iso(TODAY + timedelta(days=2)))
        self.assertEqual((state["correct"], state["incorrect"], state["reviews"]), (1, 0, 1))
        self.assertEqual(state["last_reviewed"], scheduler.to_iso(TODAY))

    def test_wrong_answer_sends_a_high_box_card_back_to_box_one(self):
        state = {"box": 5, "due": "2026-09-01", "correct": 9, "incorrect": 0, "reviews": 9,
                 "last_reviewed": "2026-08-01"}
        updated = scheduler.apply_review(state, False, TODAY)
        self.assertEqual(updated["box"], 1)
        self.assertEqual(updated["due"], scheduler.to_iso(TODAY + timedelta(days=1)))
        self.assertEqual(updated["incorrect"], 1)
        self.assertEqual(updated["correct"], 9)

    def test_apply_review_does_not_mutate_the_original_state(self):
        state = scheduler.new_state(TODAY)
        scheduler.apply_review(state, True, TODAY)
        self.assertEqual(state["box"], 1)
        self.assertEqual(state["reviews"], 0)

    def test_five_correct_answers_reach_and_stay_in_box_five(self):
        state = None
        for _ in range(6):
            state = scheduler.apply_review(state, True, TODAY)
        self.assertEqual(state["box"], 5)
        self.assertEqual(state["reviews"], 6)


class DueTests(unittest.TestCase):
    def test_new_cards_are_due(self):
        self.assertTrue(scheduler.is_due(None, TODAY))

    def test_card_due_in_the_future_is_not_due(self):
        state = scheduler.new_state(TODAY + timedelta(days=3))
        self.assertFalse(scheduler.is_due(state, TODAY))

    def test_card_due_today_or_earlier_is_due(self):
        self.assertTrue(scheduler.is_due(scheduler.new_state(TODAY), TODAY))
        self.assertTrue(scheduler.is_due(scheduler.new_state(TODAY - timedelta(days=5)), TODAY))

    def test_accuracy(self):
        self.assertIsNone(scheduler.accuracy(None))
        self.assertIsNone(scheduler.accuracy(scheduler.new_state(TODAY)))
        state = {"reviews": 4, "correct": 3}
        self.assertAlmostEqual(scheduler.accuracy(state), 0.75)


class StreakTests(unittest.TestCase):
    def test_no_sessions(self):
        self.assertEqual(
            scheduler.compute_streak([], TODAY),
            {"current": 0, "longest": 0, "last_day": None},
        )

    def test_consecutive_days_ending_today(self):
        days = [TODAY - timedelta(days=offset) for offset in range(3)]
        streak = scheduler.compute_streak(days, TODAY)
        self.assertEqual(streak["current"], 3)
        self.assertEqual(streak["longest"], 3)

    def test_streak_survives_until_the_end_of_the_next_day(self):
        days = [TODAY - timedelta(days=2), TODAY - timedelta(days=1)]
        self.assertEqual(scheduler.compute_streak(days, TODAY)["current"], 2)

    def test_streak_breaks_after_a_missed_day(self):
        days = [TODAY - timedelta(days=5), TODAY - timedelta(days=4)]
        self.assertEqual(scheduler.compute_streak(days, TODAY)["current"], 0)

    def test_longest_streak_is_kept_from_the_past(self):
        days = [TODAY - timedelta(days=offset) for offset in (10, 9, 8, 7, 1, 0)]
        streak = scheduler.compute_streak(days, TODAY)
        self.assertEqual(streak["longest"], 4)
        self.assertEqual(streak["current"], 2)

    def test_duplicate_iso_days_count_once(self):
        days = ["2026-08-02", "2026-08-02", "2026-08-01"]
        self.assertEqual(scheduler.compute_streak(days, TODAY)["current"], 2)


if __name__ == "__main__":
    unittest.main()
