import io
from pathlib import Path

import pytest
from pypdf import PdfWriter

from between.agreement import AgreementError, label_key, locate, pdf_to_text

DOCS = Path(__file__).parent.parent / "samples" / "agreements"


def test_locate_finds_section_labels():
    t = (DOCS / "plan2_crossborder.txt").read_text()
    assert "4(a)" in locate(t, "currently 65% Parent One and 35% Parent Two", 2)
    assert locate(t, "not in the document", 2) is None
    assert label_key("Item 5") == "5" and label_key("Section 6.1") == "6.1"


def test_pdf_without_text_is_refused():
    w = PdfWriter()
    w.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    w.write(buf)
    with pytest.raises(AgreementError) as e:
        pdf_to_text(buf.getvalue())
    assert e.value.code == "no_text_layer"


def test_garbage_bytes_are_not_a_pdf():
    with pytest.raises(AgreementError) as e:
        pdf_to_text(b"not a pdf")
    assert e.value.code == "not_a_pdf"
