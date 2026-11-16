# One Word Study — Specification (round 1)

Source of truth: `problem.md`. This file turns requirements R1–R6 into
precise, testable behavior. Decisions marked *(clarified)* were confirmed
with the project owner before coding.

## Overview

A local Flask web app. The student uploads one PDF of unit material; the
app finds lines written as `Term: definition` or `Term - definition`,
turns them into flash cards, and quizzes the student on them.

The logic (PDF text extraction, card parsing, quiz building, answer
checking) lives in `flashcards.py` and has no Flask imports. `app.py`
is a thin web layer over it.

## R1 — Upload one PDF

- The home page (`/`) has a form with a single file input (no `multiple`)
  that accepts `.pdf`.
- Submitting posts to `/upload`. Only one file is read.
- If no file is chosen, the page shows: `Please choose a PDF file.`
- If the file cannot be read as a PDF, the page shows:
  `Could not read this file as a PDF.`
- Uploads up to 50 MB are accepted. Bigger files get the response:
  `This PDF is too large (limit is 50 MB).`
- A new upload replaces the student's previous cards and quiz.

## R2 — Flash cards

- Each card has a `term` (front) and a `definition` (back).
- After a successful upload, the student is sent to `/cards`, which lists
  every card with its term and definition, in the order they appear in
  the PDF. Clicking a card flips it: the front shows the term, the back
  shows the definition. The page also shows the card count.

## R3 — Quiz from the cards

- The quiz has exactly one question per card; every card appears once.
- Question order is shuffled for each new quiz.
- *(clarified)* One question at a time: `/quiz` shows the current
  question; after the student answers, it shows feedback and a "Next"
  button. After the last question it shows the score (`X / N correct`)
  and a link to start again.

## R4 — Which lines become cards

The PDF text is split into lines. For each line:

1. Leading and trailing whitespace is removed. A leading bullet marker
   (`•`, `◦`, `▪`, `*`, `-`, `–`, `—` followed by a space) is removed.
2. The separator is the **earliest** occurrence in the line of:
   - a colon `:` (spaces around it are optional), or
   - *(clarified)* a dash with whitespace on **both** sides: ` - `, ` – `
     (en dash), or ` — ` (em dash). A hyphen inside a word, as in
     `self-esteem`, is never a separator.
3. The term is the text before the separator and the definition is the
   text after it. Runs of whitespace inside each are collapsed to one
   space. If either part is empty, the line is not a card.
4. *(clarified)* Only the matching line is used. Lines that continue a
   wrapped definition are ignored.
5. *(clarified)* No heading filter: any line matching the pattern is a
   card, including lines like `Chapter 3: Cells`.
6. Exact duplicate cards (same term and definition, ignoring case and
   spacing) are kept only once, at the first occurrence.

## R5 — Quiz questions and answer checking

- A question shows the card's definition. The term is not shown.
- The student types the term into a text box and submits.
- An answer is correct when it equals the term after both are normalized:
  casefolded, with leading/trailing whitespace removed and inner runs of
  whitespace collapsed to one space.
- Correct answer: the page shows `Correct!`.
- Wrong or empty answer: the page shows `Not quite.` and
  `The correct answer is: <term>`, so the student sees where to focus.

## R6 — Messages when no cards can be made

- If the PDF has no extractable text (for example, a scanned PDF), the
  page shows exactly: `No text found in this PDF.`
- If the PDF has text but no line matches R4, the page shows exactly:
  `We didn't find terms. They don't match our pattern: "Term: definition" or "Term - definition".`
- In both cases the student stays on the upload page and can try another
  file.

## Non-functional

- Python 3.12, Flask, pypdf, pytest. No API keys, logins, or paid
  services.
- Runs locally with one command (`./run.sh`) on `http://127.0.0.1:5050`.
- Cards and quiz state are kept in server memory per browser session.
  Nothing is written to disk, and state is lost when the server stops.
