from decimal import Decimal
from pathlib import Path

from app.expense import analyze_statements
from app.own_accounts import OwnAccounts, find_account_number

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def _csv(*rows: str) -> bytes:
    return ("date,description,amount\n" + "\n".join(rows) + "\n").encode()


def _excluded(report) -> dict[str, str]:
    return {t.description: t.transfer_note for t in report.transactions if t.internal_transfer}


def test_account_number_is_read_from_pdf_header() -> None:
    assert find_account_number("Account number XXXX XXXX 1234") == "1234"
    assert find_account_number("A/C No: 50100012341234 Branch: MG Road") == "50100012341234"
    report = analyze_statements([("Salary", "statement_bank_style.pdf", (SAMPLES / "statement_bank_style.pdf").read_bytes())])
    assert report.accounts[0].account_number == "••1234"


def test_transfer_mentioning_my_other_account_is_excluded_even_without_its_statement() -> None:
    savings = _csv("2026-09-01,SALARY CREDIT ACME,50000", "2026-09-02,NEFT TO A/C XXXXXX9876 HDFC,-8000", "2026-09-03,SWIGGY ORDER,-500")
    report = analyze_statements([("Savings", "s.csv", savings, "1111")], other_account_numbers=["9876"])
    assert _excluded(report) == {"NEFT TO A/C XXXXXX9876 HDFC": "To your account ••9876"}
    assert report.total_spending == Decimal("500")
    assert (report.internal_transfer_total, report.internal_transfer_count) == (Decimal("8000"), 1)


def test_pair_between_uploaded_accounts_matched_by_account_number() -> None:
    savings = _csv("2026-09-02,IMPS TO XXXX5678,-8000")
    coop = _csv("2026-09-03,IMPS CR 998877,8000")  # the receiving side has no hint at all
    report = analyze_statements([("Savings", "s.csv", savings, "1234"), ("Co-op", "c.csv", coop, "5678")])
    assert _excluded(report) == {"IMPS TO XXXX5678": "Moved to Co-op (arrived 03 Sep)", "IMPS CR 998877": "Moved from Savings (sent 02 Sep)"}
    assert (report.total_income, report.total_spending, report.internal_transfer_count) == (Decimal("0"), Decimal("0"), 1)


def test_statement_mentioning_its_own_account_is_not_a_transfer() -> None:
    report = analyze_statements([("Savings", "s.csv", _csv("2026-09-01,NEFT CR TO A/C XXXX1234 FROM ACME CORP,30000"), "1234")])
    assert _excluded(report) == {}
    assert report.total_income == Decimal("30000")


def test_transfer_to_my_own_name() -> None:
    rows = _csv("2026-09-01,SALARY PRABU S ACME,50000", "2026-09-02,UPI/PRABU S/SBI/SAVINGS,-7000", "2026-09-03,UPI/RAVI KUMAR/GPAY,-700")
    report = analyze_statements([("Savings", "s.csv", rows)], owner_names="Prabu S")
    assert _excluded(report) == {"UPI/PRABU S/SBI/SAVINGS": "To your own name"}  # salary mentioning the name still counts as income
    assert (report.total_income, report.total_spending) == (Decimal("50000"), Decimal("700"))


def test_reference_numbers_ending_in_my_digits_are_not_matched() -> None:
    rows = _csv("2026-09-02,UPI/312345671234/RAVI KUMAR,-1500")
    report = analyze_statements([("Savings", "s.csv", rows)], other_account_numbers=["1234"])
    assert _excluded(report) == {}


def test_full_account_number_is_matched_anywhere() -> None:
    own = OwnAccounts.build({"50100012349876": None}, None)
    assert own.mentioned_account("NEFT-50100012349876-FD BOOKING", "Savings") == "9876"
    assert own.mentioned_account("NEFT-50100012341111-FRIEND", "Savings") is None
