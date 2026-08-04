"""MediCards command line interface.

Run ``python -m src.main --help`` for the full list of commands, or start it
with no arguments for a menu.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import date
from pathlib import Path

if __package__ in (None, ""):  # allow `python src/main.py` as well as `-m src.main`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import scheduler, storage
from src.storage import DeckError

# Card text may contain dashes and accents that the legacy Windows code page
# cannot encode once output is redirected to a file or a pipe.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BOX_LABELS = {
    1: "box 1 (1 day)",
    2: "box 2 (2 days)",
    3: "box 3 (4 days)",
    4: "box 4 (8 days)",
    5: "box 5 (16 days)",
}

RULE = "-" * 62


# --------------------------------------------------------------------------
# shared helpers
# --------------------------------------------------------------------------

def load_decks(args) -> list[dict]:
    """Load the deck named on the command line, or all of them."""
    if getattr(args, "deck", None):
        return [storage.load_deck(storage.resolve_deck(args.deck, args.decks_dir))]

    decks = storage.load_all_decks(args.decks_dir)
    if not decks:
        raise DeckError(f"No decks found in {args.decks_dir}. Add a JSON deck or import a CSV.")
    return decks


def collect_cards(decks: list[dict], progress: dict, on_day: date, due_only: bool = True) -> list[dict]:
    """Flatten decks into review items, optionally keeping only due cards."""
    items = []
    for deck in decks:
        for card in deck["cards"]:
            state = storage.get_card_state(progress, deck["id"], card["id"])
            if due_only and not scheduler.is_due(state, on_day):
                continue
            items.append({"deck": deck, "card": card, "state": state})
    return items


def summarise(decks: list[dict], progress: dict, on_day: date) -> dict:
    """Aggregate counts used by both ``stats`` and ``report``."""
    boxes = {box: 0 for box in range(scheduler.FIRST_BOX, scheduler.LAST_BOX + 1)}
    total = due = new = correct = incorrect = 0

    for deck in decks:
        for card in deck["cards"]:
            total += 1
            state = storage.get_card_state(progress, deck["id"], card["id"])
            if state is None:
                new += 1
                boxes[scheduler.FIRST_BOX] += 1
            else:
                boxes[scheduler.clamp_box(state.get("box", 1))] += 1
                correct += int(state.get("correct", 0))
                incorrect += int(state.get("incorrect", 0))
            if scheduler.is_due(state, on_day):
                due += 1

    answered = correct + incorrect
    deck_id = decks[0]["id"] if len(decks) == 1 else None
    return {
        "date": scheduler.to_iso(on_day),
        "decks": [{"id": d["id"], "name": d["name"], "cards": len(d["cards"])} for d in decks],
        "total_cards": total,
        "due_today": due,
        "new_cards": new,
        "boxes": boxes,
        "answers": {"correct": correct, "incorrect": incorrect, "total": answered},
        "accuracy": (correct / answered) if answered else None,
        "streak": scheduler.compute_streak(storage.study_days(progress, deck_id), on_day),
        "sessions": len(
            [s for s in progress.get("sessions", []) if not deck_id or s.get("deck") == deck_id]
        ),
    }


def format_accuracy(value: float | None) -> str:
    return f"{value * 100:.0f}%" if value is not None else "n/a"


def ask(prompt: str) -> str | None:
    """Read one line, returning ``None`` if the user hits Ctrl+C / Ctrl+D."""
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def cmd_decks(args) -> int:
    paths = storage.list_decks(args.decks_dir)
    if not paths:
        print(f"No decks in {args.decks_dir}.")
        print("Add a JSON deck there, or run:  python -m src.main import-csv <file.csv>")
        return 1

    progress = storage.load_progress(args.progress)
    on_day = scheduler.today()

    print(f"Decks in {args.decks_dir}\n{RULE}")
    for path in paths:
        try:
            deck = storage.load_deck(path)
        except DeckError as exc:
            print(f"  {path.stem:<20} !! {exc}")
            continue
        due = len(collect_cards([deck], progress, on_day))
        print(f"  {deck['id']:<20} {len(deck['cards']):>3} cards   {due:>3} due   {deck['name']}")
    return 0


def cmd_due(args) -> int:
    decks = load_decks(args)
    progress = storage.load_progress(args.progress)
    on_day = scheduler.today()
    items = collect_cards(decks, progress, on_day)

    print(f"Due on {scheduler.to_iso(on_day)}: {len(items)} card(s)\n{RULE}")
    if not items:
        print("  Nothing to review - enjoy the day off.")
        return 0

    for item in items:
        box = (item["state"] or {}).get("box", scheduler.FIRST_BOX)
        marker = "new" if item["state"] is None else f"box {box}"
        question = item["card"]["question"]
        if len(question) > 60:
            question = question[:57] + "..."
        print(f"  [{marker:>5}] {item['deck']['id']:<14} {question}")
    print(f"\nStart reviewing:  python -m src.main review" + (f" --deck {args.deck}" if args.deck else ""))
    return 0


def cmd_review(args) -> int:
    decks = load_decks(args)
    progress = storage.load_progress(args.progress)
    on_day = scheduler.today()

    items = collect_cards(decks, progress, on_day, due_only=not args.all)
    if not items:
        print("Nothing is due today. Use --all to review the whole deck anyway.")
        return 0

    random.shuffle(items)
    if args.limit and args.limit > 0:
        items = items[: args.limit]

    deck_label = decks[0]["name"] if len(decks) == 1 else f"{len(decks)} decks"
    print(f"\nReview session | {deck_label} | {len(items)} card(s)")
    print("Enter = show answer | y = correct | n = wrong | s = skip | q = quit\n")

    reviewed = correct_count = 0
    for index, item in enumerate(items, start=1):
        card, deck, state = item["card"], item["deck"], item["state"]
        box = (state or {}).get("box", scheduler.FIRST_BOX)
        tags = f"  [{', '.join(card['tags'])}]" if card["tags"] else ""

        print(RULE)
        print(f"Card {index}/{len(items)}  |  {deck['id']}  |  {BOX_LABELS[scheduler.clamp_box(box)]}{tags}")
        print(f"Q: {card['question']}")

        command = ask("   [Enter to reveal] ")
        if command is None or command.lower() == "q":
            print("Session stopped early - progress so far is saved.")
            break
        if command.lower() == "s":
            print("Skipped.\n")
            continue

        print(f"A: {card['answer']}")

        verdict = None
        while verdict is None:
            answer = ask("   Did you get it right? [y/n/s/q] ")
            if answer is None or answer.lower() == "q":
                verdict = "quit"
            elif answer.lower() in ("y", "yes"):
                verdict = True
            elif answer.lower() in ("n", "no"):
                verdict = False
            elif answer.lower() == "s":
                verdict = "skip"
            else:
                print("   Please answer y, n, s or q.")

        if verdict == "quit":
            print("Session stopped early - progress so far is saved.")
            break
        if verdict == "skip":
            print("Skipped.\n")
            continue

        new_state = scheduler.apply_review(state, verdict, on_day)
        storage.set_card_state(progress, deck["id"], card["id"], new_state)
        reviewed += 1
        correct_count += 1 if verdict else 0

        moved = "promoted to" if verdict else "back to"
        print(f"   {'[+] correct' if verdict else '[-] wrong'} - {moved} box {new_state['box']}, "
              f"due {new_state['due']}\n")

    if reviewed == 0:
        print("No cards answered, nothing saved.")
        return 0

    storage.record_session(
        progress,
        {
            "date": scheduler.to_iso(on_day),
            "deck": decks[0]["id"] if len(decks) == 1 else "*",
            "reviewed": reviewed,
            "correct": correct_count,
        },
    )
    storage.save_progress(progress, args.progress)

    streak = scheduler.compute_streak(storage.study_days(progress), on_day)
    print(RULE)
    print(f"Reviewed {reviewed} card(s) | {correct_count} correct "
          f"({format_accuracy(correct_count / reviewed)}) | streak {streak['current']} day(s)")
    print(f"Progress saved to {args.progress}")
    return 0


def cmd_stats(args) -> int:
    decks = load_decks(args)
    progress = storage.load_progress(args.progress)
    stats = summarise(decks, progress, scheduler.today())

    scope = decks[0]["name"] if len(decks) == 1 else "All decks"
    print(f"\n{scope} | {stats['date']}\n{RULE}")
    print(f"  Cards           {stats['total_cards']}")
    print(f"  Due today       {stats['due_today']}")
    print(f"  Never reviewed  {stats['new_cards']}")
    print(f"  Answers         {stats['answers']['total']} "
          f"({stats['answers']['correct']} correct, {stats['answers']['incorrect']} wrong)")
    print(f"  Accuracy        {format_accuracy(stats['accuracy'])}")
    print(f"  Sessions        {stats['sessions']}")
    print(f"  Streak          {stats['streak']['current']} day(s) "
          f"(longest {stats['streak']['longest']})")

    print(f"\n  Box distribution\n{RULE}")
    widest = max(stats["boxes"].values()) or 1
    for box in sorted(stats["boxes"]):
        count = stats["boxes"][box]
        bar = "#" * round(28 * count / widest)
        print(f"  {BOX_LABELS[box]:<16} {count:>4}  {bar}")
    return 0


def cmd_import_csv(args) -> int:
    path = storage.import_csv(args.csv, args.decks_dir, args.name)
    deck = storage.load_deck(path)
    print(f"Imported {len(deck['cards'])} card(s) into {path}")
    print(f"Review it with:  python -m src.main review --deck {deck['id']}")
    return 0


def cmd_report(args) -> int:
    decks = load_decks(args)
    progress = storage.load_progress(args.progress)
    stats = summarise(decks, progress, scheduler.today())

    if args.format == "json":
        text = json.dumps(stats, indent=2, ensure_ascii=False) + "\n"
    else:
        lines = [
            "# MediCards progress report",
            "",
            f"Generated: {stats['date']}",
            "",
            "## Summary",
            "",
            "| Metric | Value |",
            "| --- | --- |",
            f"| Cards | {stats['total_cards']} |",
            f"| Due today | {stats['due_today']} |",
            f"| Never reviewed | {stats['new_cards']} |",
            f"| Answers | {stats['answers']['total']} |",
            f"| Accuracy | {format_accuracy(stats['accuracy'])} |",
            f"| Sessions | {stats['sessions']} |",
            f"| Current streak | {stats['streak']['current']} day(s) |",
            f"| Longest streak | {stats['streak']['longest']} day(s) |",
            "",
            "## Cards per box",
            "",
            "| Box | Cards |",
            "| --- | --- |",
        ]
        lines += [f"| {BOX_LABELS[box]} | {count} |" for box, count in sorted(stats["boxes"].items())]
        lines += ["", "## Decks", "", "| Deck | Cards |", "| --- | --- |"]
        lines += [f"| {d['name']} | {d['cards']} |" for d in stats["decks"]]
        text = "\n".join(lines) + "\n"

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(f"Report written to {out_path}")
    else:
        print(text, end="")
    return 0


# --------------------------------------------------------------------------
# interactive menu
# --------------------------------------------------------------------------

MENU = """
MediCards - spaced repetition for medical facts
{rule}
  1) List decks
  2) Show cards due today
  3) Start a review session
  4) Statistics
  5) Export a progress report
  q) Quit
"""


def run_menu(args) -> int:
    while True:
        print(MENU.format(rule=RULE))
        choice = ask("Choose: ")
        if choice is None or choice.lower() in ("q", "quit", "exit"):
            print("Bye.")
            return 0

        actions = {"1": cmd_decks, "2": cmd_due, "3": cmd_review, "4": cmd_stats}
        try:
            if choice in actions:
                if choice in ("2", "3", "4"):
                    deck = ask("Deck name (Enter for all decks): ")
                    args.deck = deck or None
                actions[choice](args)
            elif choice == "5":
                args.format = "md"
                args.out = ask("Output file (Enter for reports/report.md): ") or "reports/report.md"
                cmd_report(args)
            else:
                print("Unknown choice.")
        except DeckError as exc:
            print(f"Error: {exc}")


# --------------------------------------------------------------------------
# argument parsing
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="medicards",
        description="Medical flashcards with Leitner-box spaced repetition.",
    )
    parser.add_argument("--decks-dir", default=str(storage.DECKS_DIR), help="folder holding deck JSON files")
    parser.add_argument("--progress", default=str(storage.PROGRESS_FILE), help="progress file to read and write")

    subparsers = parser.add_subparsers(dest="command")

    deck_option = ("--deck", {"help": "deck name, stem or path (default: every deck)"})

    p_decks = subparsers.add_parser("decks", help="list available decks")
    p_decks.set_defaults(func=cmd_decks, deck=None)

    p_due = subparsers.add_parser("due", help="show the cards due today")
    p_due.add_argument(deck_option[0], **deck_option[1])
    p_due.set_defaults(func=cmd_due)

    p_review = subparsers.add_parser("review", help="run an interactive review session")
    p_review.add_argument(deck_option[0], **deck_option[1])
    p_review.add_argument("--limit", type=int, default=20, help="maximum cards this session (default: 20)")
    p_review.add_argument("--all", action="store_true", help="include cards that are not due yet")
    p_review.set_defaults(func=cmd_review)

    p_stats = subparsers.add_parser("stats", help="show progress statistics")
    p_stats.add_argument(deck_option[0], **deck_option[1])
    p_stats.set_defaults(func=cmd_stats)

    p_import = subparsers.add_parser("import-csv", help="turn a CSV file into a deck")
    p_import.add_argument("csv", help="CSV with question,answer[,id,tags] columns")
    p_import.add_argument("--name", help="deck name (default: the file name)")
    p_import.set_defaults(func=cmd_import_csv, deck=None)

    p_report = subparsers.add_parser("report", help="export a progress report")
    p_report.add_argument(deck_option[0], **deck_option[1])
    p_report.add_argument("--format", choices=("md", "json"), default="md")
    p_report.add_argument("--out", help="file to write (default: print to screen)")
    p_report.set_defaults(func=cmd_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if not getattr(args, "command", None):
            args.deck = None
            return run_menu(args)
        return args.func(args)
    except DeckError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
