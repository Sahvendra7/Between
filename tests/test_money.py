import pytest

from between.money import MoneyError, fee_estimate, fmt_usd, parse_usd, split_amount


def test_parse_usd_cases():
    assert parse_usd("$1,234.5") == 123450 and parse_usd("12") == 1200 and parse_usd(" 420.00 ") == 42000
    for bad, code in [("12.345", "too_many_decimals"), ("-5", "not_positive"), ("0", "not_positive"),
                      ("1e3", "format"), ("", "empty"), ("1000000.01", "too_large"), ("12,34", "format")]:
        with pytest.raises(MoneyError) as e:
            parse_usd(bad)
        assert e.value.code == code, bad


def test_fmt_usd():
    assert fmt_usd(123450) == "$1,234.50" and fmt_usd(5) == "$0.05"


def test_fee_estimate_matches_sandbox():
    assert fee_estimate(25200) == 928 and fee_estimate(100) == 52 and fee_estimate(25000) == 922


def test_cents_always_add_up():
    assert split_amount(10001, {"A": 40, "B": 60}) == {"A": 4000, "B": 6001}
    for cents in range(1, 400):
        assert sum(split_amount(cents, {"A": 33, "B": 67}).values()) == cents
