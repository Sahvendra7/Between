import pytest
import sqlalchemy as sa

from between import db, record
from conftest import insert_family

PARENT_A = {"kind": "parent", "role": "A", "session_ref": "ab12cd34"}


def three(conn, now):
    insert_family(conn)
    for i in range(3):
        record.append(conn, "f1", "test.step", {"n": i}, PARENT_A, now=now)


def test_chain_ok_and_hashes_are_64_hex(conn, now):
    three(conn, now)
    evs = record.events(conn, "f1")
    assert [e["seq"] for e in evs] == [1, 2, 3] and all(len(e["hash"]) == 64 for e in evs)
    assert evs[0]["prev"] == "0" * 64 and record.check(conn, "f1") is None


def test_chain_detects_edit(conn, now):
    three(conn, now)
    conn.execute(sa.update(db.event).where(db.event.c.seq == 2).values(body_json='{"n": 99}'))
    assert record.check(conn, "f1") == 2


def test_chain_detects_deletion(conn, now):
    three(conn, now)
    conn.execute(sa.delete(db.event).where(db.event.c.seq == 2))
    assert record.check(conn, "f1") == 3


def test_actor_recorded(conn, now):
    three(conn, now)
    assert record.events(conn, "f1")[0]["actor"] == PARENT_A


def test_body_cannot_hold_document_text(conn, now):
    insert_family(conn)
    with pytest.raises(ValueError):
        record.append(conn, "f1", "x", {"rule": {"quote": "shall be paid 60%"}}, PARENT_A, now=now)
