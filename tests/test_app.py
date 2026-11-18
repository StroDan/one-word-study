"""Tests for the Flask web layer, using Flask's test client (no browser)."""
import html
import io
import json
import re
from datetime import datetime
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
def client(tmp_path):
    app = create_app(save_path=tmp_path / "cards.json")  # R10: never touch the real save file
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


def test_R1_new_upload_becomes_the_current_cards(client):
    # Changed with R10: a good upload is added as a new set without asking and becomes
    # the current one; the old set stays in the history (R11).
    upload(client, "sample.pdf")
    upload(client, "glossary.pdf")
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
    start_quiz(client, "all")  # R9: the student picks the length first
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
    start_quiz(client, "all")
    client.post("/quiz", data={"answer": "x"})
    client.post("/quiz/next")
    client.post("/quiz/restart")
    # R9: starting over asks for the length again before question 1.
    assert "How many questions?" in page(client.get("/quiz"))
    assert "Question 1 of 5" in page(start_quiz(client, "all"))


def test_R3_quiz_without_upload_redirects_home(client):
    response = client.get("/quiz")
    assert response.status_code == 302


# ---------- R5 ----------

def test_R5_question_shows_definition_but_not_term(client):
    upload(client, "sample.pdf")
    start_quiz(client, "all")  # R9
    text = page(client.get("/quiz"))
    definition = current_definition(client)
    assert definition in SAMPLE_TERMS.values()
    assert DEFINITION_TO_TERM[definition] not in text
    assert 'name="answer"' in text


def test_R5_correct_answer_ignoring_case_and_spaces(client):
    upload(client, "sample.pdf")
    start_quiz(client, "all")  # R9
    term = DEFINITION_TO_TERM[current_definition(client)]
    text = page(client.post("/quiz", data={"answer": f"  {term.upper()}  "}))
    assert "Correct!" in text
    assert "Not quite." not in text


def test_R5_wrong_answer_shows_correct_term(client):
    upload(client, "sample.pdf")
    start_quiz(client, "all")  # R9
    term = DEFINITION_TO_TERM[current_definition(client)]
    text = page(client.post("/quiz", data={"answer": "definitely wrong"}))
    visible = re.sub(r"<[^>]+>", "", text)
    assert "Not quite." in visible
    assert f"The correct answer is: {term}" in visible


def test_R5_wrong_answers_lower_the_score(client):
    upload(client, "sample.pdf")
    start_quiz(client, "all")  # R9
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

def test_R10_saved_cards_are_there_after_restart(save_path):
    upload(make_client(save_path), "sample.pdf")
    later = make_client(save_path)  # a new server process, a new browser session
    text = visible(later.get("/cards"))
    assert "Osmosis" in text
    assert "sample.pdf" in text
    assert "Question 1 of 5" in visible(start_quiz(later))


def test_R10_home_page_mentions_the_current_cards(saved_client):
    # Changed with R11: there can be many saved sets, so the home page names the current one.
    assert "You're studying" not in visible(saved_client.get("/"))
    upload(saved_client, "sample.pdf")
    text = visible(saved_client.get("/"))
    assert "You're studying 5 cards from sample.pdf." in text


def test_R10_broken_save_file_starts_with_no_cards(save_path):
    save_path.parent.mkdir(parents=True)
    save_path.write_text("{broken", encoding="utf-8")
    response = make_client(save_path).get("/cards")
    assert response.status_code == 302


def test_R10_first_upload_needs_no_confirmation(saved_client):
    response = upload(saved_client, "sample.pdf", follow=False)
    assert response.headers["Location"].endswith("/cards")


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


# ---------- R10 (changed) and R11: every upload is a saved set; card history ----------

class FakeClock:
    """Returns Nov 1 2026 09:00 on the first call, then one day later on each call."""

    def __init__(self):
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return datetime(2026, 11, self.calls, 9, 0, 0)


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def history_app(save_path, clock):
    app = create_app(save_path=save_path, clock=clock)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def hc(history_app):
    """A browser on the history app."""
    return history_app.test_client()


def upload_as(client, fixture, name, follow=True):
    data = {"pdf": (io.BytesIO((FIXTURES / fixture).read_bytes()), name)}
    return client.post("/upload", data=data, content_type="multipart/form-data",
                       follow_redirects=follow)


def saved_sets(save_path):
    return json.loads(save_path.read_text(encoding="utf-8"))["sets"]


def set_id(save_path, filename):
    [found] = [s["id"] for s in saved_sets(save_path) if s["filename"] == filename]
    return found


def history_rows(client):
    """The history list on the home page, as visible text per row."""
    text = page(client.get("/"))
    rows = re.findall(r'<li class="set[^"]*">(.*?)</li>', text, re.S)
    return [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", row)).strip() for row in rows]


def test_R10_upload_saves_the_set_with_its_date(hc, save_path):
    upload(hc, "sample.pdf")
    [saved] = saved_sets(save_path)
    assert saved["filename"] == "sample.pdf"
    assert saved["uploaded"] == "2026-11-01T09:00:00"
    assert {c["term"]: c["definition"] for c in saved["cards"]} == SAMPLE_TERMS
    assert re.fullmatch(r"[0-9a-f]{32}", saved["id"])


def test_R10_new_upload_is_added_without_asking(hc, save_path):
    upload(hc, "sample.pdf")
    response = upload(hc, "glossary.pdf", follow=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/cards")
    text = visible(hc.get("/cards"))
    for term in GLOSSARY_TERMS:
        assert term in text
    assert "Osmosis" not in text
    assert [s["filename"] for s in saved_sets(save_path)] == ["glossary.pdf", "sample.pdf"]


def test_R10_replace_warning_and_its_routes_are_gone(hc):
    upload(hc, "sample.pdf")
    text = visible(upload(hc, "glossary.pdf"))
    assert "Replace" not in text
    assert hc.post("/upload/replace").status_code == 404
    assert hc.post("/upload/cancel").status_code == 404


def test_R10_failed_upload_keeps_every_set_and_the_current_one(hc, save_path):
    upload_as(hc, "sample.pdf", "a.pdf")
    upload_as(hc, "glossary.pdf", "b.pdf")
    hc.post(f"/sets/{set_id(save_path, 'a.pdf')}/study")
    before = save_path.read_bytes()
    response = upload(hc, "no_terms.pdf")
    assert NO_TERMS_MESSAGE in page(response)
    assert save_path.read_bytes() == before
    assert "Osmosis" in visible(hc.get("/cards"))


def test_R10_old_one_set_save_file_is_loaded_as_a_set(save_path):
    save_path.parent.mkdir(parents=True)
    old = {"filename": "unit.pdf",
           "cards": [{"term": t, "definition": d} for t, d in SAMPLE_TERMS.items()]}
    save_path.write_text(json.dumps(old), encoding="utf-8")
    client = make_client(save_path)
    assert "Osmosis" in visible(client.get("/cards"))
    assert "You're studying 5 cards from unit.pdf." in visible(client.get("/"))
    [row] = history_rows(client)
    assert "unit.pdf" in row and "5 cards" in row
    # Kept, not lost, when the next PDF is added.
    upload(client, "glossary.pdf")
    assert [s["filename"] for s in saved_sets(save_path)] == ["glossary.pdf", "unit.pdf"]


def test_R11_home_page_lists_sets_newest_first_with_name_date_and_count(hc):
    assert "Your card sets" not in visible(hc.get("/"))
    upload(hc, "sample.pdf")
    upload(hc, "glossary.pdf")
    assert "Your card sets" in visible(hc.get("/"))
    rows = history_rows(hc)
    assert len(rows) == 2
    assert "glossary.pdf" in rows[0] and "Nov 2, 2026" in rows[0] and "3 cards" in rows[0]
    assert "sample.pdf" in rows[1] and "Nov 1, 2026" in rows[1] and "5 cards" in rows[1]


def test_R11_one_card_uses_singular(save_path):
    save_path.parent.mkdir(parents=True)
    save_path.write_text(json.dumps({"sets": [{
        "id": "a" * 32, "filename": "one.pdf", "uploaded": "2026-11-01T09:00:00",
        "cards": [{"term": "Cell", "definition": "The basic unit of life."}]}]}), encoding="utf-8")
    [row] = history_rows(make_client(save_path))
    assert "1 card" in row and "1 cards" not in row


def test_R11_current_set_is_marked_in_the_list(hc, save_path):
    upload(hc, "sample.pdf")
    upload(hc, "glossary.pdf")
    rows = history_rows(hc)
    assert "Studying now" in rows[0] and "Studying now" not in rows[1]
    assert "You're studying 3 cards from glossary.pdf." in visible(hc.get("/"))


def test_R11_picking_a_set_makes_it_current(hc, save_path):
    upload(hc, "sample.pdf")
    upload(hc, "glossary.pdf")
    response = hc.post(f"/sets/{set_id(save_path, 'sample.pdf')}/study")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/cards")
    assert "Osmosis" in visible(hc.get("/cards"))
    assert "Question 1 of 5" in visible(start_quiz(hc))
    # Picking does not change the order of the list.
    rows = history_rows(hc)
    assert "glossary.pdf" in rows[0] and "Studying now" in rows[1]


def test_R11_each_row_has_study_and_delete(hc, save_path):
    upload(hc, "sample.pdf")
    text = page(hc.get("/"))
    sid = set_id(save_path, "sample.pdf")
    assert f'action="/sets/{sid}/study"' in text
    assert f'href="/sets/{sid}/delete"' in text


def test_R11_picking_another_set_ends_the_quiz_but_picking_the_same_keeps_it(hc, save_path):
    upload(hc, "sample.pdf")
    upload(hc, "glossary.pdf")
    start_quiz(hc)
    hc.post(f"/sets/{set_id(save_path, 'glossary.pdf')}/study")
    assert "Question 1 of 3" in visible(hc.get("/quiz"))
    hc.post(f"/sets/{set_id(save_path, 'sample.pdf')}/study")
    assert "How many questions?" in visible(hc.get("/quiz"))


def test_R11_picking_an_unknown_set_changes_nothing(hc):
    upload(hc, "sample.pdf")
    response = hc.post("/sets/nope/study")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    assert "Osmosis" in visible(hc.get("/cards"))


def test_R11_current_set_is_per_browser(history_app, save_path):
    first, second = history_app.test_client(), history_app.test_client()
    upload(first, "sample.pdf")
    upload(second, "glossary.pdf")
    assert "Osmosis" in visible(first.get("/cards"))
    assert "Inflation" in visible(second.get("/cards"))


def test_R11_after_restart_the_newest_set_is_current(hc, save_path):
    upload(hc, "sample.pdf")
    upload(hc, "glossary.pdf")
    hc.post(f"/sets/{set_id(save_path, 'sample.pdf')}/study")
    later = make_client(save_path)
    assert "Inflation" in visible(later.get("/cards"))


def test_R11_delete_asks_first_and_deletes_nothing_yet(hc, save_path):
    upload(hc, "sample.pdf")
    sid = set_id(save_path, "sample.pdf")
    response = hc.get(f"/sets/{sid}/delete")
    assert response.status_code == 200
    text = visible(response)
    assert "Delete sample.pdf (5 cards)?" in text
    assert f'action="/sets/{sid}/delete"' in page(response)
    assert "Delete" in text and "Cancel" in text
    assert re.search(r'<a [^>]*href="/"[^>]*>\s*Cancel', page(response))
    assert len(saved_sets(save_path)) == 1


def test_R11_confirmed_delete_removes_the_set(hc, save_path):
    upload(hc, "sample.pdf")
    upload(hc, "glossary.pdf")
    response = hc.post(f"/sets/{set_id(save_path, 'sample.pdf')}/delete")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    assert [s["filename"] for s in saved_sets(save_path)] == ["glossary.pdf"]
    assert "sample.pdf" not in visible(hc.get("/"))
    assert "sample.pdf" not in visible(make_client(save_path).get("/"))


def test_R11_deleting_the_current_set_makes_the_newest_current_and_ends_its_quiz(hc, save_path):
    upload_as(hc, "many.pdf", "old.pdf")
    upload(hc, "glossary.pdf")
    upload(hc, "sample.pdf")
    start_quiz(hc)
    hc.post(f"/sets/{set_id(save_path, 'sample.pdf')}/delete")
    assert "Inflation" in visible(hc.get("/cards"))
    assert "How many questions?" in visible(hc.get("/quiz"))


def test_R11_deleting_the_last_set_leaves_no_cards(hc, save_path):
    upload(hc, "sample.pdf")
    hc.post(f"/sets/{set_id(save_path, 'sample.pdf')}/delete")
    assert saved_sets(save_path) == []
    assert hc.get("/cards").headers["Location"].endswith("/")
    assert hc.get("/quiz").headers["Location"].endswith("/")
    assert "Your card sets" not in visible(hc.get("/"))


def test_R11_deleting_an_unknown_set_changes_nothing(hc, save_path):
    upload(hc, "sample.pdf")
    before = save_path.read_bytes()
    assert hc.get("/sets/nope/delete").headers["Location"].endswith("/")
    assert hc.post("/sets/nope/delete").headers["Location"].endswith("/")
    assert save_path.read_bytes() == before


def test_R11_only_the_last_ten_sets_are_kept(hc, save_path):
    for n in range(1, 12):
        upload_as(hc, "sample.pdf", f"unit{n}.pdf")
    names = [s["filename"] for s in saved_sets(save_path)]
    assert names == [f"unit{n}.pdf" for n in range(11, 1, -1)]
    assert len(history_rows(hc)) == 10


def test_R11_same_file_name_updates_the_set_and_moves_it_to_the_top(hc, save_path):
    upload_as(hc, "sample.pdf", "unit.pdf")
    old_id = set_id(save_path, "unit.pdf")
    upload(hc, "many.pdf")
    upload_as(hc, "glossary.pdf", "unit.pdf")
    sets = saved_sets(save_path)
    assert [s["filename"] for s in sets] == ["unit.pdf", "many.pdf"]
    assert sets[0]["id"] == old_id
    assert sets[0]["uploaded"] == "2026-11-03T09:00:00"
    assert [c["term"] for c in sets[0]["cards"]] == GLOSSARY_TERMS
    rows = history_rows(hc)
    assert len(rows) == 2 and "Nov 3, 2026" in rows[0] and "3 cards" in rows[0]


def test_R11_same_file_name_ends_a_quiz_on_that_set_in_another_browser(history_app, save_path):
    first, second = history_app.test_client(), history_app.test_client()
    upload_as(first, "sample.pdf", "unit.pdf")
    second.post(f"/sets/{set_id(save_path, 'unit.pdf')}/study")
    start_quiz(second)
    upload_as(first, "glossary.pdf", "unit.pdf")
    assert "How many questions?" in visible(second.get("/quiz"))
    assert "Inflation" in visible(second.get("/cards"))
