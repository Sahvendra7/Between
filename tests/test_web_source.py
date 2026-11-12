"""A citation opens the agreement at the cited page with the quoted clause highlighted."""
import re
from pathlib import Path

from keys import PLAN1
from webutil import fake_ai, family_with_rules, make, submit_expense, two_parents

DOC1 = (Path(__file__).parent.parent / "samples" / "agreements" / PLAN1["doc"]).read_text()


def test_decision_citation_links_to_highlighted_clause():
    app, _ = make(ai=fake_ai(PLAN1))
    a, b, fid = family_with_rules(app, DOC1)
    loc = submit_expense(a, fid, "medical").headers["location"]
    link = re.search(r'href="(/f/[^"]+/source\?[^"]+)"', a.get(loc).text).group(1).replace("&amp;", "&")
    page = a.get(link).text
    marked = re.search(r'<mark id="clause">(.*?)</mark>', page, re.S).group(1)
    split = next(r for r in PLAN1["rules"] if r["kind"] == "split" and r["category"] == "medical")
    assert " ".join(marked.split()) == " ".join(split["source"]["quote"].split())


def test_rules_page_links_every_agreement_rule():
    app, _ = make(ai=fake_ai(PLAN1))
    a, b, fid = family_with_rules(app, DOC1)
    html = a.get(f"/f/{fid}/rules").text
    assert len(re.findall(r'/source\?', html)) >= len(re.findall(r"<blockquote>", html)) > 0


def test_source_is_family_scoped():
    app, _ = make(ai=fake_ai(PLAN1))
    a, b, fid = family_with_rules(app, DOC1)
    link = re.search(r'href="(/f/[^"]+/source\?[^"]+)"', a.get(f"/f/{fid}/rules").text).group(1).replace("&amp;", "&")
    c, d, other = two_parents(app)
    assert c.get(link).status_code in (403, 404)
    assert c.get(link.replace(fid, other)).status_code == 404
