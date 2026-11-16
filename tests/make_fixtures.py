"""Build the small PDFs used by the tests (run once; outputs are committed).

    .venv/bin/python tests/make_fixtures.py

Writes raw PDF syntax by hand so no extra PDF-writing dependency is needed.
"""
from pathlib import Path

from pypdf import PdfWriter

FIXTURES = Path(__file__).parent / "fixtures"


def _escape(line: str) -> bytes:
    raw = line.encode("cp1252")  # WinAnsiEncoding, so en/em dashes and bullets work
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def text_pdf(lines: list[str]) -> bytes:
    """Return a one-page PDF that shows each string on its own line."""
    stream = b"BT /F1 12 Tf 14 TL 72 740 Td\n"
    for line in lines:
        stream += b"(" + _escape(line) + b") Tj T*\n"
    stream += b"ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return out


SAMPLE_LINES = [
    "Unit 4 Biology Review",
    "self-esteem is not a card because the hyphen has no spaces",
    "Cell: The basic unit of life.",
    "Mitochondria - Organelle that produces energy for the cell.",
    "Osmosis – Movement of water across a membrane.",
    "Photosynthesis: Process plants use to turn light into food,",
    "which continues on this wrapped line.",
    "• Enzyme: A protein that speeds up a reaction.",
    "This sentence has no separator at all.",
]

# Lecture-slide style (made up): "• Term – definition", lowercase definitions that wrap
# over several lines, and lines that look like cards but are not (R4, R7).
SLIDES_LINES = [
    "Unit 2 Markets and Prices",
    "• Office hours",
    "• Mondays 2:30-5:00 pm Room 6200",
    "• Supply – the amount of a good that sellers",
    "are willing and able to sell at each price,",
    "holding other things equal.",
    "Demand and Elasticity",
    "• Demand – the amount buyers want at each price",
    "• Price elasticity – how much quantity responds",
    "to a change in price",
    "• Labor markets – how are wages set?",
    "• Quantity demanded falls when price rises – the law of demand",
    "• September 14 - November 17",
]

# Glossary style (made up): "Term:  Definition" with capital-letter definitions,
# continuation lines, and a blank line (a single space) between entries (R4, R7).
GLOSSARY_LINES = [
    "Glossary of Terms",
    " ",
    "Budget Deficit:  The amount by which spending is greater than revenue",
    "in one year.",
    " ",
    "Inflation:  A general rise in prices.  It lowers what money can buy.",
    "Someone on a fixed income loses purchasing power.",
    " ",
    "Opportunity Cost:  The value of the next best choice not taken.",
    "Because every choice uses limited resources, something is given up.",
]

NO_TERMS_LINES = [
    "Unit 4 Biology Review",
    "Cells are small and self-contained.",
    "Read chapter four before Friday.",
]


def main() -> None:
    FIXTURES.mkdir(exist_ok=True)
    (FIXTURES / "sample.pdf").write_bytes(text_pdf(SAMPLE_LINES))
    (FIXTURES / "no_terms.pdf").write_bytes(text_pdf(NO_TERMS_LINES))
    (FIXTURES / "slides.pdf").write_bytes(text_pdf(SLIDES_LINES))
    (FIXTURES / "glossary.pdf").write_bytes(text_pdf(GLOSSARY_LINES))
    blank = PdfWriter()
    blank.add_blank_page(width=612, height=792)  # stands in for a scanned page
    with open(FIXTURES / "scanned.pdf", "wb") as fh:
        blank.write(fh)


if __name__ == "__main__":
    main()
