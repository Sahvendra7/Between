"""Independent check: re-read every payment of a family from PayPal and check the record's chain.

  uv run python scripts/verify.py --family FID [--database-url URL]

Uses PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET (sandbox) from the environment or .env.
Exit 0 when every payment matches PayPal and the chain is intact; 1 otherwise.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import sqlalchemy as sa  # noqa: E402

from between import db, record  # noqa: E402
from between.reconcile import verify_payment  # noqa: E402

VERIFIER = {"kind": "system", "role": None, "session_ref": "verify.py"}


def run(engine, pp, family_id: str) -> int:
    bad = False
    with engine.begin() as conn:
        rows = conn.execute(sa.select(db.payment.c.id).join(db.expense, db.expense.c.id == db.payment.c.expense_id)
                            .where(db.expense.c.family_id == family_id, db.payment.c.status != "cancelled",
                                   db.payment.c.order_id.is_not(None)).order_by(db.payment.c.id)).scalars().all()
        for pid in rows:
            p = verify_payment(conn, pp, pid, VERIFIER, datetime.now(timezone.utc))
            err = p["last_error"] or ""
            bad |= err.startswith("mismatch") or p["verification"] != "verified"
            print(f"pay_{pid} {p['status']} {p['verification']} gross={p['gross_minor']} fee={p['fee_minor']} "
                  f"net={p['net_minor']} capture={p['capture_id']}{' ERROR ' + err if err else ''}")
        broken = record.check(conn, family_id)
    print(f"CHAIN BROKEN at {broken}" if broken else "CHAIN OK")
    return 1 if bad or broken else 0


def _env() -> dict:
    vals = dict(os.environ)
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                vals.setdefault(k.strip(), v.strip())
    return vals


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", required=True)
    ap.add_argument("--database-url")
    a = ap.parse_args()
    from between.config import load
    from between.payments import PayPal
    settings = load(_env())
    engine = db.make_engine(a.database_url or settings.database_url)
    return run(engine, PayPal(settings.paypal_client_id, settings.paypal_client_secret), a.family)


if __name__ == "__main__":
    sys.exit(main())
