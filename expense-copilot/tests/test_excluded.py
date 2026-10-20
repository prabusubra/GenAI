from decimal import Decimal

from app.expense import analyze_statements

ROWS = b"""date,description,amount
2026-09-01,SALARY CREDIT ACME,85000
2026-09-02,PROPERTY ADVANCE NEFT,-60000
2026-09-03,SWIGGY ORDER,-500
2026-09-04,SWIGGY ORDER,-500
"""


def _report(excluded=None):
    return analyze_statements([("Savings", "s.csv", ROWS)], excluded_ids=excluded)


def test_ids_are_stable_and_unique() -> None:
    first, second = _report(), _report()
    ids = [t.id for t in first.transactions]
    assert ids == [t.id for t in second.transactions]
    assert len(set(ids)) == 4  # the two identical Swiggy orders still get different ids


def test_left_out_transactions_are_not_in_any_total() -> None:
    big = next(t for t in _report().transactions if t.description == "PROPERTY ADVANCE NEFT")
    report = _report({big.id})
    assert (report.total_income, report.total_spending) == (Decimal("85000"), Decimal("1000"))
    assert (report.excluded_count, report.excluded_spending, report.excluded_income) == (1, Decimal("60000"), Decimal("0"))
    assert [t.description for t in report.transactions if t.user_excluded] == ["PROPERTY ADVANCE NEFT"]
    assert report.accounts[0].total_spending == Decimal("1000")
    assert "Transfers" not in {c.category for c in report.category_spend}
    assert any("You left out 1 transaction" in insight for insight in report.insights)


def test_excluding_income_too() -> None:
    salary = next(t for t in _report().transactions if t.amount > 0)
    report = _report({salary.id})
    assert (report.total_income, report.excluded_income) == (Decimal("0"), Decimal("85000"))


def test_user_can_count_a_detected_own_account_transfer() -> None:
    rows = b"date,description,amount\n2026-09-01,SALARY CREDIT ACME,85000\n2026-09-02,UPI TO SELF ACCOUNT,-10000\n"
    files = [("Savings", "s.csv", rows)]
    transfer = next(t for t in analyze_statements(files).transactions if t.internal_transfer)
    report = analyze_statements(files, included_ids={transfer.id})
    counted = next(t for t in report.transactions if t.id == transfer.id)
    assert (counted.internal_transfer, counted.user_included, counted.category) == (False, True, "Transfers")
    assert report.total_spending == Decimal("10000") and report.internal_transfer_count == 0
    # leaving out wins when the same id is in both sets
    both = analyze_statements(files, excluded_ids={transfer.id}, included_ids={transfer.id})
    assert next(t for t in both.transactions if t.id == transfer.id).user_excluded
