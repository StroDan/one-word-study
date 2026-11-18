"""Flask web layer. All study logic lives in flashcards.py."""
from __future__ import annotations

import os
import uuid
from pathlib import Path

from flask import Flask, redirect, render_template, request, session, url_for

from flashcards import (
    PdfReadError,
    build_quiz,
    cards_from_pdf,
    check_answer,
    load_cards,
    save_cards,
)

MAX_UPLOAD_MB = 50
NO_FILE_MESSAGE = "Please choose a PDF file."
BAD_PDF_MESSAGE = "Could not read this file as a PDF."
TOO_LARGE_MESSAGE = f"This PDF is too large (limit is {MAX_UPLOAD_MB} MB)."
# R10: outside the repository, so saved cards are never committed.
DEFAULT_SAVE_PATH = Path.home() / ".one-word-study" / "cards.json"


def create_app(save_path: str | os.PathLike | None = None) -> Flask:
    app = Flask(__name__)
    app.secret_key = os.urandom(32)  # local only; sessions reset when the server restarts
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
    save_path = Path(save_path) if save_path is not None else DEFAULT_SAVE_PATH

    # R10: the saved cards, shared by every browser tab. "version" goes up on each
    # replace, so a quiz built from older cards is dropped.
    loaded = load_cards(save_path)
    deck = {"filename": loaded[0] if loaded else None,
            "cards": loaded[1] if loaded else [],
            "version": 0}

    # Per-browser state kept in memory:
    # {session id: {"version", "quiz", "index", "score", "feedback", "pending"}}
    store: dict[str, dict] = {}

    def session_state() -> dict:
        sid = session.setdefault("sid", uuid.uuid4().hex)
        data = store.setdefault(sid, {"version": None, "quiz": None, "pending": None})
        if data["version"] != deck["version"]:
            data.update(version=deck["version"], quiz=None)
        return data

    def state() -> dict | None:
        """This browser's quiz state, or None when there are no cards yet."""
        if not deck["cards"]:
            return None
        data = session_state()
        if data["quiz"] is None:
            new_quiz(data)
        return data

    def new_quiz(data: dict) -> None:
        data.update(quiz=build_quiz(deck["cards"]), index=0, score=0, feedback=None)

    def upload_page(message: str):
        return render_template("index.html", message=message, deck=deck)

    @app.get("/")
    def index():
        return render_template("index.html", deck=deck)

    @app.post("/upload")
    def upload():
        # R10: read the new PDF first; the saved cards stay unless it is usable.
        file = request.files.get("pdf")
        if file is None or not file.filename:
            return upload_page(NO_FILE_MESSAGE), 400
        try:
            cards, message = cards_from_pdf(file.stream)
        except PdfReadError:
            return upload_page(BAD_PDF_MESSAGE), 400
        if message:
            return upload_page(message)
        pending = {"filename": file.filename, "cards": cards}
        if not deck["cards"]:
            replace_deck(pending)
            return redirect(url_for("cards"))
        session_state()["pending"] = pending
        return render_template("confirm.html", old=deck, new=pending)

    @app.post("/upload/replace")
    def replace():
        data = session_state()
        if data["pending"] is not None:
            replace_deck(data["pending"])
        return redirect(url_for("cards"))

    @app.post("/upload/cancel")
    def cancel():
        session_state()["pending"] = None
        return redirect(url_for("cards"))

    def replace_deck(new: dict) -> None:
        save_cards(save_path, new["filename"], new["cards"])
        deck.update(filename=new["filename"], cards=new["cards"], version=deck["version"] + 1)
        session_state()["pending"] = None

    @app.errorhandler(413)
    def too_large(_error):
        return upload_page(TOO_LARGE_MESSAGE), 413

    @app.get("/cards")
    def cards():
        if not deck["cards"]:
            return redirect(url_for("index"))
        return render_template("cards.html", cards=deck["cards"], filename=deck["filename"])

    @app.get("/quiz")
    def quiz():
        data = state()
        if data is None:
            return redirect(url_for("index"))
        return render_quiz(data)

    @app.post("/quiz")
    def answer():
        data = state()
        if data is None:
            return redirect(url_for("index"))
        if data["feedback"] is None and data["index"] < len(data["quiz"]):
            card = data["quiz"][data["index"]]
            correct = check_answer(request.form.get("answer", ""), card.term)
            data["score"] += correct
            data["feedback"] = {"correct": correct, "answer": request.form.get("answer", "")}
        return render_quiz(data)

    @app.post("/quiz/next")
    def next_question():
        data = state()
        if data is None:
            return redirect(url_for("index"))
        if data["feedback"] is not None:
            data["index"] += 1
            data["feedback"] = None
        return redirect(url_for("quiz"))

    @app.post("/quiz/restart")
    def restart():
        data = state()
        if data is None:
            return redirect(url_for("index"))
        new_quiz(data)
        return redirect(url_for("quiz"))

    def render_quiz(data: dict):
        total = len(data["quiz"])
        done = data["index"] >= total
        return render_template(
            "quiz.html",
            done=done,
            card=None if done else data["quiz"][data["index"]],
            number=data["index"] + 1,
            total=total,
            score=data["score"],
            feedback=data["feedback"],
        )

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5050)
