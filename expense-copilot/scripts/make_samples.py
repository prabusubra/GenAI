"""Generate fake sample statements in every supported format.

Run from the project root:  python scripts/make_samples.py
Every file holds the same month of made-up transactions, so all of them should
produce the same report.
"""

import csv
import json
from decimal import Decimal
from pathlib import Path

from fpdf import FPDF, FontFace
from fpdf.enums import TableBordersLayout

OUT = Path(__file__).resolve().parent.parent / "samples"
OPENING_BALANCE = Decimal("25000.00")

# (date, description, amount) - negative = money out, positive = money in
TRANSACTIONS = [
    ("2026-09-01", "SALARY CREDIT ACME TECHNOLOGIES", "85000.00"),
    ("2026-09-01", "RENT TRANSFER TO LANDLORD NEFT", "-22000.00"),
    ("2026-09-02", "BIGBASKET ORDER 88213", "-2340.50"),
    ("2026-09-03", "SWIGGY FOOD ORDER BENGALURU", "-486.00"),
    ("2026-09-04", "UBER INDIA TRIP BANGALORE KA", "-312.75"),
    ("2026-09-05", "AIRTEL MOBILE RECHARGE", "-599.00"),
    ("2026-09-05", "UPI TO SELF ACCOUNT SAMPLE COOP BANK", "-10000.00"),
    ("2026-09-06", "NETFLIX SUBSCRIPTION", "-649.00"),
    ("2026-09-07", "AMAZON PAY SHOPPING", "-3899.00"),
    ("2026-09-08", "ATM CASH WITHDRAWAL MG ROAD BENGALURU", "-5000.00"),
    ("2026-09-09", "APOLLO PHARMACY MYSURU", "-742.30"),
    ("2026-09-10", "BESCOM ELECTRICITY BILL", "-1860.00"),
    ("2026-09-11", "THIRD WAVE COFFEE PUNE MH", "-410.00"),
    ("2026-09-12", "HP PETROL PUMP FUEL HOSUR TN", "-2500.00"),
    ("2026-09-13", "DMART SUPERMARKET CHENNAI", "-4120.80"),
    ("2026-09-14", "PVR CINEMA TICKETS KOCHI", "-760.00"),
    ("2026-09-15", "UPI TO RAVI KUMAR", "-1500.00"),
    ("2026-09-16", "FLIPKART REFUND", "1299.00"),
    ("2026-09-17", "ZOMATO ORDER BENGALURU", "-638.00"),
    ("2026-09-18", "ACT FIBERNET INTERNET BILL", "-1178.82"),
    ("2026-09-19", "METRO CARD TOP UP", "-500.00"),
    ("2026-09-20", "CULT FIT MEMBERSHIP", "-2499.00"),
    ("2026-09-21", "MELUKOTE TEMPLE STORE MANDYA", "-350.00"),
    ("2026-09-22", "STAR HEALTH INSURANCE PREMIUM", "-1850.00"),
    ("2026-09-24", "MYNTRA FASHION", "-2199.00"),
    ("2026-09-26", "SPOTIFY PREMIUM", "-119.00"),
    ("2026-09-28", "CITY CLINIC CONSULTATION MYSORE", "-800.00"),
    ("2026-09-30", "SAVINGS INTEREST", "212.40"),
]

# A second account at another (fake) bank - receives the self transfer above.
SECOND_ACCOUNT_OPENING = Decimal("5000.00")
SECOND_ACCOUNT = [
    ("2026-09-05", "IMPS FROM SELF ACCOUNT SAMPLE BANK", "10000.00"),
    ("2026-09-06", "FARM SUPPLY STORE HIWARE BAZAR", "-3200.00"),
    ("2026-09-08", "FREELANCE PAYMENT RECEIVED", "15000.00"),
    ("2026-09-10", "GRAMEEN KIRANA STORE PIN 571401", "-850.00"),
    ("2026-09-12", "MORE SUPERMARKET JAIPUR RJ", "-2150.00"),
    ("2026-09-15", "IRCTC TRAIN TICKET", "-1450.00"),
    ("2026-09-18", "HOTEL STAY UDAIPUR", "-4800.00"),
    ("2026-09-20", "HOMESTAY MAWLYNNONG MEGHALAYA", "-2500.00"),
    ("2026-09-22", "ELECTRICITY BILL JVVNL JAIPUR", "-1120.00"),
    ("2026-09-25", "ATM WDL HAZRATGANJ LUCKNOW", "-3000.00"),
    ("2026-09-28", "INTEREST CREDIT", "95.50"),
]


def _rows():
    """Yield (date, description, amount, running balance)."""
    balance = OPENING_BALANCE
    for date, description, amount in TRANSACTIONS:
        balance += Decimal(amount)
        yield date, description, Decimal(amount), balance


def _ddmmyyyy(iso: str) -> str:
    year, month, day = iso.split("-")
    return f"{day}/{month}/{year}"


def write_csv_signed() -> None:
    with open(OUT / "statement_signed.csv", "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "description", "amount"])
        for date, description, amount, _ in _rows():
            writer.writerow([date, description, amount])


def write_csv_debit_credit() -> None:
    with open(OUT / "statement_debit_credit.csv", "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Txn Date", "Narration", "Debit", "Credit", "Balance"])
        for date, description, amount, balance in _rows():
            debit, credit = (f"{-amount:,.2f}", "") if amount < 0 else ("", f"{amount:,.2f}")
            writer.writerow([_ddmmyyyy(date), description, debit, credit, f"{balance:,.2f}"])


def write_json() -> None:
    data = {"transactions": [
        {"date": date, "description": description, "amount": f"{abs(amount)}", "type": "debit" if amount < 0 else "credit", "currency": "INR"}
        for date, description, amount, _ in _rows()
    ]}
    (OUT / "statement.json").write_text(json.dumps(data, indent=2) + "\n")


def write_pdf_table(borders: TableBordersLayout = TableBordersLayout.ALL, name: str = "statement_table.pdf") -> None:
    pdf = FPDF()
    pdf.set_font("Helvetica", size=8)
    rows = list(_rows())
    for start in range(0, len(rows), 15):  # two pages, header repeated
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Sample Bank - Account Statement (FAKE DATA)", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=8)
        with pdf.table(col_widths=(18, 60, 22, 22, 22, 26), borders_layout=borders) as table:
            for row in [("Date", "Narration", "Chq./Ref.No.", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance")] + [
                (_ddmmyyyy(date), description, f"REF{start + i + 1:05d}", f"{-amount:,.2f}" if amount < 0 else "", f"{amount:,.2f}" if amount > 0 else "", f"{balance:,.2f}")
                for i, (date, description, amount, balance) in enumerate(rows[start:start + 15])
            ]:
                cells = table.row()
                for value in row:
                    cells.cell(value)
    pdf.output(str(OUT / name))


def write_pdf_no_row_lines() -> None:
    """Only vertical column lines - many banks print statements like this."""
    write_pdf_table(TableBordersLayout.NO_HORIZONTAL_LINES, "statement_no_row_lines.pdf")


def write_pdf_text() -> None:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Courier", size=8)
    lines = ["Sample Bank - Account Statement (FAKE DATA)", "", f"Opening Balance {'':>40}{OPENING_BALANCE:>12,.2f}", ""]
    for date, description, amount, balance in _rows():
        day, month = date[8:], ("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()[int(date[5:7]) - 1])
        lines.append(f"{day} {month} {date[:4]}  {description:<34}{abs(amount):>12,.2f}{balance:>14,.2f}")
    lines += ["", "Page 1 of 1"]
    for line in lines:
        pdf.cell(0, 5, line, new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(OUT / "statement_text.pdf"))


def write_second_account() -> None:
    balance = SECOND_ACCOUNT_OPENING
    with open(OUT / "second_account_coop_bank.csv", "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Value Date", "Particulars", "Withdrawals", "Deposits", "Balance"])
        for date, description, amount in SECOND_ACCOUNT:
            amount = Decimal(amount)
            balance += amount
            writer.writerow([_ddmmyyyy(date), description, f"{-amount:,.2f}" if amount < 0 else "", f"{amount:,.2f}" if amount > 0 else "", f"{balance:,.2f}"])


class _StatementPDF(FPDF):
    def header(self) -> None:
        self.set_fill_color(23, 64, 140)
        self.rect(0, 0, self.w, 22, style="F")
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 15)
        self.set_xy(12, 6)
        self.cell(0, 7, "SAMPLE BANK")
        self.set_font("Helvetica", size=8)
        self.set_xy(12, 13)
        self.cell(0, 5, "Savings Account Statement  |  SAMPLE DATA - NOT A REAL ACCOUNT")
        self.set_text_color(0, 0, 0)
        self.set_y(28)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(110, 110, 110)
        self.cell(0, 5, "This is a computer-generated sample statement for testing Expense Copilot.", align="L")
        self.cell(0, 5, f"Page {self.page_no()} of {{nb}}", align="R")


def write_pdf_realistic() -> None:
    rows = list(_rows())
    income = sum(amount for *_, amount, _ in rows if amount > 0)
    spending = -sum(amount for *_, amount, _ in rows if amount < 0)
    pdf = _StatementPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.set_font("Helvetica", size=9)
    details = [("Account holder", "Test User"), ("Account number", "XXXX XXXX 1234"), ("Branch", "Sample Branch, Bengaluru"),
               ("Statement period", "01/09/2026 to 30/09/2026"), ("Currency", "INR")]
    for label, value in details:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(38, 5.5, label)
        pdf.set_font("Helvetica", size=9)
        pdf.cell(0, 5.5, value, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    pdf.set_fill_color(240, 244, 251)
    pdf.set_draw_color(200, 210, 230)
    summary = [("Opening Balance", OPENING_BALANCE), ("Total Deposits", income), ("Total Withdrawals", spending), ("Closing Balance", rows[-1][3])]
    box_width = (pdf.w - pdf.l_margin - pdf.r_margin) / len(summary)
    top = pdf.get_y()
    for index, (label, value) in enumerate(summary):
        x = pdf.l_margin + index * box_width
        pdf.rect(x, top, box_width - 2, 15, style="DF")
        pdf.set_xy(x + 3, top + 2)
        pdf.set_font("Helvetica", size=7)
        pdf.cell(box_width - 8, 4, label.upper())
        pdf.set_xy(x + 3, top + 7)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(box_width - 8, 6, f"{value:,.2f}")
    pdf.set_y(top + 20)

    pdf.set_font("Helvetica", size=8)
    pdf.set_draw_color(190, 190, 190)
    long_narrations = {"RENT TRANSFER TO LANDLORD NEFT": "NEFT DR-SMPL0001234-RENT TRANSFER TO LANDLORD SEPTEMBER 2026 FLAT 402"}
    with pdf.table(col_widths=(18, 62, 22, 22, 22, 26), text_align=("LEFT", "LEFT", "LEFT", "RIGHT", "RIGHT", "RIGHT"),
                   headings_style=FontFace(emphasis="BOLD", fill_color=(23, 64, 140), color=(255, 255, 255)),
                   cell_fill_color=(246, 248, 252), cell_fill_mode="ROWS", line_height=5) as table:
        heading = table.row()
        for value in ("Date", "Narration", "Chq./Ref.No.", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"):
            heading.cell(value)
        for number, (date, description, amount, balance) in enumerate(rows, start=1):
            cells = table.row()
            for value in (_ddmmyyyy(date), long_narrations.get(description, description), f"UTR{number:08d}",
                          f"{-amount:,.2f}" if amount < 0 else "", f"{amount:,.2f}" if amount > 0 else "", f"{balance:,.2f}"):
                cells.cell(value)

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(0, 5, "*** End of statement ***", align="C")
    pdf.output(str(OUT / "statement_bank_style.pdf"))


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for write in (write_csv_signed, write_csv_debit_credit, write_json, write_pdf_table, write_pdf_text, write_pdf_realistic, write_pdf_no_row_lines, write_second_account):
        write()
    income = sum(Decimal(a) for _, _, a in TRANSACTIONS if Decimal(a) > 0)
    spending = -sum(Decimal(a) for _, _, a in TRANSACTIONS if Decimal(a) < 0)
    print(f"Wrote {len(TRANSACTIONS)} transactions to {OUT}/  expected: income {income}, spending {spending}, net {income - spending}")
