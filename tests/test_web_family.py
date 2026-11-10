from fastapi.testclient import TestClient

from webutil import csrf, create_family, join, make, two_parents


def test_create_family_then_join_other_parent():
    app, _ = make()
    a, b, fid = two_parents(app)
    home_b = b.get(f"/f/{fid}")
    assert home_b.status_code == 200 and "David" in home_b.text and "Maria" in home_b.text


def test_invite_get_does_not_consume_it():
    app, _ = make()
    a = TestClient(app)
    fid, token = create_family(a)
    assert TestClient(app).get(f"/join/{token}").status_code == 200  # a link preview shouldn't burn the invite
    assert join(TestClient(app), token).status_code == 303


def test_used_invite_shows_error():
    app, _ = make()
    a = TestClient(app)
    fid, token = create_family(a)
    join(TestClient(app), token)
    r = join(TestClient(app), token)
    assert r.status_code == 400 and "already been used" in r.text


def test_other_family_route_is_403():
    app, _ = make()
    a, b, fid = two_parents(app)
    stranger = TestClient(app)
    other_fid, _ = create_family(stranger)
    assert a.get(f"/f/{other_fid}").status_code == 403
    assert TestClient(app).get(f"/f/{fid}").status_code == 403


def test_post_without_csrf_is_403():
    app, _ = make()
    a, b, fid = two_parents(app)
    assert a.post(f"/f/{fid}/agreement", data={"text": "x"}).status_code == 403
    assert a.post(f"/f/{fid}/agreement", data={"text": "x", "csrf": "wrong"}).status_code == 403


def test_real_looking_paypal_email_refused_in_demo_mode():
    app, _ = make()
    r = TestClient(app).post("/families", data={"role_label": "Mother", "other_label": "Father", "display_name": "M",
                                                 "paypal_email": "jane@gmail.com"})
    assert r.status_code == 400 and "sandbox" in r.text
    create_family(TestClient(app), email="sb-x@personal.example.com")  # positive control


def test_security_headers_present():
    app, _ = make()
    r = TestClient(app).get("/")
    assert r.headers["x-frame-options"] == "DENY" and r.headers["referrer-policy"] == "same-origin"
    assert "default-src 'self'" in r.headers["content-security-policy"]


def test_session_cookie_flags():
    app, _ = make(secure_cookies=True)
    r = TestClient(app).post("/families", data={"role_label": "Mother", "other_label": "Father", "display_name": "M",
                                                 "paypal_email": "sb-x@personal.example.com"})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "secure" in cookie


def test_demo_banner_on_every_page():
    app, _ = make()
    assert "Sandbox demonstration with synthetic data" in TestClient(app).get("/").text


def test_rotate_invite_only_before_other_parent_joins():
    app, _ = make()
    a, b, fid = two_parents(app)
    page = a.get(f"/f/{fid}/agreement").text
    r = a.post(f"/f/{fid}/invite/rotate", data={"csrf": csrf(page)})
    assert r.status_code == 409  # B has joined: rotating would lock B out
