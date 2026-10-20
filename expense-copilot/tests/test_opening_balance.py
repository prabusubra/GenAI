from decimal import Decimal

from app.expense import analyze_statements


def _run(*files):
    return analyze_statements(list(files))


ASCENDING = b"""date,description,debit,credit,balance
01/09/2026,SALARY CREDIT ACME,,"50,000.00","70,000.00"
02/09/2026,SWIGGY ORDER,500.00,,"69,500.00"
03/09/2026,RENT TRANSFER NEFT,"30,000.00",,"39,500.00"
"""


def test_opening_balance_from_balance_column_counts_as_base_amount() -> None:
    report = _run(("Savings", "s.csv", ASCENDING))
    assert report.opening_balance == Decimal("20000.00")
    assert report.total_income == Decimal("50000.00")  # the base amount is not income
    assert report.money_available == Decimal("70000.00")
    assert report.left_at_end == Decimal("39500.00")
    assert report.accounts[0].closing_balance == Decimal("39500.00")
    assert any("carried over" in insight for insight in report.insights)


def test_newest_first_statement() -> None:
    newest_first = b"""date,description,amount,balance
2026-09-03,RENT TRANSFER NEFT,-30000,39500
2026-09-02,SWIGGY ORDER,-500,69500
2026-09-01,SALARY CREDIT ACME,50000,70000
"""
    assert _run(("Savings", "s.csv", newest_first)).opening_balance == Decimal("20000")


def test_balances_with_cr_dr_suffix() -> None:
    rows = b"date,description,amount,balance\n2026-09-01,SWIGGY ORDER,-500,\"1,500.00 Cr\"\n2026-09-02,ATM CASH,-2000,500.00 Dr\n"
    report = _run(("Savings", "s.csv", rows))
    assert report.opening_balance == Decimal("2000.00")
    assert report.accounts[0].closing_balance == Decimal("-500.00")


def test_typed_opening_balance_wins_and_missing_one_is_reported() -> None:
    no_balance = b"date,description,amount\n2026-09-01,SWIGGY ORDER,-500\n"
    report = _run(("Savings", "s.csv", ASCENDING, None, "25,000"), ("Wallet", "w.csv", no_balance))
    assert report.opening_balance == Decimal("25000")
    assert report.accounts_without_opening == ["Wallet"]
    assert _run(("Wallet", "w.csv", no_balance)).opening_balance is None


def test_two_months_of_one_account_use_the_earlier_opening() -> None:
    august = b"date,description,amount,balance\n2026-08-05,SALARY,40000,50000\n"
    september = b"date,description,amount,balance\n2026-09-05,SALARY,40000,90000\n"
    report = _run(("Savings", "sep.csv", september), ("Savings", "aug.csv", august))
    assert report.opening_balance == Decimal("10000")
    assert report.left_at_end == Decimal("90000")


def test_spending_paid_from_money_carried_over() -> None:
    rows = b"date,description,amount,balance\n2026-09-01,SALARY,10000,30000\n2026-09-02,RENT NEFT,-15000,15000\n"
    report = _run(("Savings", "s.csv", rows))
    assert report.left_at_end == Decimal("15000")
    assert any("came out of the money carried over" in insight for insight in report.insights)
