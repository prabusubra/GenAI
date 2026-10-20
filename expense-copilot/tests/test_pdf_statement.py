from decimal import Decimal

import pytest
from fpdf import FPDF
from fpdf.enums import TableBordersLayout

from app.expense import StatementParseError, analyze, parse_statement

HEADER = ("Date", "Narration", "Chq./Ref.No.", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance")


def _table_pdf(pages: list[list[tuple[str, ...]]], borders: TableBordersLayout = TableBordersLayout.ALL) -> bytes:
    pdf = FPDF()
    pdf.set_font("Helvetica", size=8)
    for rows in pages:
        pdf.add_page()
        with pdf.table(borders_layout=borders, v_align="TOP") as table:
            for row in (HEADER, *rows):
                cells = table.row()
                for value in row:
                    cells.cell(value)
    return bytes(pdf.output())


def _text_pdf(lines: list[str]) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Courier", size=9)
    for line in lines:
        pdf.cell(0, 6, line, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def test_pdf_table_statement() -> None:
    content = _table_pdf([
        [
            ("01/09/26", "SALARY ACME CORP", "REF1", "", "80,000.00", "90,000.00"),
            ("02/09/26", "SWIGGY ORDER\nBANGALORE", "REF2", "450.00", "", "89,550.00"),
        ],
        [("05/09/26", "ATM CASH WITHDRAWAL", "REF3", "5,000.00", "-", "84,550.00")],
    ])
    transactions = parse_statement("statement.pdf", content)
    assert [t.amount for t in transactions] == [Decimal("80000.00"), Decimal("-450.00"), Decimal("-5000.00")]
    assert transactions[1].description == "SWIGGY ORDER BANGALORE"
    report = analyze(transactions)
    assert report.total_spending == Decimal("5450.00")
    assert report.category_spend[0].category == "Cash withdrawal"


def test_pdf_table_without_row_lines_splits_merged_rows() -> None:
    # With only vertical column lines, pdfplumber returns the whole body as one row
    # whose cells stack every value - and the sparse debit/credit columns have
    # fewer values than there are dates, so they must be matched by position.
    content = _table_pdf([[
        ("01/09/26", "SALARY ACME", "R1", "", "80,000.00", "90,000.00"),
        ("02/09/26", "NEFT DR RENT TRANSFER TO\nLANDLORD FLAT 402", "R2", "22,000.00", "", "68,000.00"),
        ("03/09/26", "SWIGGY ORDER", "R3", "3,000.00", "", "65,000.00"),
        ("04/09/26", "FLIPKART REFUND", "R4", "", "1,000.00", "66,000.00"),
    ]], borders=TableBordersLayout.NO_HORIZONTAL_LINES)
    transactions = parse_statement("statement.pdf", content)
    assert [t.amount for t in transactions] == [Decimal("80000.00"), Decimal("-22000.00"), Decimal("-3000.00"), Decimal("1000.00")]
    assert transactions[1].description == "NEFT DR RENT TRANSFER TO LANDLORD FLAT 402"


def test_pdf_text_statement_uses_balance_to_sign_amounts() -> None:
    content = _text_pdf([
        "Account Statement",
        "Opening Balance                          10,000.00",
        "01 Sep 2026  Refund from Flipkart     500.00   10,500.00",
        "02 Sep 2026  Uber trip                320.00   10,180.00",
        "03 Sep 2026  Netflix subscription     649.00    9,531.00",
        "Page 1 of 1",
    ])
    transactions = parse_statement("statement.pdf", content)
    assert [t.amount for t in transactions] == [Decimal("500.00"), Decimal("-320.00"), Decimal("-649.00")]
    assert transactions[2].description == "Netflix subscription"


def test_pdf_text_statement_with_dr_cr_markers() -> None:
    content = _text_pdf([
        "2026-09-01 Electricity bill 1,200.00 Dr",
        "2026-09-02 Interest 45.10 Cr",
    ])
    assert [t.amount for t in parse_statement("s.pdf", content)] == [Decimal("-1200.00"), Decimal("45.10")]


def test_scanned_pdf_reports_missing_text() -> None:
    pdf = FPDF()
    pdf.add_page()
    pdf.rect(10, 10, 50, 50)
    with pytest.raises(StatementParseError, match="no selectable text"):
        parse_statement("scan.pdf", bytes(pdf.output()))


def test_corrupt_pdf_is_rejected() -> None:
    with pytest.raises(StatementParseError, match="could not be read"):
        parse_statement("broken.pdf", b"%PDF-1.4 not really a pdf")


def test_password_protected_pdf_is_explained() -> None:
    pdf = FPDF()
    pdf.set_encryption(owner_password="owner", user_password="secret")
    pdf.add_page()
    with pytest.raises(StatementParseError, match="password-protected"):
        parse_statement("locked.pdf", bytes(pdf.output()))
