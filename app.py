"""Flask web layer. All study logic lives in flashcards.py."""
from __future__ import annotations

import os
import uuid

from flask import Flask, redirect, render_template, request, session, url_for

from flashcards import PdfReadError, build_quiz, cards_from_pdf, check_answer

MAX_UPLOAD_MB = 50
NO_FILE_MESSAGE = "Please choose a PDF file."
BAD_PDF_MESSAGE = "Could not read this file as a PDF."
TOO_LARGE_MESSAGE = f"This PDF is too large (limit is {MAX_UPLOAD_MB} MB)."


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.urandom(32)  # local only; sessions reset when the server restarts
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

    # Per-browser state kept in memory: {session id: {"cards", "quiz", "index", "score", "feedback"}}
    store: dict[str, dict] = {}

    def state() -> dict | None:
        sid = session.get("sid")
        return store.get(sid) if sid else None

    def new_quiz(data: dict) -> None:
        data.update(quiz=build_quiz(data["cards"]), index=0, score=0, feedback=None)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/upload")
    def upload():
        sid = session.setdefault("sid", uuid.uuid4().hex)
        store.pop(sid, None)  # any new upload replaces the previous cards
        file = request.files.get("pdf")
        if file is None or not file.filename:
            return render_template("index.html", message=NO_FILE_MESSAGE), 400
        try:
            cards, message = cards_from_pdf(file.stream)
        except PdfReadError:
            return render_template("index.html", message=BAD_PDF_MESSAGE), 400
        if message:
            return render_template("index.html", message=message)
        data = {"cards": cards, "filename": file.filename}
        new_quiz(data)
        store[sid] = data
        return redirect(url_for("cards"))

    @app.errorhandler(413)
    def too_large(_error):
        return render_template("index.html", message=TOO_LARGE_MESSAGE), 413

    @app.get("/cards")
    def cards():
        data = state()
        if data is None:
            return redirect(url_for("index"))
        return render_template("cards.html", cards=data["cards"], filename=data["filename"])

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
