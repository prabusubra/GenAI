from decimal import Decimal

from app.expense import analyze, parse_statement


def test_statement_analysis() -> None:
    transactions = parse_statement(
        "statement.csv",
        b"date,description,debit,credit\n2026-08-01,Salary,0,50000\n2026-08-02,BigBasket,1250,0\n2026-08-03,Uber,320,0\n",
    )
    report = analyze(transactions)
    assert report.total_spending == Decimal("1570")
    assert report.category_spend[0].category == "Groceries"
