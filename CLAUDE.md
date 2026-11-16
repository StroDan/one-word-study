# CLAUDE.md

CSC299 final project: a local Flask app that turns a PDF into flash cards and a quiz.

- Source of truth: `problem.md` (requirements R1–R6). Detailed behavior: `spec.md`.
  If they disagree or something is unclear, ask the owner before coding.
- Python 3.12 only, in `.venv` (create it with `/opt/homebrew/bin/python3.12 -m venv .venv`).
  The system `python3` is 3.9 and too old.
- Logic lives in `flashcards.py` (no Flask imports). `app.py` is only the web layer.
- Tests: `.venv/bin/python -m pytest`. Each test name starts with the requirement ID it
  checks, e.g. `test_R4_...`. Every requirement needs at least one test.
- Run the app: `./run.sh`.
- Commits: small, and each message says what changed and why. Never write "update",
  "fix", or "wip" as the message. Never amend or undo commits. Never push.
- No API keys, logins, or paid services.
