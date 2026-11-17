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
   is joined back together.
3. A quiz shows each definition, one at a time, and you type the term.
   Capitals and extra spaces don't matter. If you're wrong, it shows the
   correct term so you know what to review. You get a score at the end.
4. If the PDF has no text (for example, a scanned PDF), it says
   "No text found in this PDF." If it has text but no lines match the
   pattern, it tells you which pattern to use.

It runs only on your computer. No accounts, API keys, or internet services.
See `spec.md` for the exact rules.

## Run it

Requires Python 3.12 at `/opt/homebrew/bin/python3.12`.

```sh
./run.sh
```

Then open http://127.0.0.1:5050. The first run creates `.venv` and installs
the dependencies.

## Run the tests

```sh
.venv/bin/python -m pytest
```

(Run `./run.sh` once first, or create the venv yourself:
`/opt/homebrew/bin/python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt`.)

Test names start with the requirement they check, e.g. `test_R4_...`.
The sample PDFs in `tests/fixtures/` are built by `tests/make_fixtures.py`.
