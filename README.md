# MediCards — Spaced Repetition Flashcards for Medicine

A command line flashcard trainer for medical facts — antidotes, emergency dosages, ICD-10 codes —
built around the **Leitner box** spaced repetition algorithm. Cards you keep getting right come back
less and less often; cards you miss come straight back tomorrow.

Pure Python standard library. No dependencies, no database, no account. Your progress lives in one
JSON file.

```
$ python -m src.main due
Due on 2026-08-02: 20 card(s)
--------------------------------------------------------------
  [  new] pharmacology   Antidote for paracetamol (acetaminophen) overdose?
  [box 2] pharmacology   Mechanism of action of statins?
  [  new] icd10          ICD-10 code for essential (primary) hypertension?
```

---

## How spaced repetition works here

The **Leitner system** is the simplest spaced repetition algorithm that actually works. Imagine five
physical boxes on your desk. Every card starts in box 1. Each time you review it:

- **Right** → the card moves **one box up**, so you will not see it again for longer.
- **Wrong** → the card drops **all the way back to box 1**, no matter how far it had climbed.

Each box has its own waiting time:

| Box | Reviewed again after | Meaning |
| --- | --- | --- |
| 1 | 1 day | brand new, or just got it wrong |
| 2 | 2 days | starting to stick |
| 3 | 4 days | fairly solid |
| 4 | 8 days | well learned |
| 5 | 16 days | long-term memory |

A card is **due** when its scheduled date is today or in the past. New cards are always due.
The intervals roughly double, which is the point: the longer you can already recall something, the
longer you can safely wait before checking again — and the more of your study time goes to the
cards you actually keep forgetting.

The whole algorithm is about forty lines in [src/scheduler.py](src/scheduler.py):

```python
def apply_review(state, correct, reviewed_on):
    box = promote(state["box"]) if correct else demote(state["box"])   # up one, or back to 1
    state["box"] = box
    state["due"] = to_iso(next_review(box, reviewed_on))               # today + box interval
    ...
```

---

## Features

- Load Q&A decks from JSON, several decks side by side
- Interactive review session: question → reveal → self-grade
- Leitner scheduling with five boxes and automatic next-review dates
- Progress, statistics and per-card history saved to `data/progress.json`
- **Due today** view, so you always know how much work is waiting
- **Streaks** — current and longest run of consecutive study days
- Import decks from CSV
- Export a progress report as Markdown or JSON
- Menu mode for browsing, subcommands for everything else
- 54 unit tests, no third-party packages

---

## Install

Python 3.9 or newer. That's it.

```bash
git clone https://github.com/<your-username>/medicards.git
cd medicards
python -m src.main --help
```

*(On Windows use `py` instead of `python` if that is how your launcher is set up.)*

---

## Usage

```bash
python -m src.main                       # interactive menu
python -m src.main decks                 # list decks with card and due counts
python -m src.main due                   # what is waiting today
python -m src.main due --deck icd10      # ...for one deck

python -m src.main review                        # review everything due, max 20 cards
python -m src.main review --deck pharmacology    # one deck only
python -m src.main review --limit 10             # shorter session
python -m src.main review --all                  # ignore the schedule, drill the whole deck

python -m src.main stats                         # box distribution, accuracy, streak
python -m src.main import-csv data/sample_import.csv --name "Quick Review"
python -m src.main report --format md --out reports/progress.md
python -m src.main report --format json --out reports/progress.json
```

Global options: `--decks-dir` and `--progress` point the app at a different deck folder or progress
file — handy for keeping a separate exam set.

### Inside a review session

| Key | Action |
| --- | --- |
| `Enter` | reveal the answer |
| `y` | I got it right — promote the card |
| `n` | I got it wrong — back to box 1 |
| `s` | skip, leave the schedule untouched |
| `q` | quit; everything answered so far is saved |

```
--------------------------------------------------------------
Card 1/5  |  pharmacology  |  box 1 (1 day)  [antidote, cardiology]
Q: Antidote for digoxin toxicity?
   [Enter to reveal] A: Digoxin-specific antibody Fab fragments (DigiFab)...
   Did you get it right? [y/n/s/q] y
   [+] correct - promoted to box 2, due 2026-08-04
--------------------------------------------------------------
Reviewed 5 card(s) | 4 correct (80%) | streak 3 day(s)
Progress saved to data/progress.json
```

---

## Deck format

A deck is one JSON file in `data/decks/`. The file name is the deck id (`icd10.json` → `icd10`).

```json
{
  "name": "ICD-10 - everyday codes",
  "description": "Frequently used ICD-10 codes and chapter structure.",
  "cards": [
    {
      "id": "icd-001",
      "question": "ICD-10 code for essential (primary) hypertension?",
      "answer": "I10",
      "tags": ["cardiology"]
    }
  ]
}
```

- `question` and `answer` are required; `name`, `description`, `id` and `tags` are optional.
- If you leave out `id`, MediCards derives a stable one by hashing the question, so reordering a
  deck never scrambles your progress.
- Card ids only need to be unique *within* a deck — progress is stored as `deck::card`.

### CSV import

Header row required, `question` and `answer` columns required, `id` and `tags` optional
(tags separated by `;`):

```csv
question,answer,tags
Antidote for cyanide poisoning?,Hydroxocobalamin,antidote;toxicology
ICD-10 code for iron deficiency anaemia?,D50,haematology
```

```bash
python -m src.main import-csv data/sample_import.csv --name "Quick Review"
```

### Included decks

| Deck | Cards | About |
| --- | --- | --- |
| `pharmacology` | 22 | Antidotes, drug mechanisms, monitoring, classic side effects |
| `dosages` | 18 | Adult emergency doses — anaphylaxis, arrest, seizures, trauma |
| `icd10` | 22 | Everyday ICD-10 codes and how the code structure works |

> ⚠️ **These decks are a study aid, not clinical guidance.** Doses, codes and protocols vary by
> country, guideline version and patient. Always check your local formulary and protocol before
> treating anyone.

---

## Progress file

`data/progress.json` is git-ignored — your study history is yours.

```json
{
  "version": 1,
  "cards": {
    "pharmacology::ph-001": {
      "box": 3,
      "due": "2026-08-06",
      "correct": 4,
      "incorrect": 1,
      "reviews": 5,
      "last_reviewed": "2026-08-02"
    }
  },
  "sessions": [
    { "date": "2026-08-02", "deck": "pharmacology", "reviewed": 12, "correct": 9 }
  ]
}
```

Sessions are what streaks are computed from. Writes are atomic (temp file + `os.replace`), so an
interrupted save cannot corrupt your history.

---

## Project layout

```
medicards/
├── src/
│   ├── main.py           # CLI: commands, review session, menu, reports
│   ├── scheduler.py      # Leitner algorithm — boxes, intervals, due dates, streaks
│   └── storage.py        # deck loading, CSV import, atomic JSON persistence
├── data/
│   ├── decks/            # pharmacology.json, dosages.json, icd10.json
│   ├── progress.json     # your progress (git-ignored)
│   └── sample_import.csv
├── tests/
│   ├── test_scheduler.py
│   ├── test_storage.py
│   └── test_main.py
├── README.md
├── requirements.txt
└── .gitignore
```

`scheduler.py` does no I/O and `storage.py` knows nothing about the Leitner rules — which is why
both are easy to test and why swapping in a different algorithm (SM-2, FSRS) would only touch one
file.

---

## Tests

```bash
python -m unittest discover -s tests -v
```

```
Ran 54 tests in 0.09s
OK
```

Covered: box promotion/demotion and interval maths, due-date logic, streak counting across gaps,
deck validation and error messages, CSV import edge cases, atomic progress round-trips, and the
CLI's card selection, statistics and report output.

---

## Ideas for next steps

- Typed answers with fuzzy matching instead of self-grading
- Tag filters (`review --tag antidote`)
- A "leech" list for cards that keep falling back to box 1
- SM-2 / FSRS scheduling behind the same `scheduler` interface
- Export a deck back to CSV or Anki

---

## License

MIT
