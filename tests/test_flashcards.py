"""Tests for the logic module (no Flask). Each test name starts with its requirement ID."""
import io
import json
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
    load_cards,
    parse_cards,
    parse_line,
    quiz_length_choices,
    save_cards,
)

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "sample.pdf"
NO_TERMS = FIXTURES / "no_terms.pdf"
SCANNED = FIXTURES / "scanned.pdf"
SLIDES = FIXTURES / "slides.pdf"
GLOSSARY = FIXTURES / "glossary.pdf"

SAMPLE_CARDS = [
    Card("Cell", "The basic unit of life."),
    Card("Mitochondria", "Organelle that produces energy for the cell."),
    Card("Osmosis", "Movement of water across a membrane."),
    Card("Photosynthesis", "Process plants use to turn light into food, which continues on this wrapped line."),
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


# ---------- R9: choose quiz length ----------

MANY_CARDS = [Card(f"Term {chr(65 + i)}", f"Meaning {i}") for i in range(25)]


def test_R9_quiz_of_ten_picks_ten_different_cards():
    quiz = build_quiz(MANY_CARDS, count=10, rng=random.Random(7))
    assert len(quiz) == 10
    assert len(set(quiz)) == 10
    assert set(quiz) <= set(MANY_CARDS)


def test_R9_same_seed_gives_same_quiz():
    first = build_quiz(MANY_CARDS, count=20, rng=random.Random(42))
    second = build_quiz(MANY_CARDS, count=20, rng=random.Random(42))
    assert first == second
    assert len(set(first)) == 20


def test_R9_quiz_cards_are_picked_at_random():
    picks = {frozenset(build_quiz(MANY_CARDS, count=10, rng=random.Random(s))) for s in range(10)}
    assert len(picks) > 1


def test_R9_count_none_asks_every_card_once():
    quiz = build_quiz(MANY_CARDS, count=None, rng=random.Random(3))
    assert sorted(quiz, key=lambda c: c.term) == sorted(MANY_CARDS, key=lambda c: c.term)


def test_R9_count_bigger_than_cards_asks_every_card_once():
    quiz = build_quiz(SAMPLE_CARDS, count=10, rng=random.Random(3))
    assert sorted(quiz, key=lambda c: c.term) == sorted(SAMPLE_CARDS, key=lambda c: c.term)


def test_R9_build_quiz_does_not_change_input():
    original = list(MANY_CARDS)
    build_quiz(MANY_CARDS, count=10, rng=random.Random(1))
    assert MANY_CARDS == original


@pytest.mark.parametrize("count, expected", [
    (25, [10, 20]), (21, [10, 20]), (20, [10]), (15, [10]), (11, [10]), (10, []), (5, []), (1, []),
])
def test_R9_number_choices_are_only_those_smaller_than_the_card_count(count, expected):
    assert quiz_length_choices(count) == expected


# ---------- R10: save cards between visits ----------

def test_R10_save_file_is_readable_json(tmp_path):
    path = tmp_path / "cards.json"
    save_cards(path, "sample.pdf", SAMPLE_CARDS[:1])
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "filename": "sample.pdf",
        "cards": [{"term": "Cell", "definition": "The basic unit of life."}],
    }


def test_R10_save_creates_missing_folder_and_leaves_no_temp_files(tmp_path):
    path = tmp_path / "new folder" / "cards.json"
    save_cards(path, "a.pdf", SAMPLE_CARDS)
    assert [f.name for f in path.parent.iterdir()] == ["cards.json"]


def test_R10_saving_again_replaces_the_old_cards(tmp_path):
    path = tmp_path / "cards.json"
    save_cards(path, "a.pdf", SAMPLE_CARDS)
    save_cards(path, "b.pdf", SAMPLE_CARDS[:2])
    assert load_cards(path) == ("b.pdf", SAMPLE_CARDS[:2])


def test_R10_non_ascii_text_survives_saving(tmp_path):
    path = tmp_path / "cards.json"
    cards = [Card("Ölçü", "Größe – “quoted” • bullet")]
    save_cards(path, "été.pdf", cards)
    assert load_cards(path) == ("été.pdf", cards)


def test_R10_missing_file_loads_nothing(tmp_path):
    assert load_cards(tmp_path / "nothing.json") is None


@pytest.mark.parametrize("content", [
    "not json",
    "",
    "[]",
    '{"filename": "a.pdf"}',
    '{"filename": "a.pdf", "cards": [{"term": "Cell"}]}',
    '{"filename": 3, "cards": []}',
    '{"filename": "a.pdf", "cards": []}',
])
def test_R10_broken_or_empty_file_loads_nothing(tmp_path, content):
    path = tmp_path / "cards.json"
    path.write_text(content, encoding="utf-8")
    assert load_cards(path) is None


# ---------- R4: only "Term: definition" / "Term - definition" lines ----------

def test_R4_colon_line_is_card():
    assert parse_line("Cell: The basic unit of life.") == Card("Cell", "The basic unit of life.")


def test_R4_colon_without_space_after_is_not_card():
    # Changed in R4: a colon only separates when whitespace follows it.
    assert parse_line("Cell:The basic unit") is None


def test_R4_space_before_colon_is_still_allowed():
    assert parse_line("Cell : The basic unit") == Card("Cell", "The basic unit")


def test_R4_time_with_colon_is_not_card():
    assert parse_line("Mondays 2:30-5:00 pm Josh Cray") is None


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


def test_R4_term_must_start_with_capital_letter():
    assert parse_line("constrained: that is, limited by workers") is None


def test_R4_term_of_four_words_is_card():
    assert parse_line("Bank for International Settlements: A bank") == Card(
        "Bank for International Settlements", "A bank"
    )


def test_R4_term_of_five_words_is_not_card():
    assert parse_line("Quantity demanded falls when price – the law of demand") is None


@pytest.mark.parametrize("line", ["Chapter 3: Cells", "September 14 - November 17"])
def test_R4_term_ending_with_number_is_not_card(line):
    assert parse_line(line) is None


def test_R4_heading_like_line_without_number_still_becomes_card():
    assert parse_line("Chapter three: Cells") == Card("Chapter three", "Cells")


def test_R4_question_definition_is_not_card():
    assert parse_line("Labor markets – how are wages set?") is None


def test_R4_question_is_checked_after_R7_continuation():
    assert parse_cards("Big question: what happens\nwhen prices rise?") == []


def test_R4_exact_duplicates_kept_once():
    # Second line differs only in capitals and spacing. (Its term must start with a
    # capital letter now, or R4 rejects it and R7 joins it to the first definition.)
    text = "Cell: Unit of life\nCELL :  unit of  life\nCell: Something else"
    assert parse_cards(text) == [Card("Cell", "Unit of life"), Card("Cell", "Something else")]


# ---------- R7: definitions that continue onto the next lines ----------

def test_R7_lowercase_lines_continue_the_definition():
    text = "Supply – the amount sellers\nare willing to sell,\nholding other things equal."
    assert parse_cards(text) == [
        Card("Supply", "the amount sellers are willing to sell, holding other things equal.")
    ]


def test_R7_capitalized_line_ends_the_definition():
    text = "Demand – the amount buyers want\nDemand and Elasticity\nmore text"
    assert parse_cards(text) == [Card("Demand", "the amount buyers want")]


def test_R7_blank_line_ends_the_definition():
    text = "Inflation: A rise in prices\n   \nand this is not part of it"
    assert parse_cards(text) == [Card("Inflation", "A rise in prices")]


@pytest.mark.parametrize("bullet", ["•", "-", "*"])
def test_R7_bullet_line_ends_the_definition(bullet):
    text = f"Supply – the amount sellers sell\n{bullet} also a separate point"
    assert parse_cards(text) == [Card("Supply", "the amount sellers sell")]


def test_R7_new_card_line_starts_a_new_card():
    text = "Cell: the unit of life\nAtom: the unit of matter"
    assert parse_cards(text) == [Card("Cell", "the unit of life"), Card("Atom", "the unit of matter")]


def test_R7_continuation_whitespace_is_collapsed():
    text = "Cell: the   unit\n   of    life"
    assert parse_cards(text) == [Card("Cell", "the unit of life")]


def test_R7_line_starting_with_parenthesis_continues_the_definition():
    text = "Osmosis: movement of water across a membrane\n(from low to high concentration)"
    assert parse_cards(text) == [
        Card("Osmosis", "movement of water across a membrane (from low to high concentration)")
    ]


def test_R7_parenthesis_line_with_leading_spaces_and_more_lines_after_it():
    text = "Enzyme: A protein\n   (a catalyst)\nthat speeds up reactions\nAtom: Unit of matter"
    assert parse_cards(text) == [
        Card("Enzyme", "A protein (a catalyst) that speeds up reactions"),
        Card("Atom", "Unit of matter"),
    ]


def test_R7_parenthesis_line_with_colon_is_still_a_continuation():
    # "(see also" does not start with a capital letter, so the line is never a card of its own.
    assert parse_cards("Osmosis: movement of water\n(see also: Diffusion)") == [
        Card("Osmosis", "movement of water (see also: Diffusion)")
    ]


def test_R7_blank_line_still_ends_before_a_parenthesis_line():
    assert parse_cards("Osmosis: movement of water\n\n(not part of it)") == [
        Card("Osmosis", "movement of water")
    ]


def test_R4_R7_slides_style_pdf():
    cards, message = cards_from_pdf(SLIDES)
    assert message is None
    assert cards == [
        Card("Supply", "the amount of a good that sellers are willing and able to sell "
                       "at each price, holding other things equal."),
        Card("Demand", "the amount buyers want at each price"),
        Card("Price elasticity", "how much quantity responds to a change in price"),
    ]


def test_R4_R7_glossary_style_pdf():
    cards, message = cards_from_pdf(GLOSSARY)
    assert message is None
    assert cards == [
        Card("Budget Deficit", "The amount by which spending is greater than revenue in one year."),
        Card("Inflation", "A general rise in prices. It lowers what money can buy."),
        Card("Opportunity Cost", "The value of the next best choice not taken."),
    ]


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
