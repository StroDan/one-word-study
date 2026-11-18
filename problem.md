# Problem
A student is trying to remember important information before an exam
and to understand the important words of the unit. The unit material
is a PDF that sometimes can be very big, and students don't understand
which words are important, so they try to memorize everything. Students
don't have a lot of time before the test to write flashcards.

# Initial requirements
- R1 The student uploads one PDF with the unit info.
- R2 The program makes flash cards from the PDF, with the term on one
  side and the definition on the other.
- R3 The program makes a quiz from the cards.
- R4 (changed: stricter rules, so not every line with a colon
  becomes a card) The program only makes a card from lines written
  as `Term: definition` or `Term - definition`, and only when:
  - there is a space after the colon (so `2:30` is not a card)
  - the term starts with a capital letter, has 4 words or fewer,
    and does not end with a number
  - the definition is not a question
- R5 The quiz shows a definition with the term missing. The student
  writes the term to get it right (capitals and extra spaces don't
  matter). If the answer is wrong, the program shows the correct answer
  so the student sees where to focus.
- R6 If the PDF has no text (scanned), the program shows "No text found
  in this PDF." If it has text but no lines match R4, the program shows
  "We didn't find terms. They don't match our pattern: "Term: definition"
  or "Term - definition"."
- R7 (changed: a line that starts with "(" now also counts as part of
  the definition) A definition can go on to the next lines. A next
  line is part of the definition if it starts with a small letter or
  an opening parenthesis "(". The definition stops at an empty line, a
  bullet point (a line starting with a bullet symbol such as •, -, or
  *), or a new card line.
- R8 Practice missed cards. After the quiz, if the student got some
  wrong, the app offers a short practice round with only the missed
  cards, and the student can repeat it until they get them all right
  or choose to stop.
- R9 Choose quiz length. Before the quiz starts, the student can
  choose how many questions to answer: 10, 20, or all cards. The
  questions are picked at random from the cards, with no card asked
  twice in the same quiz.
- R10 Save cards between visits. The cards from the last uploaded PDF
  are saved on this computer, so when the student comes back later,
  they can start a quiz without uploading the PDF again. Uploading a
  new PDF replaces the saved cards with the new ones. Before that
  happens, the app tells the student that the old cards will be
  replaced and lets them cancel. If the new PDF can't be used (it
  can't be read, has no text, or has no terms), the old cards stay and
  the app tells the student why the upload failed.
