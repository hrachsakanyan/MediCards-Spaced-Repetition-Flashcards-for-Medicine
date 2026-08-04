"""Reading decks, importing CSV and persisting progress to JSON."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
from pathlib import Path

PROGRESS_VERSION = 1

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DECKS_DIR = DATA_DIR / "decks"
PROGRESS_FILE = DATA_DIR / "progress.json"


class DeckError(Exception):
    """Raised when a deck file is missing or malformed."""


# --------------------------------------------------------------------------
# decks
# --------------------------------------------------------------------------

def list_decks(decks_dir: Path | str = DECKS_DIR) -> list[Path]:
    """Every ``*.json`` deck in ``decks_dir``, sorted by file name."""
    decks_dir = Path(decks_dir)
    if not decks_dir.is_dir():
        return []
    return sorted(decks_dir.glob("*.json"))


def resolve_deck(name: str, decks_dir: Path | str = DECKS_DIR) -> Path:
    """Find a deck by file name, stem or path.

    ``pharmacology``, ``pharmacology.json`` and ``data/decks/pharmacology.json``
    all resolve to the same file.
    """
    candidate = Path(name)
    if candidate.is_file():
        return candidate

    decks_dir = Path(decks_dir)
    for path in (decks_dir / name, decks_dir / f"{name}.json"):
        if path.is_file():
            return path

    available = ", ".join(p.stem for p in list_decks(decks_dir)) or "none found"
    raise DeckError(f"Deck {name!r} not found. Available decks: {available}")


def fallback_card_id(question: str) -> str:
    """Stable id derived from the question, for decks that omit ``id``.

    Hashing the question (rather than using the position in the file) keeps
    progress attached to the right card when a deck is reordered.
    """
    digest = hashlib.sha1(question.strip().encode("utf-8")).hexdigest()
    return f"q{digest[:8]}"


def load_deck(path: Path | str) -> dict:
    """Load and validate a deck file.

    Returns ``{"id", "name", "description", "path", "cards"}`` where every card
    is guaranteed to have ``id``, ``question``, ``answer`` and ``tags``.
    """
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DeckError(f"Deck file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DeckError(f"Deck {path.name} is not valid JSON: {exc}") from exc

    if not isinstance(raw, dict) or not isinstance(raw.get("cards"), list):
        raise DeckError(f"Deck {path.name} must be an object with a 'cards' list")

    cards, seen_ids = [], set()
    for index, card in enumerate(raw["cards"], start=1):
        if not isinstance(card, dict):
            raise DeckError(f"Deck {path.name}: card #{index} is not an object")

        question = str(card.get("question", "")).strip()
        answer = str(card.get("answer", "")).strip()
        if not question or not answer:
            raise DeckError(f"Deck {path.name}: card #{index} needs a question and an answer")

        card_id = str(card.get("id") or fallback_card_id(question))
        if card_id in seen_ids:
            raise DeckError(f"Deck {path.name}: duplicate card id {card_id!r}")
        seen_ids.add(card_id)

        tags = card.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]

        cards.append(
            {
                "id": card_id,
                "question": question,
                "answer": answer,
                "tags": [str(tag).strip() for tag in tags if str(tag).strip()],
            }
        )

    if not cards:
        raise DeckError(f"Deck {path.name} contains no cards")

    return {
        "id": path.stem,
        "name": str(raw.get("name") or path.stem),
        "description": str(raw.get("description") or ""),
        "path": str(path),
        "cards": cards,
    }


def load_all_decks(decks_dir: Path | str = DECKS_DIR) -> list[dict]:
    """Load every deck in ``decks_dir``, skipping none — errors propagate."""
    return [load_deck(path) for path in list_decks(decks_dir)]


# --------------------------------------------------------------------------
# progress
# --------------------------------------------------------------------------

def empty_progress() -> dict:
    return {"version": PROGRESS_VERSION, "cards": {}, "sessions": []}


def progress_key(deck_id: str, card_id: str) -> str:
    """Namespace card ids by deck so two decks can reuse the same id."""
    return f"{deck_id}::{card_id}"


def load_progress(path: Path | str = PROGRESS_FILE) -> dict:
    """Load saved progress, returning a blank record if the file is unusable."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return empty_progress()

    if not isinstance(data, dict):
        return empty_progress()

    data.setdefault("version", PROGRESS_VERSION)
    if not isinstance(data.get("cards"), dict):
        data["cards"] = {}
    if not isinstance(data.get("sessions"), list):
        data["sessions"] = []
    return data


def save_progress(progress: dict, path: Path | str = PROGRESS_FILE) -> Path:
    """Write progress to disk atomically, so a crash cannot truncate it."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    handle, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as tmp_file:
            json.dump(progress, tmp_file, indent=2, ensure_ascii=False)
            tmp_file.write("\n")
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
    return path


def get_card_state(progress: dict, deck_id: str, card_id: str) -> dict | None:
    return progress.get("cards", {}).get(progress_key(deck_id, card_id))


def set_card_state(progress: dict, deck_id: str, card_id: str, state: dict) -> None:
    progress.setdefault("cards", {})[progress_key(deck_id, card_id)] = state


def record_session(progress: dict, session: dict) -> None:
    progress.setdefault("sessions", []).append(session)


def study_days(progress: dict, deck_id: str | None = None) -> list[str]:
    """The dates on which at least one card was reviewed."""
    days = []
    for session in progress.get("sessions", []):
        if deck_id and session.get("deck") != deck_id:
            continue
        if session.get("reviewed", 0) and session.get("date"):
            days.append(session["date"])
    return days


# --------------------------------------------------------------------------
# CSV import
# --------------------------------------------------------------------------

def import_csv(
    csv_path: Path | str,
    decks_dir: Path | str = DECKS_DIR,
    deck_name: str | None = None,
    description: str = "",
) -> Path:
    """Convert a CSV file into a deck JSON file and return the new path.

    Expected columns: ``question`` and ``answer`` (required), plus optional
    ``id`` and ``tags`` (tags separated by ``;``). A header row is required.
    """
    csv_path = Path(csv_path)
    decks_dir = Path(decks_dir)

    try:
        text = csv_path.read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise DeckError(f"CSV file not found: {csv_path}") from exc

    reader = csv.DictReader(text.splitlines())
    fields = {(name or "").strip().lower() for name in (reader.fieldnames or [])}
    if not {"question", "answer"} <= fields:
        raise DeckError("CSV must have a header row with 'question' and 'answer' columns")

    cards = []
    for line_number, row in enumerate(reader, start=2):
        clean = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        question, answer = clean.get("question", ""), clean.get("answer", "")
        if not question and not answer:
            continue
        if not question or not answer:
            raise DeckError(f"{csv_path.name} line {line_number}: question and answer are both required")

        tags = [tag.strip() for tag in clean.get("tags", "").split(";") if tag.strip()]
        cards.append(
            {
                "id": clean.get("id") or fallback_card_id(question),
                "question": question,
                "answer": answer,
                "tags": tags,
            }
        )

    if not cards:
        raise DeckError(f"{csv_path.name} contained no cards")

    deck_name = deck_name or csv_path.stem
    deck = {
        "name": deck_name,
        "description": description or f"Imported from {csv_path.name}",
        "cards": cards,
    }

    decks_dir.mkdir(parents=True, exist_ok=True)
    out_path = decks_dir / f"{slugify(deck_name)}.json"
    out_path.write_text(json.dumps(deck, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out_path


def slugify(value: str) -> str:
    """Turn a deck name into a safe file stem."""
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value.strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "deck"
