"""Flash card logic: PDF text extraction, card parsing, quiz building, answer checking,
and saving cards to a JSON file.

No Flask imports here, so everything can be tested without a browser.
See spec.md for the exact rules.
"""
from __future__ import annotations

import json
import os
import random
import re
import tempfile
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import BinaryIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError as _PypdfReadError

NO_TEXT_MESSAGE = "No text found in this PDF."
NO_TERMS_MESSAGE = (
    "We didn't find terms. They don't match our pattern: "
    '"Term: definition" or "Term - definition".'
)

# Earliest of: a colon followed by whitespace (so "2:30" is not one), or a dash
# (-, en, em) with whitespace on both sides.
_SEPARATOR = re.compile(r"\s*:\s+|\s+[-–—]\s+")
_BULLET = re.compile(r"^[•◦▪*\-–—]\s+")
MAX_TERM_WORDS = 4
QUIZ_LENGTHS = (10, 20)  # R9: the number choices; "all" is always offered too


class PdfReadError(Exception):
    """The uploaded file could not be read as a PDF."""


@dataclass(frozen=True)
class Card:
    term: str
    definition: str


def _collapse(text: str) -> str:
    return " ".join(text.split())


def extract_text(source: str | PathLike | BinaryIO) -> str:
    """Return all text in the PDF (pages joined by newlines). Raises PdfReadError."""
    try:
        reader = PdfReader(source)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except (_PypdfReadError, ValueError, KeyError, TypeError, OSError) as exc:
        raise PdfReadError(str(exc)) from exc


def _is_good_term(term: str) -> bool:
    """R4: starts with a capital letter, at most 4 words, does not end with a digit."""
    return (
        term[0].isupper()
        and len(term.split()) <= MAX_TERM_WORDS
        and not term[-1].isdigit()
    )


def parse_line(line: str) -> Card | None:
    """Return a Card if the line is a card line under R4, else None."""
    line = _BULLET.sub("", line.strip())
    match = _SEPARATOR.search(line)
    if not match:
        return None
    term = _collapse(line[: match.start()])
    definition = _collapse(line[match.end():])
    if not term or not definition:
        return None
    if not _is_good_term(term) or definition.endswith("?"):
        return None
    return Card(term, definition)


def _continues_definition(line: str) -> bool:
    """R7: a following line joins the definition if it starts lowercase or with "("
    and is not blank, a bullet, or a card line of its own."""
    stripped = line.strip()
    return (
        bool(stripped)
        and (stripped[0].islower() or stripped[0] == "(")
        and not _BULLET.match(stripped)
        and parse_line(stripped) is None
    )


def parse_cards(text: str) -> list[Card]:
    """Return the cards in order (R4), with wrapped definitions joined (R7) and
    exact duplicates removed."""
    lines = text.splitlines()
    cards: list[Card] = []
    seen: set[tuple[str, str]] = set()
    i = 0
    while i < len(lines):
        card = parse_line(lines[i])
        i += 1
        if card is None:
            continue
        parts = [card.definition]
        while i < len(lines) and _continues_definition(lines[i]):
            parts.append(_collapse(lines[i]))
            i += 1
        card = Card(card.term, " ".join(parts))
        if card.definition.endswith("?"):  # R4, checked on the full definition
            continue
        key = (card.term.casefold(), card.definition.casefold())
        if key not in seen:
            seen.add(key)
            cards.append(card)
    return cards


def cards_from_pdf(source: str | PathLike | BinaryIO) -> tuple[list[Card], str | None]:
    """Return (cards, message). message is set (and cards empty) when no cards can be made."""
    text = extract_text(source)
    if not text.strip():
        return [], NO_TEXT_MESSAGE
    cards = parse_cards(text)
    if not cards:
        return [], NO_TERMS_MESSAGE
    return cards, None


def build_quiz(
    cards: list[Card], count: int | None = None, rng: random.Random | None = None
) -> list[Card]:
    """Return `count` cards picked at random with no repeats (R9), in random order.
    count None, or bigger than the number of cards, means every card once (R3)."""
    size = len(cards) if count is None else min(count, len(cards))
    return (rng or random).sample(cards, size)


def quiz_length_choices(card_count: int) -> list[int]:
    """R9: the number choices to offer: only those smaller than the card count
    (a choice equal to or above it would just be "all")."""
    return [n for n in QUIZ_LENGTHS if n < card_count]


def normalize(text: str) -> str:
    return _collapse(text).casefold()


def check_answer(answer: str, term: str) -> bool:
    """True when the answer matches the term, ignoring capitals and extra spaces."""
    given = normalize(answer)
    return bool(given) and given == normalize(term)


def save_cards(path: str | PathLike, filename: str, cards: list[Card]) -> None:
    """R10: save the cards and the PDF's filename as JSON. Written to a temp file in the
    same folder and then renamed, so a crash never leaves a half-written file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "filename": filename,
        "cards": [{"term": c.term, "definition": c.definition} for c in cards],
    }
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".cards-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def load_cards(path: str | PathLike) -> tuple[str, list[Card]] | None:
    """R10: return (filename, cards) from a save file, or None if there is no usable
    file (missing, not JSON, wrong shape, or no cards)."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        filename = data["filename"]
        cards = [Card(c["term"], c["definition"]) for c in data["cards"]]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not isinstance(filename, str) or not cards:
        return None
    if not all(isinstance(c.term, str) and isinstance(c.definition, str) for c in cards):
        return None
    return filename, cards
