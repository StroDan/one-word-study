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

# Earliest of: a colon followed by whitespace (so "2:30" is not one), or a dash
# (-, en, em) with whitespace on both sides.
_SEPARATOR = re.compile(r"\s*:\s+|\s+[-–—]\s+")
_BULLET = re.compile(r"^[•◦▪*\-–—]\s+")
MAX_TERM_WORDS = 4


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
