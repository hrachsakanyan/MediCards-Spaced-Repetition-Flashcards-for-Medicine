"""Tests for deck loading, CSV import and progress persistence."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import storage
from src.storage import DeckError

SAMPLE_DECK = {
    "name": "Sample",
    "description": "two cards",
    "cards": [
        {"id": "a1", "question": "Antidote for heparin?", "answer": "Protamine", "tags": ["antidote"]},
        {"question": "ICD-10 for asthma?", "answer": "J45"},
    ],
}


class TempDirTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write_deck(self, name="sample", deck=None) -> Path:
        path = self.tmp / f"{name}.json"
        path.write_text(json.dumps(deck or SAMPLE_DECK), encoding="utf-8")
        return path


class LoadDeckTests(TempDirTestCase):
    def test_loads_cards_and_fills_in_defaults(self):
        deck = storage.load_deck(self.write_deck())
        self.assertEqual(deck["id"], "sample")
        self.assertEqual(deck["name"], "Sample")
        self.assertEqual(len(deck["cards"]), 2)
        self.assertEqual(deck["cards"][0]["tags"], ["antidote"])
        self.assertEqual(deck["cards"][1]["tags"], [])

    def test_missing_id_gets_a_stable_hash_id(self):
        deck = storage.load_deck(self.write_deck())
        generated = deck["cards"][1]["id"]
        self.assertEqual(generated, storage.fallback_card_id("ICD-10 for asthma?"))
        self.assertEqual(storage.load_deck(self.write_deck())["cards"][1]["id"], generated)

    def test_missing_file(self):
        with self.assertRaises(DeckError):
            storage.load_deck(self.tmp / "nope.json")

    def test_invalid_json(self):
        path = self.tmp / "broken.json"
        path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(DeckError):
            storage.load_deck(path)

    def test_card_without_answer_is_rejected(self):
        deck = {"name": "x", "cards": [{"question": "Q", "answer": "  "}]}
        with self.assertRaises(DeckError):
            storage.load_deck(self.write_deck("bad", deck))

    def test_duplicate_ids_are_rejected(self):
        deck = {"cards": [{"id": "a", "question": "Q1", "answer": "A1"},
                          {"id": "a", "question": "Q2", "answer": "A2"}]}
        with self.assertRaises(DeckError):
            storage.load_deck(self.write_deck("dupes", deck))

    def test_empty_deck_is_rejected(self):
        with self.assertRaises(DeckError):
            storage.load_deck(self.write_deck("empty", {"cards": []}))


class ResolveDeckTests(TempDirTestCase):
    def test_resolves_by_stem_file_name_and_path(self):
        path = self.write_deck("pharm")
        self.assertEqual(storage.resolve_deck("pharm", self.tmp), path)
        self.assertEqual(storage.resolve_deck("pharm.json", self.tmp), path)
        self.assertEqual(storage.resolve_deck(str(path), self.tmp), path)

    def test_unknown_deck_lists_the_available_ones(self):
        self.write_deck("pharm")
        with self.assertRaises(DeckError) as ctx:
            storage.resolve_deck("cardio", self.tmp)
        self.assertIn("pharm", str(ctx.exception))

    def test_list_decks_is_sorted_and_ignores_other_files(self):
        self.write_deck("b")
        self.write_deck("a")
        (self.tmp / "notes.txt").write_text("hello", encoding="utf-8")
        self.assertEqual([p.stem for p in storage.list_decks(self.tmp)], ["a", "b"])

    def test_list_decks_on_a_missing_folder(self):
        self.assertEqual(storage.list_decks(self.tmp / "missing"), [])


class ProgressTests(TempDirTestCase):
    def test_missing_progress_file_returns_an_empty_record(self):
        progress = storage.load_progress(self.tmp / "progress.json")
        self.assertEqual(progress["cards"], {})
        self.assertEqual(progress["sessions"], [])

    def test_corrupt_progress_file_does_not_crash(self):
        path = self.tmp / "progress.json"
        path.write_text("<<<broken>>>", encoding="utf-8")
        self.assertEqual(storage.load_progress(path)["cards"], {})

    def test_round_trip(self):
        path = self.tmp / "nested" / "progress.json"
        progress = storage.empty_progress()
        storage.set_card_state(progress, "pharm", "a1", {"box": 3, "due": "2026-08-09"})
        storage.record_session(progress, {"date": "2026-08-02", "deck": "pharm", "reviewed": 4, "correct": 3})
        storage.save_progress(progress, path)

        reloaded = storage.load_progress(path)
        self.assertEqual(storage.get_card_state(reloaded, "pharm", "a1")["box"], 3)
        self.assertEqual(reloaded["sessions"][0]["reviewed"], 4)

    def test_card_keys_are_namespaced_by_deck(self):
        progress = storage.empty_progress()
        storage.set_card_state(progress, "pharm", "a1", {"box": 2})
        storage.set_card_state(progress, "icd10", "a1", {"box": 5})
        self.assertEqual(storage.get_card_state(progress, "pharm", "a1")["box"], 2)
        self.assertEqual(storage.get_card_state(progress, "icd10", "a1")["box"], 5)

    def test_study_days_can_be_filtered_by_deck(self):
        progress = storage.empty_progress()
        storage.record_session(progress, {"date": "2026-08-01", "deck": "pharm", "reviewed": 2, "correct": 1})
        storage.record_session(progress, {"date": "2026-08-02", "deck": "icd10", "reviewed": 3, "correct": 3})
        storage.record_session(progress, {"date": "2026-08-03", "deck": "pharm", "reviewed": 0, "correct": 0})
        self.assertEqual(storage.study_days(progress), ["2026-08-01", "2026-08-02"])
        self.assertEqual(storage.study_days(progress, "pharm"), ["2026-08-01"])


class ImportCsvTests(TempDirTestCase):
    def write_csv(self, text: str) -> Path:
        path = self.tmp / "import.csv"
        path.write_text(text, encoding="utf-8")
        return path

    def test_import_creates_a_usable_deck(self):
        csv_path = self.write_csv(
            "question,answer,tags\n"
            "Antidote for iron overdose?,Deferoxamine,antidote;toxicology\n"
            "ICD-10 for COPD?,J44,\n"
        )
        out = storage.import_csv(csv_path, self.tmp / "decks", deck_name="Quick Review")
        self.assertEqual(out.name, "quick-review.json")

        deck = storage.load_deck(out)
        self.assertEqual(len(deck["cards"]), 2)
        self.assertEqual(deck["cards"][0]["tags"], ["antidote", "toxicology"])
        self.assertEqual(deck["cards"][1]["tags"], [])

    def test_blank_lines_are_skipped(self):
        csv_path = self.write_csv("question,answer\nQ1,A1\n,\nQ2,A2\n")
        deck = storage.load_deck(storage.import_csv(csv_path, self.tmp / "decks"))
        self.assertEqual(len(deck["cards"]), 2)

    def test_half_filled_row_is_an_error(self):
        csv_path = self.write_csv("question,answer\nQ1,\n")
        with self.assertRaises(DeckError):
            storage.import_csv(csv_path, self.tmp / "decks")

    def test_missing_columns_are_reported(self):
        csv_path = self.write_csv("front,back\nQ1,A1\n")
        with self.assertRaises(DeckError):
            storage.import_csv(csv_path, self.tmp / "decks")

    def test_missing_csv_file(self):
        with self.assertRaises(DeckError):
            storage.import_csv(self.tmp / "nope.csv", self.tmp / "decks")


class SlugifyTests(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(storage.slugify("Quick Review"), "quick-review")
        self.assertEqual(storage.slugify("  ICD-10 / codes  "), "icd-10-codes")
        self.assertEqual(storage.slugify("***"), "deck")


if __name__ == "__main__":
    unittest.main()
