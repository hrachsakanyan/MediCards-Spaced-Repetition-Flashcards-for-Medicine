"""Leitner-box spaced repetition scheduling.

Every card lives in one of five numbered boxes. Box 1 is reviewed the most
often, box 5 the least. Answer a card correctly and it moves one box up, so
you will not see it again for a longer stretch. Answer it wrong and it drops
all the way back to box 1, no matter how far it had climbed.

The module is deliberately free of I/O: it takes plain dicts and dates in and
gives plain dicts and dates back, which keeps it easy to test.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

FIRST_BOX = 1
LAST_BOX = 5

#: How many days a card rests in each box before it becomes due again.
BOX_INTERVALS = {
    1: 1,
    2: 2,
    3: 4,
    4: 8,
    5: 16,
}

DATE_FORMAT = "%Y-%m-%d"


# --------------------------------------------------------------------------
# date helpers
# --------------------------------------------------------------------------

def today() -> date:
    """Return the current local date (wrapped so tests can pass their own)."""
    return date.today()


def to_iso(value: date) -> str:
    """Serialise a date as ``YYYY-MM-DD``."""
    return value.strftime(DATE_FORMAT)


def from_iso(value: str) -> date:
    """Parse a ``YYYY-MM-DD`` string back into a :class:`datetime.date`."""
    return datetime.strptime(value, DATE_FORMAT).date()


# --------------------------------------------------------------------------
# box arithmetic
# --------------------------------------------------------------------------

def clamp_box(box: int) -> int:
    """Keep a box number inside the valid range."""
    return max(FIRST_BOX, min(LAST_BOX, int(box)))


def promote(box: int) -> int:
    """Move a card one box up after a correct answer (box 5 stays at 5)."""
    return clamp_box(clamp_box(box) + 1)


def demote(box: int) -> int:
    """Send a card back to box 1 after a wrong answer."""
    return FIRST_BOX


def interval_for(box: int) -> int:
    """Days to wait before a card in ``box`` is asked again."""
    return BOX_INTERVALS[clamp_box(box)]


def next_review(box: int, reviewed_on: date) -> date:
    """The date a card reviewed on ``reviewed_on`` becomes due again."""
    return reviewed_on + timedelta(days=interval_for(box))


# --------------------------------------------------------------------------
# card state
# --------------------------------------------------------------------------

def new_state(due_on: date | None = None) -> dict:
    """Build the progress record of a card that has never been reviewed."""
    due = due_on or today()
    return {
        "box": FIRST_BOX,
        "due": to_iso(due),
        "correct": 0,
        "incorrect": 0,
        "reviews": 0,
        "last_reviewed": None,
    }


def apply_review(state: dict | None, correct: bool, reviewed_on: date | None = None) -> dict:
    """Return a *new* state for a card that was just answered.

    ``state`` may be ``None`` for a card seen for the first time.
    """
    reviewed_on = reviewed_on or today()
    base = dict(new_state(reviewed_on) if state is None else state)

    box = promote(base.get("box", FIRST_BOX)) if correct else demote(base.get("box", FIRST_BOX))

    base["box"] = box
    base["due"] = to_iso(next_review(box, reviewed_on))
    base["reviews"] = int(base.get("reviews", 0)) + 1
    base["correct"] = int(base.get("correct", 0)) + (1 if correct else 0)
    base["incorrect"] = int(base.get("incorrect", 0)) + (0 if correct else 1)
    base["last_reviewed"] = to_iso(reviewed_on)
    return base


def is_due(state: dict | None, on_day: date | None = None) -> bool:
    """True if a card should be reviewed on ``on_day``. New cards are due."""
    if state is None:
        return True
    on_day = on_day or today()
    due = state.get("due")
    if not due:
        return True
    return from_iso(due) <= on_day


def accuracy(state: dict | None) -> float | None:
    """Share of correct answers for a card, or ``None`` if never reviewed."""
    if not state:
        return None
    reviews = int(state.get("reviews", 0))
    if reviews == 0:
        return None
    return int(state.get("correct", 0)) / reviews


# --------------------------------------------------------------------------
# streaks
# --------------------------------------------------------------------------

def compute_streak(study_days, on_day: date | None = None) -> dict:
    """Turn a collection of study days into current / longest streak counts.

    ``study_days`` accepts dates or ISO strings, duplicates included. The
    current streak still counts if the last session was yesterday — the day is
    not over yet.
    """
    on_day = on_day or today()
    days = sorted({from_iso(d) if isinstance(d, str) else d for d in study_days})
    if not days:
        return {"current": 0, "longest": 0, "last_day": None}

    longest = run = 1
    for previous, current in zip(days, days[1:]):
        run = run + 1 if (current - previous).days == 1 else 1
        longest = max(longest, run)

    current_streak = 0
    if days[-1] in (on_day, on_day - timedelta(days=1)):
        seen = set(days)
        cursor = days[-1]
        while cursor in seen:
            current_streak += 1
            cursor -= timedelta(days=1)

    return {
        "current": current_streak,
        "longest": longest,
        "last_day": to_iso(days[-1]),
    }
