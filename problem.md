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
- R4 The program only makes a card from lines written as
  `Term: definition` or `Term - definition`.
- R5 The quiz shows a definition with the term missing. The student
  writes the term to get it right (capitals and extra spaces don't
  matter). If the answer is wrong, the program shows the correct answer
  so the student sees where to focus.
- R6 If the PDF has no text (scanned), the program shows "No text found
  in this PDF." If it has text but no lines match R4, the program shows
  "We didn't find terms. They don't match our pattern: "Term: definition"
  or "Term - definition"."
