"""Tests for the Flask web layer, using Flask's test client (no browser)."""
import html
import io
import json
import re
from pathlib import Path

import pytest

from app import DEFAULT_SAVE_PATH, create_app
from flashcards import NO_TERMS_MESSAGE, NO_TEXT_MESSAGE, load_cards

FIXTURES = Path(__file__).parent / "fixtures"

SAMPLE_TERMS = {
    "Cell": "The basic unit of life.",
    "Mitochondria": "Organelle that produces energy for the cell.",
    "Osmosis": "Movement of water across a membrane.",
    "Photosynthesis": "Process plants use to turn light into food, which continues on this wrapped line.",
    "Enzyme": "A protein that speeds up a reaction.",
}
DEFINITION_TO_TERM = {d: t for t, d in SAMPLE_TERMS.items()}


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def upload(client, name, follow=True):
    data = {"pdf": (io.BytesIO((FIXTURES / name).read_bytes()), name)}
    return client.post("/upload", data=data, content_type="multipart/form-data",
                       follow_redirects=follow)


def page(response):
    return html.unescape(response.get_data(as_text=True))


def current_definition(client):
    text = page(client.get("/quiz"))
    match = re.search(r'<p class="definition">(.*?)</p>', text, re.S)
    assert match, text
    return match.group(1).strip()


# ---------- R1 ----------

def test_R1_home_page_has_single_pdf_upload_form(client):
    text = page(client.get("/"))
    assert 'action="/upload"' in text
    assert 'enctype="multipart/form-data"' in text
    inputs = re.findall(r'<input[^>]*type="file"[^>]*>', text)
    assert len(inputs) == 1
    assert "multiple" not in inputs[0]
    assert 'accept=".pdf' in inputs[0]


def test_R1_upload_without_file_shows_error(client):
    response = client.post("/upload", data={}, content_type="multipart/form-data")
    assert "Please choose a PDF file." in page(response)


def test_R1_upload_of_non_pdf_shows_error(client):
    data = {"pdf": (io.BytesIO(b"hello"), "notes.pdf")}
    response = client.post("/upload", data=data, content_type="multipart/form-data")
    assert "Could not read this file as a PDF." in page(response)


def test_R1_successful_upload_redirects_to_cards(client):
    response = upload(client, "sample.pdf", follow=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/cards")


def test_R1_new_upload_replaces_old_cards(client):
    upload(client, "sample.pdf")
    upload(client, "no_terms.pdf")
    assert "Osmosis" not in page(client.get("/cards"))


# ---------- R2 ----------

def test_R2_cards_page_shows_every_term_and_definition(client):
    text = page(upload(client, "sample.pdf"))
    for term, definition in SAMPLE_TERMS.items():
        assert term in text
        assert definition in text
    assert "5 cards" in text


def test_R2_cards_page_without_upload_redirects_home(client):
    response = client.get("/cards")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


# ---------- R3 ----------

def test_R3_quiz_asks_one_question_per_card_then_scores(client):
    upload(client, "sample.pdf")
    seen = []
    for _ in SAMPLE_TERMS:
        definition = current_definition(client)
        seen.append(definition)
        client.post("/quiz", data={"answer": DEFINITION_TO_TERM[definition]})
        client.post("/quiz/next")
    assert sorted(seen) == sorted(SAMPLE_TERMS.values())
    assert "5 / 5 correct" in page(client.get("/quiz"))


def test_R3_quiz_restart_starts_over(client):
    upload(client, "sample.pdf")
    client.post("/quiz", data={"answer": "x"})
    client.post("/quiz/next")
    client.post("/quiz/restart")
    assert "Question 1 of 5" in page(client.get("/quiz"))


def test_R3_quiz_without_upload_redirects_home(client):
    response = client.get("/quiz")
    assert response.status_code == 302


# ---------- R5 ----------

def test_R5_question_shows_definition_but_not_term(client):
    upload(client, "sample.pdf")
    text = page(client.get("/quiz"))
    definition = current_definition(client)
    assert definition in SAMPLE_TERMS.values()
    assert DEFINITION_TO_TERM[definition] not in text
    assert 'name="answer"' in text


def test_R5_correct_answer_ignoring_case_and_spaces(client):
    upload(client, "sample.pdf")
    term = DEFINITION_TO_TERM[current_definition(client)]
    text = page(client.post("/quiz", data={"answer": f"  {term.upper()}  "}))
    assert "Correct!" in text
    assert "Not quite." not in text


def test_R5_wrong_answer_shows_correct_term(client):
    upload(client, "sample.pdf")
    term = DEFINITION_TO_TERM[current_definition(client)]
    text = page(client.post("/quiz", data={"answer": "definitely wrong"}))
    visible = re.sub(r"<[^>]+>", "", text)
    assert "Not quite." in visible
    assert f"The correct answer is: {term}" in visible


def test_R5_wrong_answers_lower_the_score(client):
    upload(client, "sample.pdf")
    for _ in SAMPLE_TERMS:
        client.post("/quiz", data={"answer": "wrong"})
        client.post("/quiz/next")
    assert "0 / 5 correct" in page(client.get("/quiz"))


# ---------- R6 ----------

def test_R6_scanned_pdf_shows_no_text_message(client):
    text = page(upload(client, "scanned.pdf"))
    assert NO_TEXT_MESSAGE in text
    assert 'action="/upload"' in text


def test_R6_pdf_without_terms_shows_pattern_message(client):
    text = page(upload(client, "no_terms.pdf"))
    assert NO_TERMS_MESSAGE in text
    assert 'action="/upload"' in text


# ---------- helpers for R8-R10 ----------

MANY_TERMS = {f"Made-up meaning number {n}.": word for n, word in enumerate([
    "Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf", "Hotel", "India",
    "Juliett", "Kilo", "Lima", "Mike", "November", "Oscar", "Papa", "Quebec", "Romeo",
    "Sierra", "Tango", "Uniform", "Victor", "Whiskey", "Xray", "Yankee",
], start=1)}
GLOSSARY_TERMS = ["Budget Deficit", "Inflation", "Opportunity Cost"]


def make_client(save_path):
    app = create_app(save_path=save_path)
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def save_path(tmp_path):
    return tmp_path / "saved" / "cards.json"


@pytest.fixture
def saved_client(save_path):
    return make_client(save_path)


def start_quiz(client, length="all"):
    return client.post("/quiz/start", data={"length": length}, follow_redirects=True)


def play_round(client, terms_by_definition, wrong=()):
    """Answer every question of the current round; terms in `wrong` get a wrong answer.
    Returns the definitions asked, in order."""
    asked = []
    while True:
        text = page(client.get("/quiz"))
        match = re.search(r'<p class="definition">(.*?)</p>', text, re.S)
        if not match:
            return asked
        definition = match.group(1).strip()
        asked.append(definition)
        term = terms_by_definition[definition]
        client.post("/quiz", data={"answer": "wrong" if term in wrong else term})
        client.post("/quiz/next")


def visible(response):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page(response)))


# ---------- R8: practice missed cards ----------

def test_R8_score_page_offers_practice_of_missed_cards(saved_client):
    upload(saved_client, "sample.pdf")
    start_quiz(saved_client)
    play_round(saved_client, DEFINITION_TO_TERM, wrong={"Cell", "Osmosis"})
    text = visible(saved_client.get("/quiz"))
    assert "3 / 5 correct" in text
    assert "Practice the 2 missed cards" in text
    assert 'action="/quiz/practice"' in page(saved_client.get("/quiz"))


def test_R8_one_missed_card_uses_singular(saved_client):
    upload(saved_client, "sample.pdf")
    start_quiz(saved_client)
    play_round(saved_client, DEFINITION_TO_TERM, wrong={"Enzyme"})
    assert "Practice the 1 missed card" in visible(saved_client.get("/quiz"))


def test_R8_no_practice_offer_when_all_correct(saved_client):
    upload(saved_client, "sample.pdf")
    start_quiz(saved_client)
    play_round(saved_client, DEFINITION_TO_TERM)
    text = visible(saved_client.get("/quiz"))
    assert "5 / 5 correct" in text
    assert "Practice the" not in text


def test_R8_empty_answer_counts_as_missed(saved_client):
    upload(saved_client, "sample.pdf")
    start_quiz(saved_client)
    saved_client.post("/quiz", data={"answer": "   "})
    saved_client.post("/quiz/next")
    play_round(saved_client, DEFINITION_TO_TERM)
    assert "Practice the 1 missed card" in visible(saved_client.get("/quiz"))


def test_R8_practice_round_asks_only_the_missed_cards(saved_client):
    upload(saved_client, "sample.pdf")
    start_quiz(saved_client)
    play_round(saved_client, DEFINITION_TO_TERM, wrong={"Cell", "Osmosis"})
    saved_client.post("/quiz/practice")
    text = visible(saved_client.get("/quiz"))
    assert "Practice round" in text
    assert "Question 1 of 2" in text
    asked = play_round(saved_client, DEFINITION_TO_TERM)
    assert sorted(DEFINITION_TO_TERM[d] for d in asked) == ["Cell", "Osmosis"]
    text = visible(saved_client.get("/quiz"))
    assert "2 / 2 correct" in text
    assert "Practice the" not in text


def test_R8_practice_again_asks_only_cards_still_missed(saved_client):
    upload(saved_client, "sample.pdf")
    start_quiz(saved_client)
    play_round(saved_client, DEFINITION_TO_TERM, wrong={"Cell", "Osmosis", "Enzyme"})
    saved_client.post("/quiz/practice")
    play_round(saved_client, DEFINITION_TO_TERM, wrong={"Osmosis"})
    text = visible(saved_client.get("/quiz"))
    assert "2 / 3 correct" in text
    assert "Practice the 1 missed card" in text
    assert "Stop practicing" in text
    saved_client.post("/quiz/practice")
    asked = play_round(saved_client, DEFINITION_TO_TERM)
    assert [DEFINITION_TO_TERM[d] for d in asked] == ["Osmosis"]


def test_R8_stop_practicing_goes_to_cards_and_ends_the_round(saved_client):
    upload(saved_client, "sample.pdf")
    start_quiz(saved_client)
    play_round(saved_client, DEFINITION_TO_TERM, wrong={"Cell"})
    saved_client.post("/quiz/practice")
    play_round(saved_client, DEFINITION_TO_TERM, wrong={"Cell"})
    response = saved_client.post("/quiz/stop")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/cards")
    assert "How many questions?" in visible(saved_client.get("/quiz"))


def test_R8_practice_without_missed_cards_does_nothing(saved_client):
    upload(saved_client, "sample.pdf")
    start_quiz(saved_client)
    play_round(saved_client, DEFINITION_TO_TERM)
    saved_client.post("/quiz/practice")
    assert "5 / 5 correct" in visible(saved_client.get("/quiz"))


# ---------- R9: choose quiz length ----------

def test_R9_quiz_starts_with_length_choice(saved_client):
    upload(saved_client, "many.pdf")
    response = saved_client.get("/quiz")
    text = visible(response)
    assert "How many questions?" in text
    assert "10 questions" in text
    assert "20 questions" in text
    assert "All 25 cards" in text
    assert 'class="definition"' not in page(response)
    for value in ("10", "20", "all"):
        assert f'name="length" value="{value}"' in page(response)


def test_R9_choices_bigger_than_the_card_count_are_hidden(saved_client):
    upload(saved_client, "sample.pdf")
    text = visible(saved_client.get("/quiz"))
    assert "All 5 cards" in text
    assert "10 questions" not in text
    assert "20 questions" not in text
    assert "This set has 5 cards, so the quiz asks all of them." in text


@pytest.mark.parametrize("length, total", [("10", 10), ("20", 20), ("all", 25)])
def test_R9_quiz_asks_the_chosen_number_of_different_cards(saved_client, length, total):
    upload(saved_client, "many.pdf")
    assert f"Question 1 of {total}" in visible(start_quiz(saved_client, length))
    asked = play_round(saved_client, MANY_TERMS)
    assert len(asked) == total
    assert len(set(asked)) == total
    assert f"{total} / {total} correct" in visible(saved_client.get("/quiz"))


def test_R9_unknown_length_shows_the_choice_again(saved_client):
    upload(saved_client, "many.pdf")
    assert "How many questions?" in visible(start_quiz(saved_client, "7"))


def test_R9_number_bigger_than_card_count_asks_all(saved_client):
    upload(saved_client, "sample.pdf")
    assert "Question 1 of 5" in visible(start_quiz(saved_client, "20"))


def test_R9_new_quiz_after_score_asks_length_again(saved_client):
    upload(saved_client, "many.pdf")
    start_quiz(saved_client, "10")
    play_round(saved_client, MANY_TERMS)
    saved_client.post("/quiz/restart")
    assert "How many questions?" in visible(saved_client.get("/quiz"))


def test_R9_start_without_cards_redirects_home(saved_client):
    response = saved_client.post("/quiz/start", data={"length": "all"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


# ---------- R10: save cards between visits ----------

def test_R10_upload_saves_cards_and_filename_to_file(saved_client, save_path):
    upload(saved_client, "sample.pdf")
    saved = json.loads(save_path.read_text(encoding="utf-8"))
    assert saved["filename"] == "sample.pdf"
    assert {c["term"]: c["definition"] for c in saved["cards"]} == SAMPLE_TERMS


def test_R10_saved_cards_are_there_after_restart(save_path):
    upload(make_client(save_path), "sample.pdf")
    later = make_client(save_path)  # a new server process, a new browser session
    text = visible(later.get("/cards"))
    assert "Osmosis" in text
    assert "sample.pdf" in text
    assert "Question 1 of 5" in visible(start_quiz(later))


def test_R10_home_page_mentions_saved_cards(saved_client):
    assert "saved cards" not in visible(saved_client.get("/"))
    upload(saved_client, "sample.pdf")
    text = visible(saved_client.get("/"))
    assert "You have 5 saved cards from sample.pdf." in text


def test_R10_broken_save_file_starts_with_no_cards(save_path):
    save_path.parent.mkdir(parents=True)
    save_path.write_text("{broken", encoding="utf-8")
    response = make_client(save_path).get("/cards")
    assert response.status_code == 302


def test_R10_first_upload_needs_no_confirmation(saved_client):
    response = upload(saved_client, "sample.pdf", follow=False)
    assert response.headers["Location"].endswith("/cards")


def test_R10_new_upload_asks_before_replacing(saved_client, save_path):
    upload(saved_client, "sample.pdf")
    response = upload(saved_client, "glossary.pdf")
    text = visible(response)
    assert "Replace 5 cards from sample.pdf with 3 cards from glossary.pdf?" in text
    assert 'action="/upload/replace"' in page(response)
    assert 'action="/upload/cancel"' in page(response)
    assert "Replace" in text and "Cancel" in text
    # Nothing is replaced until the student confirms.
    assert "Osmosis" in visible(saved_client.get("/cards"))
    assert json.loads(save_path.read_text(encoding="utf-8"))["filename"] == "sample.pdf"


def test_R10_replace_saves_the_new_cards(saved_client, save_path):
    upload(saved_client, "sample.pdf")
    upload(saved_client, "glossary.pdf")
    response = saved_client.post("/upload/replace")
    assert response.headers["Location"].endswith("/cards")
    text = visible(saved_client.get("/cards"))
    assert "Osmosis" not in text
    for term in GLOSSARY_TERMS:
        assert term in text
    assert load_cards(save_path)[0] == "glossary.pdf"
    assert make_client(save_path).get("/cards").status_code == 200


def test_R10_cancel_keeps_the_old_cards(saved_client, save_path):
    upload(saved_client, "sample.pdf")
    upload(saved_client, "glossary.pdf")
    response = saved_client.post("/upload/cancel")
    assert response.headers["Location"].endswith("/cards")
    text = visible(saved_client.get("/cards"))
    assert "Osmosis" in text
    assert "Inflation" not in text
    assert load_cards(save_path)[0] == "sample.pdf"
    # The cancelled upload is forgotten: a late Replace does nothing.
    saved_client.post("/upload/replace")
    assert "Osmosis" in visible(saved_client.get("/cards"))


def test_R10_replace_without_pending_upload_changes_nothing(saved_client):
    upload(saved_client, "sample.pdf")
    response = saved_client.post("/upload/replace")
    assert response.status_code == 302
    assert "Osmosis" in visible(saved_client.get("/cards"))


def test_R10_replace_ends_the_quiz_in_progress(saved_client):
    upload(saved_client, "sample.pdf")
    start_quiz(saved_client)
    upload(saved_client, "glossary.pdf")
    saved_client.post("/upload/replace")
    assert "How many questions?" in visible(saved_client.get("/quiz"))


@pytest.mark.parametrize("name, body, message", [
    ("no_terms.pdf", None, NO_TERMS_MESSAGE),
    ("scanned.pdf", None, NO_TEXT_MESSAGE),
    ("notes.pdf", b"not a pdf", "Could not read this file as a PDF."),
])
def test_R10_failed_upload_keeps_old_cards_and_says_why(saved_client, save_path, name, body, message):
    upload(saved_client, "sample.pdf")
    before = save_path.read_bytes()
    body = body if body is not None else (FIXTURES / name).read_bytes()
    response = saved_client.post("/upload", data={"pdf": (io.BytesIO(body), name)},
                                 content_type="multipart/form-data")
    assert message in page(response)
    assert "Replace" not in visible(response)
    assert "Osmosis" in visible(saved_client.get("/cards"))
    assert save_path.read_bytes() == before


def test_R10_upload_without_file_keeps_old_cards(saved_client):
    upload(saved_client, "sample.pdf")
    response = saved_client.post("/upload", data={}, content_type="multipart/form-data")
    assert "Please choose a PDF file." in page(response)
    assert "Osmosis" in visible(saved_client.get("/cards"))


def test_R10_too_large_upload_keeps_old_cards(save_path):
    app = create_app(save_path=save_path)
    app.config["TESTING"] = True
    client = app.test_client()
    upload(client, "sample.pdf")
    app.config["MAX_CONTENT_LENGTH"] = 100
    response = upload(client, "glossary.pdf")
    assert response.status_code == 413
    assert "Osmosis" in visible(client.get("/cards"))


def test_R10_failed_upload_keeps_the_quiz_in_progress(saved_client):
    upload(saved_client, "sample.pdf")
    start_quiz(saved_client)
    upload(saved_client, "no_terms.pdf")
    assert "Question 1 of 5" in visible(saved_client.get("/quiz"))


def test_R10_default_save_file_is_outside_the_repo():
    repo = Path(__file__).resolve().parent.parent
    assert repo not in DEFAULT_SAVE_PATH.resolve().parents
