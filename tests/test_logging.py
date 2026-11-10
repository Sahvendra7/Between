import logging
from types import SimpleNamespace

from between import extraction as X
from between import record, validate as V
from conftest import insert_family

CANARY = "ZEBRA-CANARY-7731"


def test_no_document_text_in_logs(caplog, conn, now):
    caplog.set_level(logging.DEBUG)
    doc = f"=== Page 1 ===\nSection 1\n1.1 {CANARY} Medical costs shall be paid 60% by the Father and 40% by the Mother.\n"
    parsed = X.Extraction(rules=[X.ExtractedRule(kind="split", category="medical", params=X.Params(shares=X.Shares(A=40, B=60)),
                                                 source=X.Source(quote=f"{CANARY} Medical costs", page=1, section="1.1"))],
                          ambiguities=[])
    parse = lambda **kw: SimpleNamespace(stop_reason="end_turn", parsed_output=parsed)
    client = SimpleNamespace(messages=SimpleNamespace(parse=parse), beta=SimpleNamespace(messages=SimpleNamespace(parse=parse)))
    raw = X.extract_rules(doc, {"A": "Mother", "B": "Father"}, client=client)
    v = V.validate(raw, doc, {"A": "Mother", "B": "Father"})
    insert_family(conn)
    record.append(conn, "f1", "ruleset.created", {"rules": len(v["rules"]), "refused": len(v["refused"])},
                  {"kind": "system", "role": None, "session_ref": None}, now=now)
    assert CANARY not in caplog.text
    assert any(r.name == "between.ai" for r in caplog.records)  # positive control: the module does log
