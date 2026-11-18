"""Flask web layer. All study logic lives in flashcards.py."""
from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable

from flask import Flask, redirect, render_template, request, session, url_for

from flashcards import (
    QUIZ_LENGTHS,
    CardSet,
    PdfReadError,
    add_set,
    build_quiz,
    cards_from_pdf,
    check_answer,
    find_set,
    load_sets,
    quiz_length_choices,
    remove_set,
    save_sets,
)

MAX_UPLOAD_MB = 50
NO_FILE_MESSAGE = "Please choose a PDF file."
BAD_PDF_MESSAGE = "Could not read this file as a PDF."
TOO_LARGE_MESSAGE = f"This PDF is too large (limit is {MAX_UPLOAD_MB} MB)."
# R10: outside the repository, so saved cards are never committed.
DEFAULT_SAVE_PATH = Path.home() / ".one-word-study" / "cards.json"


def upload_date(when: datetime) -> str:
    """R11: the date shown in the history list, like "Nov 17, 2026"."""
    return f"{when:%b} {when.day}, {when.year}"


def create_app(save_path: str | os.PathLike | None = None,
               clock: Callable[[], datetime] = datetime.now) -> Flask:
    """save_path and clock can be set by tests (a temporary file and a fixed time)."""
    app = Flask(__name__)
    app.secret_key = os.urandom(32)  # local only; sessions reset when the server restarts
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
    app.jinja_env.filters["upload_date"] = upload_date
    save_path = Path(save_path) if save_path is not None else DEFAULT_SAVE_PATH

    # R10/R11: the saved card sets, newest first, shared by every browser tab.
    library = {"sets": load_sets(save_path)}

    # Per-browser state kept in memory:
    # {session id: {"set_id", "quiz_set", "quiz", "index", "score", "feedback", "missed", "practice"}}
    # "set_id" is the browser's current set (R11); "quiz_set" is the CardSet the quiz was
    # built from. A same-name upload makes a new CardSet object, so `is not` spots it.
    store: dict[str, dict] = {}

    def session_state() -> dict:
        sid = session.setdefault("sid", uuid.uuid4().hex)
        return store.setdefault(sid, {"set_id": None, "quiz_set": None, "quiz": None})

    def current_set(data: dict) -> CardSet | None:
        """R11: the browser's current set, or the newest one if it has none (or it was
        deleted or dropped). Ends the quiz if the set or its cards changed."""
        sets = library["sets"]
        current = find_set(sets, data["set_id"]) or (sets[0] if sets else None)
        data["set_id"] = current.id if current else None
        if data["quiz_set"] is not current:
            data.update(quiz_set=current, quiz=None)
        return current

    def state() -> tuple[dict, CardSet] | tuple[None, None]:
        """This browser's quiz state and current set, or (None, None) when there are no
        sets. Its "quiz" is None until the student picks a length (R9)."""
        data = session_state()
        current = current_set(data)
        return (data, current) if current else (None, None)

    def new_quiz(data: dict, current: CardSet, count: int | None) -> None:
        start_round(data, build_quiz(current.cards, count), practice=False)

    def start_round(data: dict, questions: list, practice: bool) -> None:
        # "missed" collects the cards answered wrong in this round (R8).
        data.update(quiz=questions, index=0, score=0, feedback=None, missed=[], practice=practice)

    def home_page(message: str | None = None):
        return render_template("index.html", message=message, sets=library["sets"],
                               current=current_set(session_state()))

    def change_sets(sets: list[CardSet]) -> None:
        save_sets(save_path, sets)  # first, so a failed write changes nothing in memory
        library["sets"] = sets

    @app.get("/")
    def index():
        return home_page()

    @app.post("/upload")
    def upload():
        # R10: read the new PDF first; nothing is saved unless it is usable.
        file = request.files.get("pdf")
        if file is None or not file.filename:
            return home_page(NO_FILE_MESSAGE), 400
        try:
            cards, message = cards_from_pdf(file.stream)
        except PdfReadError:
            return home_page(BAD_PDF_MESSAGE), 400
        if message:
            return home_page(message)
        # R11: added on top (or replacing the set with the same file name); it becomes
        # this browser's current set.
        change_sets(add_set(library["sets"], file.filename, cards, clock()))
        session_state()["set_id"] = library["sets"][0].id
        return redirect(url_for("cards"))

    @app.post("/sets/<set_id>/study")
    def study(set_id: str):
        """R11: pick a set from the history to study it again."""
        if find_set(library["sets"], set_id) is None:
            return redirect(url_for("index"))
        session_state()["set_id"] = set_id
        return redirect(url_for("cards"))

    @app.get("/sets/<set_id>/delete")
    def confirm_delete(set_id: str):
        """R11: ask before deleting."""
        card_set = find_set(library["sets"], set_id)
        if card_set is None:
            return redirect(url_for("index"))
        return render_template("delete.html", card_set=card_set)

    @app.post("/sets/<set_id>/delete")
    def delete(set_id: str):
        if find_set(library["sets"], set_id) is not None:
            change_sets(remove_set(library["sets"], set_id))
        return redirect(url_for("index"))

    @app.errorhandler(413)
    def too_large(_error):
        return home_page(TOO_LARGE_MESSAGE), 413

    @app.get("/cards")
    def cards():
        _, current = state()
        if current is None:
            return redirect(url_for("index"))
        return render_template("cards.html", cards=current.cards, filename=current.filename)

    @app.get("/quiz")
    def quiz():
        data, current = state()
        if data is None:
            return redirect(url_for("index"))
        if data["quiz"] is None:
            return render_template("choose.html", total=len(current.cards),
                                   choices=quiz_length_choices(len(current.cards)))
        return render_quiz(data)

    @app.post("/quiz/start")
    def start():
        data, current = state()
        if data is None:
            return redirect(url_for("index"))
        length = request.form.get("length", "")
        if length == "all":
            new_quiz(data, current, None)
        elif length in {str(n) for n in QUIZ_LENGTHS}:
            new_quiz(data, current, int(length))  # build_quiz asks all cards if there are fewer
        # Any other value: the choice page is shown again.
        return redirect(url_for("quiz"))

    @app.post("/quiz")
    def answer():
        data, _ = state()
        if data is None:
            return redirect(url_for("index"))
        if data["quiz"] is None:
            return redirect(url_for("quiz"))
        if data["feedback"] is None and data["index"] < len(data["quiz"]):
            card = data["quiz"][data["index"]]
            correct = check_answer(request.form.get("answer", ""), card.term)
            data["score"] += correct
            if not correct:
                data["missed"].append(card)
            data["feedback"] = {"correct": correct, "answer": request.form.get("answer", "")}
        return render_quiz(data)

    @app.post("/quiz/next")
    def next_question():
        data, _ = state()
        if data is None:
            return redirect(url_for("index"))
        if data["quiz"] is not None and data["feedback"] is not None:
            data["index"] += 1
            data["feedback"] = None
        return redirect(url_for("quiz"))

    @app.post("/quiz/practice")
    def practice():
        """R8: a new round with only the cards missed in the round just finished."""
        data, _ = state()
        if data is None:
            return redirect(url_for("index"))
        quiz = data["quiz"]
        if quiz is not None and data["index"] >= len(quiz) and data["missed"]:
            start_round(data, build_quiz(data["missed"]), practice=True)
        return redirect(url_for("quiz"))

    @app.post("/quiz/stop")
    def stop():
        """R8: stop practicing; the next visit to /quiz asks for a new quiz length."""
        data, _ = state()
        if data is not None:
            data["quiz"] = None
        return redirect(url_for("cards"))

    @app.post("/quiz/restart")
    def restart():
        data, _ = state()
        if data is None:
            return redirect(url_for("index"))
        data["quiz"] = None  # R9: a new quiz starts with the length choice
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
            missed=len(data["missed"]),
            practice=data["practice"],
        )

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5050)
