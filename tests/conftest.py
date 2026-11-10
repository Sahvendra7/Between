import os
from datetime import datetime, timezone

import pytest
import sqlalchemy as sa

from between import db


@pytest.fixture
def engine():
    url = os.environ.get("TEST_DATABASE_URL", "sqlite://")
    eng = db.make_engine(url)
    if url.startswith("postgresql"):
        db.metadata.drop_all(eng)  # test database only
    db.init_db(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def conn(engine):
    with engine.begin() as c:
        yield c


@pytest.fixture
def now():
    return datetime(2026, 11, 11, 9, 0, tzinfo=timezone.utc)


def insert_family(conn, fid="f1"):
    conn.execute(sa.insert(db.family).values(id=fid, created_at=datetime(2026, 11, 1, tzinfo=timezone.utc), currency="USD"))
    return fid


def insert_expense(conn, eid="e1", fid="f1", sha="r1"):
    conn.execute(sa.insert(db.expense).values(
        id=eid, family_id=fid, paid_by="A", category="medical", amount_minor=42000,
        incurred_on="2026-10-01", requested_on="2026-10-05", receipt_sha256=sha, emergency=False, status="decided"))
    return eid
