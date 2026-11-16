"""Flash card logic: PDF text extraction, card parsing, quiz building, answer checking.

No Flask imports here, so everything can be tested without a browser.
See spec.md for the exact rules.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass
from os import PathLike
from typing import BinaryIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError as _PypdfReadError

NO_TEXT_MESSAGE = "No text found in this PDF."
NO_TERMS_MESSAGE = (
    "We didn't find terms. They don't match our pattern: "
    '"Term: definition" or "Term - definition".'
)

# Earliest of: a colon (spaces optional) or a dash (-, en, em) with whitespace on both sides.
_SEPARATOR = re.compile(r"\s*:\s*|\s+[-–—]\s+")
_BULLET = re.compile(r"^[•◦▪*\-–—]\s+")


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


def parse_line(line: str) -> Card | None:
    """Return a Card if the line is `Term: definition` or `Term - definition`, else None."""
    line = _BULLET.sub("", line.strip())
    match = _SEPARATOR.search(line)
    if not match:
        return None
    term = _collapse(line[: match.start()])
    definition = _collapse(line[match.end():])
    if not term or not definition:
        return None
    return Card(term, definition)


def parse_cards(text: str) -> list[Card]:
    """Return one card per matching line, in order, without exact duplicates."""
    cards: list[Card] = []
    seen: set[tuple[str, str]] = set()
    for line in text.splitlines():
        card = parse_line(line)
        if card is None:
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


def build_quiz(cards: list[Card], rng: random.Random | None = None) -> list[Card]:
    """Return a shuffled copy of the cards: one question per card."""
    quiz = list(cards)
    (rng or random).shuffle(quiz)
    return quiz


def normalize(text: str) -> str:
    return _collapse(text).casefold()


def check_answer(answer: str, term: str) -> bool:
    """True when the answer matches the term, ignoring capitals and extra spaces."""
    given = normalize(answer)
    return bool(given) and given == normalize(term)
