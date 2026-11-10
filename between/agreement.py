"""Reading an agreement: page markers, clause labels, finding a quote. No model, no logging of text."""
from __future__ import annotations

import io
import re

LABEL = re.compile(r"^\s*(Section \d+|Clause \d+|Item \d+|Appendix [A-Z]|\d+\.\d+|\d+\([a-z]\)|[A-Z]\.\d+)(?=[\s.]|$)")
HEADINGS = ("Section", "Clause", "Item", "Appendix")
MIN_TEXT = 200


class AgreementError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def label_key(s: str) -> str:
    s = re.sub(r"(?i)\b(section|clause|item|appendix|para(graph)?)\b|§", "", s)
    return re.sub(r"\s+", "", s).lower()


def pages(text: str) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {}
    current = None
    for line in text.splitlines():
        m = re.match(r"^=== Page (\d+) ===$", line.strip())
        if m:
            current = int(m.group(1))
            out.setdefault(current, [])
        elif current is not None:
            out[current].append(line)
    return out


def locate(text: str, quote: str, page: int) -> list[str] | None:
    """Labels (most specific first) governing where the quote starts on that page; None if absent."""
    lines = pages(text).get(page)
    q = norm(quote or "")
    if not lines or not q:
        return None
    joined, starts = "", []
    for line in lines:
        starts.append(len(joined))
        joined += norm(line) + " "
    at = joined.find(q)
    if at < 0:
        return None
    idx = max(i for i, s in enumerate(starts) if s <= at)
    labels: list[str] = []
    for i in range(idx, -1, -1):
        m = LABEL.match(lines[i])
        if m:
            heading = m.group(1).split()[0] in HEADINGS
            if not labels or heading:
                labels.append(label_key(m.group(1)))
            if heading:
                break
    return labels


def pdf_to_text(data: bytes) -> str:
    """Text of a text-based PDF with '=== Page N ===' markers. Scanned PDFs are refused, not OCR'd."""
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        parts = [f"=== Page {i} ===\n{(page.extract_text() or '').strip()}" for i, page in enumerate(reader.pages, 1)]
    except (PdfReadError, ValueError, OSError):
        raise AgreementError("not_a_pdf") from None
    text = "\n".join(parts)
    if len(re.sub(r"=== Page \d+ ===|\s", "", text)) < MIN_TEXT:
        raise AgreementError("no_text_layer")
    return text
