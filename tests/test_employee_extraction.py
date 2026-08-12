"""Tests for employee count parsing and phrase extraction."""

from ai_intel.extraction.employees import extract_employee_phrase, parse_employee_count


def test_parse_employee_count_exact_int() -> None:
    assert parse_employee_count(42) == 42
    assert parse_employee_count(0) == 0


def test_parse_employee_count_exact_strings() -> None:
    assert parse_employee_count("42") == 42
    assert parse_employee_count("1,250 employees") == 1250
    assert parse_employee_count("5 employees") == 5


def test_parse_employee_count_rejects_ranges_and_plus() -> None:
    # Must NOT inflate or estimate ranges artificially
    assert parse_employee_count("11-50 employees") is None
    assert parse_employee_count("11–50") is None
    assert parse_employee_count("500+ employees") is None
    assert parse_employee_count("100+") is None


def test_parse_employee_count_invalid_inputs() -> None:
    assert parse_employee_count(None) is None
    assert parse_employee_count("") is None
    assert parse_employee_count("unknown size") is None


def test_extract_employee_phrase() -> None:
    assert extract_employee_phrase("Company has 11-50 employees in SF") == "11-50 employees"
    assert extract_employee_phrase("Team: 500+ employee count") == "500+ employee"
    assert extract_employee_phrase("No company metrics here") is None
