import re
from pathlib import Path

from fastapi.testclient import TestClient

from webutil import make

TEMPLATES = Path(__file__).parent.parent / "between" / "web" / "templates"


def test_no_inline_styles_or_scripts_that_csp_would_block():
    for t in TEMPLATES.glob("*.html"):
        html = t.read_text()
        assert not re.search(r'\sstyle="', html), f"inline style in {t.name}"
        assert not re.search(r"<script(?![^>]*\ssrc=)[^>]*>", html), f"inline script in {t.name}"


def test_demo_family_heading_names_both_parents():
    app, _ = make(demo_parent_a_email="sb-a@personal.example.com", demo_parent_b_email="sb-b@personal.example.com")
    c = TestClient(app)
    fid = c.post("/demo/new", follow_redirects=False).headers["location"].rsplit("/", 1)[1]
    assert "Maria (demo) &amp; David (demo)" in c.get(f"/f/{fid}").text


def test_errors_render_as_pages_for_people_and_json_for_webhooks():
    from webutil import create_family
    app, _ = make()
    c = TestClient(app)
    fid, _ = create_family(TestClient(app))
    r = c.get(f"/f/{fid}")
    assert r.status_code == 403 and "<html" in r.text and "Not your family" in r.text
    w = c.post("/webhooks/paypal", json={"id": "x"})
    assert w.headers["content-type"].startswith("application/json")
