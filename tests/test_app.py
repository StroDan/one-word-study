"""Tests for the Flask web layer, using Flask's test client (no browser)."""
import html
import io
import re
from pathlib import Path

import pytest

from app import create_app
from flashcards import NO_TERMS_MESSAGE, NO_TEXT_MESSAGE

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
