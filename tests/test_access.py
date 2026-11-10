from datetime import timedelta

import pytest
import sqlalchemy as sa

from between import access, db
from between.config import Settings
from conftest import insert_family


def test_invite_redeems_once_to_a_session(conn, now):
    insert_family(conn)
    tok = access.create_invite(conn, "f1", "B", now)
    sid = access.redeem_invite(conn, tok, now)
    s = access.session_for(conn, sid, now)
    assert (s.family_id, s.role, len(s.ref)) == ("f1", "B", 8)


def test_used_invite_cannot_be_redeemed_twice(conn, now):
    insert_family(conn)
    tok = access.create_invite(conn, "f1", "B", now)
    access.redeem_invite(conn, tok, now)
    with pytest.raises(access.AccessError) as e:
        access.redeem_invite(conn, tok, now)
    assert e.value.code == "used"


def test_invite_expires_after_72h(conn, now):
    insert_family(conn)
    tok = access.create_invite(conn, "f1", "B", now)
    with pytest.raises(access.AccessError) as e:
        access.redeem_invite(conn, tok, now + timedelta(hours=72, seconds=1))
    assert e.value.code == "expired"
    with pytest.raises(access.AccessError) as e:
        access.redeem_invite(conn, "not-a-token", now)
    assert e.value.code == "unknown"


def test_reissue_revokes_old_invite_and_session(conn, now):
    insert_family(conn)
    old_sid = access.redeem_invite(conn, access.create_invite(conn, "f1", "B", now), now)
    pending = access.create_invite(conn, "f1", "B", now)
    access.create_invite(conn, "f1", "B", now)  # rotate
    assert access.session_for(conn, old_sid, now) is None
    with pytest.raises(access.AccessError) as e:
        access.redeem_invite(conn, pending, now)
    assert e.value.code == "revoked"


def test_session_is_bound_to_one_role(conn, now):
    insert_family(conn)
    a = access.create_session(conn, "f1", "A", now)
    b = access.redeem_invite(conn, access.create_invite(conn, "f1", "B", now), now)
    assert access.session_for(conn, a, now).role == "A" and access.session_for(conn, b, now).role == "B"
    assert access.session_for(conn, a, now + access.SESSION_TTL + timedelta(seconds=1)) is None


def test_nothing_raw_is_stored(conn, now):
    insert_family(conn)
    tok = access.create_invite(conn, "f1", "B", now)
    sid = access.redeem_invite(conn, tok, now)
    dump = str(conn.execute(sa.select(db.invite)).all()) + str(conn.execute(sa.select(db.session)).all())
    assert tok not in dump and sid not in dump


def test_csrf_compare(conn, now):
    insert_family(conn)
    s = access.session_for(conn, access.create_session(conn, "f1", "A", now), now)
    assert access.check_csrf(s, s.csrf) and not access.check_csrf(s, "x") and not access.check_csrf(s, None)


def test_cookie_flags_secure_when_configured():
    assert access.cookie_kwargs(Settings(secure_cookies=True)) == {
        "httponly": True, "samesite": "lax", "secure": True, "max_age": 1209600, "path": "/"}
    assert access.cookie_kwargs(Settings(secure_cookies=False))["secure"] is False
