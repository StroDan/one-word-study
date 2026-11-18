# One Word Study

Turn a unit PDF into flash cards and a quiz, so you study the important words
instead of trying to memorize everything.

## What it does

1. You upload one PDF of your unit material.
2. Lines written as `Term: definition` or `Term - definition` become flash
   cards (term on the front, definition on the back; click to flip). To skip
   things that only look like terms, the colon needs a space after it (so
   `2:30` is ignored), the term starts with a capital letter, has at most 4
   words and doesn't end in a number, and question lines are skipped.
   A definition that wraps onto following lines starting with a small letter
   or an opening parenthesis `(` is joined back together.
3. Before a quiz you choose how many questions: 10, 20, or all cards (choices
   bigger than your number of cards are hidden). Cards are picked at random,
   never twice in one quiz.
4. The quiz shows each definition, one at a time, and you type the term.
   Capitals and extra spaces don't matter. If you're wrong, it shows the
   correct term so you know what to review. You get a score at the end.
5. If you missed any, you can practice just those cards. Repeat until you get
   them all, or stop whenever you like.
6. Every PDF you upload is saved as a card set, so next time you can go straight
   to the quiz. A new upload is added without asking, since nothing is lost. If
   the new PDF can't be used, you see why and nothing changes.
7. The home page lists your card sets, newest first, with each file name,
   upload date and number of cards. Press **Study** to switch to a set, or
   **Delete** to remove one (it asks first). The last 10 sets are kept; an
   11th upload removes the oldest. Uploading a PDF with the same file name as a
   saved set updates that set and moves it to the top instead of adding a copy.
8. If the PDF has no text (for example, a scanned PDF), it says
   "No text found in this PDF." If it has text but no lines match the
   pattern, it tells you which pattern to use.

It runs only on your computer. No accounts, API keys, or internet services.
The card sets (each PDF's name, upload date and cards) are saved in
`~/.one-word-study/cards.json`, outside this folder; delete that file to start
fresh. A save file from an older version (one set only) is still read. Quiz
progress and which set you are studying are not saved; after a restart you
start on the newest set.
See `spec.md` for the exact rules.

## Run it

Requires Python 3.12 at `/opt/homebrew/bin/python3.12`.

```sh
./run.sh
```

Then open http://127.0.0.1:5050. The first run creates `.venv` and installs
the dependencies.

### Try it with the sample PDF

`examples/unit_03_git_testing_ai.pdf` is a two-page vocabulary sheet (Git,
testing, and AI assistants) written in both card patterns, so it makes 21
clean cards. Upload it, flip a few cards, take a 10-question quiz, miss a
few on purpose to see the practice round, then check the history list on
the home page.

## Run the tests

```sh
.venv/bin/python -m pytest
```

(Run `./run.sh` once first, or create the venv yourself:
`/opt/homebrew/bin/python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt`.)

Test names start with the requirement they check, e.g. `test_R4_...`.
The tests save cards only to temporary folders, never to your real save file
(`tests/conftest.py` makes sure of that), and use a fixed clock for upload dates.
The sample PDFs in `tests/fixtures/` are built by `tests/make_fixtures.py`.
