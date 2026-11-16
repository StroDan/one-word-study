"""Tests for the logic module (no Flask). Each test name starts with its requirement ID."""
import io
import random
from pathlib import Path

import pytest

from flashcards import (
    NO_TERMS_MESSAGE,
    NO_TEXT_MESSAGE,
    Card,
    PdfReadError,
    build_quiz,
    cards_from_pdf,
    check_answer,
    extract_text,
    parse_cards,
    parse_line,
)

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "sample.pdf"
NO_TERMS = FIXTURES / "no_terms.pdf"
SCANNED = FIXTURES / "scanned.pdf"

SAMPLE_CARDS = [
    Card("Cell", "The basic unit of life."),
    Card("Mitochondria", "Organelle that produces energy for the cell."),
    Card("Osmosis", "Movement of water across a membrane."),
    Card("Photosynthesis", "Process plants use to turn light into food,"),
    Card("Enzyme", "A protein that speeds up a reaction."),
]


# ---------- R1: one PDF in ----------

def test_R1_extract_text_reads_pdf_from_path():
    assert "Cell: The basic unit of life." in extract_text(SAMPLE)


def test_R1_extract_text_reads_pdf_from_uploaded_stream():
    stream = io.BytesIO(SAMPLE.read_bytes())
    assert "Mitochondria" in extract_text(stream)


def test_R1_non_pdf_raises_pdf_read_error():
    with pytest.raises(PdfReadError):
        extract_text(io.BytesIO(b"this is not a pdf"))


# ---------- R2: cards with term and definition ----------

def test_R2_cards_from_sample_pdf_have_term_and_definition():
    cards, message = cards_from_pdf(SAMPLE)
    assert message is None
    assert cards == SAMPLE_CARDS


def test_R2_cards_keep_pdf_order():
    cards, _ = cards_from_pdf(SAMPLE)
    assert [c.term for c in cards] == [c.term for c in SAMPLE_CARDS]


# ---------- R3: quiz from the cards ----------

def test_R3_quiz_has_every_card_exactly_once():
    quiz = build_quiz(SAMPLE_CARDS, rng=random.Random(1))
    assert sorted(quiz, key=lambda c: c.term) == sorted(SAMPLE_CARDS, key=lambda c: c.term)
    assert len(quiz) == len(SAMPLE_CARDS)


def test_R3_quiz_is_shuffled_and_does_not_change_input():
    original = list(SAMPLE_CARDS)
    orders = {tuple(c.term for c in build_quiz(SAMPLE_CARDS, rng=random.Random(s))) for s in range(10)}
    assert len(orders) > 1
    assert SAMPLE_CARDS == original


def test_R3_quiz_of_no_cards_is_empty():
    assert build_quiz([]) == []


# ---------- R4: only "Term: definition" / "Term - definition" lines ----------

def test_R4_colon_line_is_card():
    assert parse_line("Cell: The basic unit of life.") == Card("Cell", "The basic unit of life.")


def test_R4_colon_without_space_is_card():
    assert parse_line("Cell:The basic unit") == Card("Cell", "The basic unit")


def test_R4_spaced_hyphen_line_is_card():
    assert parse_line("Atom - Smallest unit of matter") == Card("Atom", "Smallest unit of matter")


@pytest.mark.parametrize("dash", ["–", "—"])
def test_R4_spaced_en_and_em_dash_are_separators(dash):
    assert parse_line(f"Atom {dash} Smallest unit") == Card("Atom", "Smallest unit")


def test_R4_hyphen_inside_word_is_not_separator():
    assert parse_line("self-esteem is how you see yourself") is None


def test_R4_hyphenated_term_keeps_its_hyphen():
    assert parse_line("Self-esteem - How you see yourself") == Card("Self-esteem", "How you see yourself")


def test_R4_earliest_separator_wins():
    assert parse_line("Ratio - written as 3:4") == Card("Ratio", "written as 3:4")
    assert parse_line("Note: see page 2 - review") == Card("Note", "see page 2 - review")


def test_R4_line_without_separator_is_not_card():
    assert parse_line("This sentence has no separator at all.") is None


@pytest.mark.parametrize("line", [": definition only", "Term:", "Term -  ", "   ", ""])
def test_R4_empty_term_or_definition_is_not_card(line):
    assert parse_line(line) is None


def test_R4_bullet_marker_is_removed():
    assert parse_line("• Enzyme: A protein") == Card("Enzyme", "A protein")
    assert parse_line("- Enzyme: A protein") == Card("Enzyme", "A protein")


def test_R4_whitespace_inside_parts_is_collapsed():
    assert parse_line("  Big   word :  a   long  meaning ") == Card("Big word", "a long meaning")


def test_R4_wrapped_continuation_line_is_ignored():
    text = "Photosynthesis: Process plants use,\nwhich continues here."
    assert parse_cards(text) == [Card("Photosynthesis", "Process plants use,")]


def test_R4_heading_like_line_still_becomes_card():
    assert parse_line("Chapter 3: Cells") == Card("Chapter 3", "Cells")


def test_R4_exact_duplicates_kept_once():
    text = "Cell: Unit of life\ncell :  unit of  life\nCell: Something else"
    assert parse_cards(text) == [Card("Cell", "Unit of life"), Card("Cell", "Something else")]


# ---------- R5: answer checking ----------

def test_R5_exact_answer_is_correct():
    assert check_answer("Osmosis", "Osmosis")


def test_R5_capitals_do_not_matter():
    assert check_answer("oSMOSIS", "Osmosis")


def test_R5_extra_spaces_do_not_matter():
    assert check_answer("   cell    wall  ", "Cell wall")


def test_R5_wrong_answer_is_incorrect():
    assert not check_answer("Diffusion", "Osmosis")


def test_R5_empty_answer_is_incorrect():
    assert not check_answer("   ", "Osmosis")


def test_R5_missing_inner_space_is_incorrect():
    assert not check_answer("cellwall", "Cell wall")


# ---------- R6: messages ----------

def test_R6_messages_have_exact_wording():
    assert NO_TEXT_MESSAGE == "No text found in this PDF."
    assert NO_TERMS_MESSAGE == (
        "We didn't find terms. They don't match our pattern: "
        '"Term: definition" or "Term - definition".'
    )


def test_R6_scanned_pdf_gives_no_text_message():
    assert cards_from_pdf(SCANNED) == ([], NO_TEXT_MESSAGE)


def test_R6_text_without_terms_gives_no_terms_message():
    assert cards_from_pdf(NO_TERMS) == ([], NO_TERMS_MESSAGE)
