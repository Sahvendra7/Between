from datetime import date, datetime
from types import SimpleNamespace

from between import schedule as SC

DOC1 = open("samples/agreements/plan1_rivera_okafor.txt").read()
QUOTE = "The Child lives with each parent on alternate weeks, changing over on Sundays at 6:00 p.m."


def fake(parsed, stop="end_turn"):
    p = lambda **kw: SimpleNamespace(stop_reason=stop, parsed_output=parsed)
    return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(parse=p)), messages=SimpleNamespace(parse=p))


def test_expand_alternate_weeks_plan1():
    s = {"pattern": "alternate_weeks", "changeover_weekday": 6, "changeover_time": "18:00",
         "anchor_date": "2026-11-01", "first_parent": "A"}
    ev = SC.expand(s, date(2026, 11, 1), 14)
    assert [(e["startDate"], e["endDate"], e["resourceId"]) for e in ev] == [
        ("2026-11-01T18:00:00", "2026-11-08T18:00:00", "A"), ("2026-11-08T18:00:00", "2026-11-15T18:00:00", "B")]


def test_expand_covers_window_before_anchor_and_without_anchor():
    s = {"pattern": "alternate_weeks", "changeover_weekday": 6, "changeover_time": "18:00",
         "anchor_date": "2026-11-15", "first_parent": "B"}
    ev = SC.expand(s, date(2026, 11, 1), 14)
    assert ev[0]["startDate"] <= "2026-11-01T18:00:00" and ev[0]["resourceId"] == "B"  # 11-01 is two weeks before: same parent
    assert SC.expand({**s, "anchor_date": None}, date(2026, 11, 1), 14) == []
    assert SC.expand({**s, "pattern": "none"}, date(2026, 11, 1), 14) == []


def test_schedule_quote_must_be_grounded():
    bad = SC.ExtractedSchedule(pattern="alternate_weeks", changeover_weekday=6, changeover_time="18:00",
                               quote="The Child alternates weekly", page=1, section="2.1")
    assert SC.extract_schedule(DOC1, client=fake(bad)) is None
    good = bad.model_copy(update={"quote": QUOTE})
    out = SC.extract_schedule(DOC1, client=fake(good))
    assert out["pattern"] == "alternate_weeks" and out["source"]["section"] == "2.1"


def test_schedule_time_must_appear_in_quote_and_model_never_sets_who_starts():
    bad = SC.ExtractedSchedule(pattern="alternate_weeks", changeover_weekday=6, changeover_time="17:00",
                               quote=QUOTE, page=1, section="2.1")
    assert SC.extract_schedule(DOC1, client=fake(bad)) is None
    assert "first_parent" not in SC.ExtractedSchedule.model_fields and "anchor_date" not in SC.ExtractedSchedule.model_fields


def test_no_client_or_refusal_means_no_schedule():
    assert SC.extract_schedule(DOC1, client=None) is None
    assert SC.extract_schedule(DOC1, client=fake(None, stop="refusal")) is None
