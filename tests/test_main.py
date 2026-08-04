"""Tests for the CLI helpers and the decks shipped with the project."""

import json
import sys
import tempfile
import unittest
from argparse import Namespace
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import main, scheduler, storage

TODAY = date(2026, 8, 2)

DECK = {
    "name": "Test deck",
    "cards": [
        {"id": "c1", "question": "Q1", "answer": "A1"},
        {"id": "c2", "question": "Q2", "answer": "A2"},
        {"id": "c3", "question": "Q3", "answer": "A3"},
    ],
}


class CliTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

        self.decks_dir = self.tmp / "decks"
        self.decks_dir.mkdir()
        (self.decks_dir / "test.json").write_text(json.dumps(DECK), encoding="utf-8")

        self.progress_path = self.tmp / "progress.json"
        self.deck = storage.load_deck(self.decks_dir / "test.json")

    def args(self, **overrides) -> Namespace:
        base = {"deck": None, "decks_dir": str(self.decks_dir), "progress": str(self.progress_path)}
        base.update(overrides)
        return Namespace(**base)


class CollectCardsTests(CliTestCase):
    def test_every_card_of_a_fresh_deck_is_due(self):
        items = main.collect_cards([self.deck], storage.empty_progress(), TODAY)
        self.assertEqual(len(items), 3)
        self.assertTrue(all(item["state"] is None for item in items))

    def test_scheduled_cards_drop_out_until_their_due_date(self):
        progress = storage.empty_progress()
        storage.set_card_state(progress, "test", "c1", scheduler.apply_review(None, True, TODAY))

        due_today = main.collect_cards([self.deck], progress, TODAY)
        self.assertEqual([item["card"]["id"] for item in due_today], ["c2", "c3"])

        due_later = main.collect_cards([self.deck], progress, TODAY + timedelta(days=2))
        self.assertEqual(len(due_later), 3)

    def test_due_only_false_returns_everything(self):
        progress = storage.empty_progress()
        storage.set_card_state(progress, "test", "c1", scheduler.apply_review(None, True, TODAY))
        items = main.collect_cards([self.deck], progress, TODAY, due_only=False)
        self.assertEqual(len(items), 3)


class SummariseTests(CliTestCase):
    def test_fresh_deck(self):
        stats = main.summarise([self.deck], storage.empty_progress(), TODAY)
        self.assertEqual(stats["total_cards"], 3)
        self.assertEqual(stats["due_today"], 3)
        self.assertEqual(stats["new_cards"], 3)
        self.assertEqual(stats["boxes"][1], 3)
        self.assertIsNone(stats["accuracy"])
        self.assertEqual(stats["streak"]["current"], 0)

    def test_counts_after_a_session(self):
        progress = storage.empty_progress()
        storage.set_card_state(progress, "test", "c1", scheduler.apply_review(None, True, TODAY))
        storage.set_card_state(progress, "test", "c2", scheduler.apply_review(None, False, TODAY))
        storage.record_session(progress, {"date": scheduler.to_iso(TODAY), "deck": "test",
                                          "reviewed": 2, "correct": 1})

        stats = main.summarise([self.deck], progress, TODAY)
        self.assertEqual(stats["new_cards"], 1)
        self.assertEqual(stats["due_today"], 1)  # only the untouched card
        self.assertEqual(stats["boxes"][1], 2)   # the wrong answer plus the new card
        self.assertEqual(stats["boxes"][2], 1)
        self.assertEqual(stats["answers"], {"correct": 1, "incorrect": 1, "total": 2})
        self.assertAlmostEqual(stats["accuracy"], 0.5)
        self.assertEqual(stats["sessions"], 1)

    def test_box_counts_always_add_up_to_the_deck_size(self):
        progress = storage.empty_progress()
        state = None
        for _ in range(3):
            state = scheduler.apply_review(state, True, TODAY)
        storage.set_card_state(progress, "test", "c1", state)
        stats = main.summarise([self.deck], progress, TODAY)
        self.assertEqual(sum(stats["boxes"].values()), stats["total_cards"])


class ReportTests(CliTestCase):
    def test_json_report_is_written_to_disk(self):
        out = self.tmp / "reports" / "report.json"
        exit_code = main.cmd_report(self.args(format="json", out=str(out)))
        self.assertEqual(exit_code, 0)

        report = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(report["total_cards"], 3)
        self.assertEqual(report["decks"][0]["id"], "test")

    def test_markdown_report_contains_a_summary_table(self):
        out = self.tmp / "report.md"
        main.cmd_report(self.args(format="md", out=str(out)))
        text = out.read_text(encoding="utf-8")
        self.assertIn("# MediCards progress report", text)
        self.assertIn("| Cards | 3 |", text)


class CliPlumbingTests(CliTestCase):
    def test_unknown_deck_exits_with_an_error_code(self):
        self.assertEqual(main.main(["--decks-dir", str(self.decks_dir), "due", "--deck", "ghost"]), 1)

    def test_decks_command_runs(self):
        argv = ["--decks-dir", str(self.decks_dir), "--progress", str(self.progress_path), "decks"]
        self.assertEqual(main.main(argv), 0)

    def test_review_defaults(self):
        args = main.build_parser().parse_args(["review"])
        self.assertEqual(args.limit, 20)
        self.assertFalse(args.all)
        self.assertIsNone(args.deck)


class ShippedDeckTests(unittest.TestCase):
    def test_bundled_decks_all_load(self):
        decks = storage.load_all_decks(storage.DECKS_DIR)
        self.assertGreaterEqual(len(decks), 3)
        for deck in decks:
            self.assertTrue(deck["cards"], f"{deck['id']} has no cards")
            for card in deck["cards"]:
                self.assertTrue(card["question"] and card["answer"])


if __name__ == "__main__":
    unittest.main()
