# 💊 MediCards

### Spaced Repetition Flashcards for Medicine

<p align="center">
  <strong>A command-line medical flashcard trainer powered by the Leitner spaced repetition algorithm.</strong>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#how-spaced-repetition-works-here">How It Works</a> •
  <a href="#install">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#tests">Tests</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/Dependencies-0-success" alt="No Dependencies">
  <img src="https://img.shields.io/badge/Tests-54%20Passing-brightgreen" alt="54 Tests Passing">
  <img src="https://img.shields.io/badge/Storage-JSON-orange" alt="JSON Storage">
  <img src="https://img.shields.io/badge/Algorithm-Leitner-purple" alt="Leitner Algorithm">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="MIT License">
</p>

---

## 🩺 What is MediCards?

**MediCards** is a lightweight command-line flashcard application designed for studying and
retaining medical knowledge.

It helps you review:

* 💊 Pharmacology
* 🚑 Emergency dosages
* 🧬 ICD-10 codes
* 🧠 Medical facts and concepts
* 🏷️ Custom medical flashcard decks

Instead of showing every card every day, MediCards uses the **Leitner spaced repetition system** to
prioritize the information you are most likely to forget.

Cards you consistently answer correctly gradually appear less often, while cards you get wrong
return to the first box for more frequent review.

> ⚠️ **Educational use only:** The included medical content is a study aid and not clinical guidance.
> Always verify medications, doses, codes, and protocols against current local guidelines and official
> clinical resources before patient care.

---

## ✨ Features

| Feature                    | Description                                            |
| -------------------------- | ------------------------------------------------------ |
| 🧠 **Spaced Repetition**   | Leitner algorithm with 5 progressive learning boxes    |
| 📚 **Multiple Decks**      | Load and manage several JSON-based flashcard decks     |
| 🎯 **Due Cards**           | Quickly see exactly what needs to be reviewed today    |
| 📈 **Statistics**          | Track accuracy, box distribution, reviews and progress |
| 🔥 **Study Streaks**       | Track current and longest consecutive study streaks    |
| 💾 **Persistent Progress** | Automatically save learning history in JSON            |
| 📥 **CSV Import**          | Create new decks from CSV files                        |
| 📤 **Progress Reports**    | Export progress as Markdown or JSON                    |
| 🖥️ **Interactive CLI**    | Review cards directly from your terminal               |
| 🧪 **54 Unit Tests**       | Tested with Python's standard `unittest` framework     |
| 🚫 **Zero Dependencies**   | Uses only the Python standard library                  |

---

## 🚀 Quick Start

```bash
git clone https://github.com/<your-username>/medicards.git
cd medicards
python -m src.main --help
```

Start the interactive menu:

```bash
python -m src.main
```

Or immediately check what is due:

```bash
python -m src.main due
```

---

## 🧠 How Spaced Repetition Works

MediCards uses the **Leitner Box System**.

Imagine five physical boxes on your desk. Every new card starts in **Box 1**.

When you review a card:

```text
                    ┌───────────────┐
                    │   Correct ✅  │
                    └───────┬───────┘
                            │
                            ▼
                    Move up one box
                            │
                            ▼
        ┌───────┐ → ┌───────┐ → ┌───────┐ → ┌───────┐ → ┌───────┐
        │ Box 1 │   │ Box 2 │   │ Box 3 │   │ Box 4 │   │ Box 5 │
        │  1 day│   │ 2 days│   │ 4 days│   │ 8 days│   │16 days│
        └───────┘   └───────┘   └───────┘   └───────┘   └───────┘
                            ▲
                            │
                    Wrong ❌ → Box 1
```

| Box      | Review Interval | Learning Stage             |
| -------- | --------------: | -------------------------- |
| 📦 Box 1 |           1 day | New / frequently forgotten |
| 📦 Box 2 |          2 days | Starting to stick          |
| 📦 Box 3 |          4 days | Fairly solid               |
| 📦 Box 4 |          8 days | Well learned               |
| 📦 Box 5 |         16 days | Long-term memory           |

### The rule is simple:

**Correct → Move one box up ⬆️**

**Wrong → Return to Box 1 🔄**

This means your study time naturally shifts toward the cards you struggle with most.

---

## 💻 Example

```text
$ python -m src.main due

Due on 2026-08-02: 20 card(s)
--------------------------------------------------------------
  [ new] pharmacology   Antidote for paracetamol overdose?
  [box 2] pharmacology  Mechanism of action of statins?
  [ new] icd10          ICD-10 code for essential hypertension?
```

Start a review session:

```bash
python -m src.main review
```

Example session:

```text
--------------------------------------------------------------
Card 1/5  |  pharmacology  |  box 1 (1 day)
Tags: antidote, cardiology

Q: Antidote for digoxin toxicity?

[Enter to reveal]

A: Digoxin-specific antibody Fab fragments (DigiFab)...

Did you get it right? [y/n/s/q] y

[+] correct
Promoted to box 2
Next review: 2026-08-04

--------------------------------------------------------------
Reviewed 5 card(s) | 4 correct (80%) | streak 3 day(s)

Progress saved to data/progress.json
```

---

## 🗂️ Included Decks

| Deck              | Cards | Topics                                                       |
| ----------------- | ----: | ------------------------------------------------------------ |
| 💊 `pharmacology` |    22 | Antidotes, drug mechanisms, monitoring, classic side effects |
| 🚑 `dosages`      |    18 | Adult emergency doses, anaphylaxis, arrest, seizures, trauma |
| 🧬 `icd10`        |    22 | Common ICD-10 codes and code structure                       |

---

## 🛠️ Tech Stack

```text
Python 3.9+
│
├── argparse       → CLI interface
├── json           → Progress persistence
├── csv            → Deck importing
├── pathlib        → File management
├── hashlib        → Stable card IDs
├── unittest       → Automated testing
└── os.replace      → Atomic file writes
```

**Architecture:**

```text
                 ┌──────────────────────┐
                 │       main.py        │
                 │ CLI + Review + Menu  │
                 └──────────┬───────────┘
                            │
               ┌────────────┴────────────┐
               │                         │
               ▼                         ▼
      ┌─────────────────┐       ┌─────────────────┐
      │   scheduler.py  │       │   storage.py    │
      │                 │       │                 │
      │ Leitner Logic   │       │ JSON / CSV      │
      │ Boxes           │       │ Deck Loading     │
      │ Due Dates       │       │ Persistence      │
      │ Streaks         │       │ Atomic Writes    │
      └─────────────────┘       └─────────────────┘
```

The architecture intentionally separates **business logic** from **I/O**.

* `scheduler.py` → pure scheduling logic
* `storage.py` → data loading and persistence
* `main.py` → CLI and user interaction

This makes the system easier to test and makes it possible to replace the Leitner algorithm with
another scheduler such as **SM-2** or **FSRS** without rewriting the entire application.

---

## 📊 Progress Tracking

Your personal learning history is stored locally:

```text
data/progress.json
```

Example:

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
  }
}
```

Your progress file is **git-ignored**, meaning your personal study history stays local.

Progress files are written atomically using a temporary file followed by `os.replace`, helping
prevent corrupted history if the application is interrupted during saving.

---

## 🧪 Testing

Run the full test suite:

```bash
python -m unittest discover -s tests -v
```

Current test suite:

```text
Ran 54 tests in 0.09s
OK
```

Tests cover:

* Leitner box promotion and demotion
* Review interval calculations
* Due-date logic
* Study streak calculations
* Deck validation
* CSV import edge cases
* Atomic progress persistence
* CLI card selection
* Statistics
* Report generation

---

## 📁 Project Structure

```text
medicards/
├── src/
│   ├── main.py           # CLI, review sessions, menus, reports
│   ├── scheduler.py      # Leitner algorithm and scheduling logic
│   └── storage.py        # JSON/CSV loading and persistence
│
├── data/
│   ├── decks/
│   │   ├── pharmacology.json
│   │   ├── dosages.json
│   │   └── icd10.json
│   ├── progress.json     # Local progress (git-ignored)
│   └── sample_import.csv
│
├── tests/
│   ├── test_scheduler.py
│   ├── test_storage.py
│   └── test_main.py
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

## 🔮 Future Improvements

Potential next steps:

* ⌨️ Typed answers with fuzzy matching
* 🏷️ Tag-based filtering
* 🪨 "Leech" detection for repeatedly failed cards
* 🧠 SM-2 / FSRS scheduling algorithms
* 📤 Export decks back to CSV
* 🔄 Anki-compatible export
* 📊 Richer progress visualizations
* 🌐 Optional web interface

---

## 📄 License

MIT License

---

<p align="center">
  Built with Python 🐍
</p>
