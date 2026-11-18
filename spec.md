# One Word Study — Specification

Source of truth: `problem.md`. This file turns requirements R1–R10 into
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
- *(changed with R10)* A new upload does not clear the current cards by
  itself. A failed upload keeps them, and a good one replaces them only
  after the student confirms (see R10).

## R2 — Flash cards

- Each card has a `term` (front) and a `definition` (back).
- After a successful upload, the student is sent to `/cards`, which lists
  every card with its term and definition, in the order they appear in
  the PDF. Clicking a card flips it: the front shows the term, the back
  shows the definition. The page also shows the card count.

## R3 — Quiz from the cards

- *(changed with R9)* The quiz asks the number of questions the student
  chose (R9). No card is asked twice in the same quiz. Choosing "all"
  asks every card exactly once.
- Question order is shuffled for each new quiz.
- *(clarified)* One question at a time: `/quiz` shows the current
  question; after the student answers, it shows feedback and a "Next"
  button. After the last question it shows the score (`X / N correct`)
  and a "New quiz" button, which goes back to the length choice (R9).
- If there is no quiz in progress, `/quiz` shows the length choice (R9).
  If there are no cards, it redirects to `/`.

## R4 — Which lines become cards

The PDF text is split into lines. For each line:

1. Leading and trailing whitespace is removed. A leading bullet marker
   (`•`, `◦`, `▪`, `*`, `-`, `–`, `—` followed by a space) is removed.
2. The separator is the **earliest** occurrence in the line of:
   - a colon `:` **followed by whitespace** (spaces before it are optional).
     *(changed with R4)* A colon with no space after it, as in `2:30` or
     `Cell:The unit`, is not a separator.
   - *(clarified)* a dash with whitespace on **both** sides: ` - `, ` – `
     (en dash), or ` — ` (em dash). A hyphen inside a word, as in
     `self-esteem`, is never a separator.
3. The term is the text before the separator and the definition is the
   text after it. Runs of whitespace inside each are collapsed to one
   space. If either part is empty, the line is not a card.
4. *(changed with R4)* The term must:
   - start with a capital letter,
   - have 4 words or fewer, and
   - not end with a digit (so `Chapter 3: Cells` and
     `September 14 - November 17` are not cards).
5. *(changed with R4)* The definition must not end with `?`. This is
   checked on the full definition, after R7 has added any continuation
   lines.
6. *(clarified)* No other heading filter: a line like
   `Chapter three: Cells` is still a card.
7. Exact duplicate cards (same term and definition, ignoring case and
   spacing) are kept only once, at the first occurrence.

## R7 — Definitions that continue onto the next lines

After a card line, each following line is added to the definition
(separated by one space, with its inner whitespace collapsed) while the
line:

- *(changed with R7)* starts with a lowercase letter or an opening
  parenthesis `(` (after leading whitespace), and
- is not empty or whitespace only, does not start with a bullet marker
  from R4 step 1, and is not itself a card line under R4.

The first line that fails any of these ends the definition. So a
capitalized line (often the next slide's title, or a new sentence in a
glossary) ends it. A line like `(see also: Diffusion)` continues the
definition; it is never a card line itself, because its "term" does not
start with a capital letter.

Known limit: a lowercase line that is not part of the definition (for
example a sentence that happens to start lowercase) is still added.
Telling those apart would need language understanding, which the
project does not use.

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

## R8 — Practice missed cards

- During a round the app remembers every card answered wrong (including
  empty answers).
- On the score page, if at least one answer was wrong, there is a button
  `Practice the N missed cards` (`Practice the 1 missed card` when N is 1).
- A practice round asks only those cards, each once, in a new random
  order. It works like a normal quiz (R5 checking, feedback, Next) and its
  page is labelled `Practice round`.
- At the end of a practice round the score page shows `X / N correct` for
  that round. If some are still wrong, it offers `Practice the K missed
  cards` again (only the cards missed in *this* round) and a
  `Stop practicing` button, which ends the round and goes to `/cards`.
  If all are right, it says so and offers "New quiz" and "Review cards".
- The score page of a normal quiz keeps its "New quiz" and "Review cards"
  buttons next to the practice button.

## R9 — Choose quiz length

- Before a quiz starts, `/quiz` shows `How many questions?` with one
  button per choice; each posts `length` (`10`, `20` or `all`) to
  `/quiz/start`.
- A number choice is shown only when it is **smaller** than the number of
  cards; `All N cards` is always shown. So with 25 cards the choices are
  `10 questions`, `20 questions`, `All 25 cards`; with 15 cards
  `10 questions`, `All 15 cards`; with 10 or fewer only `All N cards`,
  plus the note `This set has N cards, so the quiz asks all of them.`
- Questions are picked at random from the cards with no repeats
  (`random.sample`). `build_quiz` takes an optional random generator so
  tests can fix the seed.
- An unknown `length` value shows the choice page again. A number bigger
  than the card count asks all cards.

## R10 — Save cards between visits

- The current cards and the PDF's filename are saved as JSON at
  `~/.one-word-study/cards.json` (outside the repository).
  `create_app(save_path=...)` can point it elsewhere; tests always use a
  temporary path.
- File format: `{"filename": "<name>.pdf", "cards": [{"term": "...",
  "definition": "..."}, ...]}`. It is written to a temporary file in the
  same folder and then renamed, so a crash never leaves half a file.
- When the app starts, it loads that file. If the file is missing, is not
  valid JSON, or has the wrong shape, the app starts with no cards.
- When saved cards exist, the home page shows `You have N saved cards
  from A.` with links to the cards and the quiz.
- Upload flow:
  1. The new PDF is read first. The current cards are not touched yet.
  2. If it can't be used (no file, not a PDF, too large, no text, no
     terms), the page shows why (R1/R6 messages) and the current cards
     stay.
  3. If it has cards and there are no saved cards, they are saved and the
     student goes to `/cards`.
  4. If it has cards and saved cards exist, the page asks
     `Replace N cards from A with M cards from B?` with `Replace` and
     `Cancel` buttons. The new cards wait in server memory for that
     browser. `Replace` saves them, ends any quiz in progress and goes to
     `/cards`. `Cancel` drops them and goes to `/cards` with the old cards.
- Quiz progress is not saved to disk; only the cards are.

## Non-functional

- Python 3.12, Flask, pypdf, pytest. No API keys, logins, or paid
  services.
- Runs locally with one command (`./run.sh`) on `http://127.0.0.1:5050`.
- *(changed with R10)* The cards are saved to one JSON file on this
  computer (R10), shared by every browser tab. Quiz progress and a
  pending upload are kept in server memory per browser session and are
  lost when the server stops.
