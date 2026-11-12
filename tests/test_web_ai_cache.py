"""Demo mode reuses the AI's reading of an identical agreement, so judges clicking the samples don't hit rate limits."""
from pathlib import Path

from between.extraction import Extraction
from keys import PLAN1
from webutil import fake_ai, make, two_parents, upload

DOC1 = (Path(__file__).parent.parent / "samples" / "agreements" / PLAN1["doc"]).read_text()


def counting(ai):
    calls = []
    inner = ai.beta.messages.parse

    def parse(**kw):
        calls.append(kw["output_format"])
        return inner(**kw)
    ai.beta.messages.parse = parse
    return ai, calls


def test_same_agreement_is_read_once_in_demo_mode():
    ai, calls = counting(fake_ai(PLAN1))
    app, _ = make(ai=ai)
    for _ in range(2):
        a, b, fid = two_parents(app)
        assert upload(a, fid, DOC1).status_code == 303
        assert "I approve these" in a.get(f"/f/{fid}/rules").text
    assert calls.count(Extraction) == 1


def test_no_reuse_outside_demo_mode():
    ai, calls = counting(fake_ai(PLAN1))
    app, _ = make(ai=ai, demo_mode=False)
    for _ in range(2):
        a, b, fid = two_parents(app)
        upload(a, fid, DOC1)
    assert calls.count(Extraction) == 2
