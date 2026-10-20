from decimal import Decimal

from app.expense import analyze_statements

SAVINGS = b"""date,description,amount
2026-09-01,SALARY CREDIT ACME,50000
2026-09-02,UPI TO SELF ACCOUNT,-10000
2026-09-03,SWIGGY ORDER BENGALURU,-500
2026-09-04,UPI TO FRIEND,-2000
"""
SECOND = b"""Value Date,Particulars,Withdrawals,Deposits
03/09/2026,IMPS FROM SELF ACCOUNT,,"10,000.00"
05/09/2026,FARM SUPPLY STORE HIWARE BAZAR,"12,000.00",
06/09/2026,UPI FROM FRIEND,,"2,000.00"
"""


def test_combined_report_excludes_own_account_transfers() -> None:
    report = analyze_statements([("Savings", "savings.csv", SAVINGS), ("Co-op", "coop.csv", SECOND)])
    assert report.internal_transfer_total == Decimal("10000")
    assert report.internal_transfer_count == 1
    # The 2,000 to/from a friend is not a self transfer: one side has no matching account.
    assert report.total_income == Decimal("52000.00")
    assert report.total_spending == Decimal("14500.00")
    accounts = {a.account: a for a in report.accounts}
    assert accounts["Co-op"].net_cash_flow == Decimal("-10000.00")
    assert accounts["Co-op"].top_category == "Farming"
    assert [p.name for p in report.place_spend] == ["Hiware Bazar", "Bengaluru"]
    assert report.state_spend[0].state == "Maharashtra"
    assert any("deficit" in insight for insight in report.insights)


def test_same_amount_without_transfer_wording_is_not_internal() -> None:
    first = b"date,description,amount\n2026-09-01,AMAZON ORDER,-999\n"
    second = b"date,description,amount\n2026-09-01,FLIPKART REFUND,999\n"
    report = analyze_statements([("A", "a.csv", first), ("B", "b.csv", second)])
    assert report.internal_transfer_count == 0


def test_same_label_merges_and_skips_overlap() -> None:
    august = b"date,description,amount\n2026-08-30,ZOMATO,-300\n2026-09-01,SALARY,1000\n"
    september = b"date,description,amount\n2026-09-01,SALARY,1000\n2026-09-02,UBER,-200\n"
    report = analyze_statements([("Savings", "aug.csv", august), ("Savings", "sep.csv", september)])
    assert [a.account for a in report.accounts] == ["Savings"]
    assert report.transaction_count == 3
    assert report.total_income == Decimal("1000")
    assert any("counted once" in warning for warning in report.warnings)


def test_identical_and_unreadable_files_are_skipped_with_warnings() -> None:
    report = analyze_statements([("A", "a.csv", SAVINGS), ("B", "copy.csv", SAVINGS), ("C", "notes.txt", b"hello")])
    assert [a.account for a in report.accounts] == ["A"]
    assert len(report.warnings) == 2


def test_transactions_from_all_statements_form_one_timeline() -> None:
    report = analyze_statements([("Savings", "savings.csv", SAVINGS), ("Co-op", "coop.csv", SECOND)])
    dates = [t.date for t in report.transactions]
    assert dates == sorted(dates)
    # Accounts are interleaved by date, not listed one statement after another.
    assert [t.account for t in report.transactions][:5] == ["Savings", "Savings", "Savings", "Co-op", "Savings"]
