# Expense Copilot

A private, local spending analyzer for **all of a person's bank accounts**. Upload
CSV, JSON, or PDF statements from several banks at once and get one combined
report: income, spending, surplus/deficit, categories, a per-account breakdown,
and where the money was spent (state, city, town, village). Uploads are parsed
in memory only and are not saved; nothing is sent to any outside service.

Technical documentation (architecture, technologies and libraries with the
reasons for choosing them, development guide) is in [`docs/`](docs/README.md).

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000` to upload a statement.

## CSV columns

Use a date field (`date`, `transaction_date`, `txn_date`, or `value_date`), a
description field (`description` or `narration`), and either `amount` or
`debit`/`credit`. Use a `type` column (`debit`/`credit`) with unsigned amount
files.

## PDF statements

Text-based PDFs (the kind you download from net banking) are supported:

- **Tables** with a header row such as `Date | Narration | Withdrawal Amt. |
  Deposit Amt. | Closing Balance` are read across pages; multi-line
  narrations are joined.
- **Plain text lines** that start with a date and end with amounts are read as
  a fallback. The sign comes from `Dr`/`Cr` markers, a minus sign, or the
  change in the running balance (an `Opening Balance` line helps).

Scanned/image-only PDFs need OCR and are not supported yet, and
password-protected PDFs must be unlocked first. CSV export is still the most
reliable option.

## Multiple accounts

Add several statements and give each an account name (it defaults to the file
name). Statements with the **same name are merged** as one account (e.g. August
and September of the same savings account); transactions that appear in both
because the periods overlap are counted once.

Money moved **between your own accounts** is excluded from income and spending.
A transfer (UPI/NEFT/IMPS/RTGS, never salary, interest, refunds or shop
payments) is treated as yours when its narration:

- mentions one of **your other accounts**: masked (`XXXXXX1234`, `**1234`),
  labelled (`A/C 1234`) or, if you typed the full number, the full number.
  Account numbers are read from PDF statement headers ("Account number ...")
  or typed next to each file (last 4 digits are enough); accounts without an
  uploaded statement go in *Your other accounts*;
- mentions **your own name** as banks print it (e.g. `UPI/PRABU S/...`), entered
  under *Your own accounts*;
- says `SELF` / `OWN A/C`.

This works even when only one side's statement is uploaded. When both are, the
debit and the matching credit (same amount, within 3 days) are paired. Each
excluded row shows why ("To your account ••9876", "Moved to Co-op ...").

API: `POST /statements/analyze-many` with repeated `statements` files and
optional matching `labels` and `account_numbers` form fields, plus optional
`owner_names` and `other_accounts` (comma-separated). `POST /statements/analyze` still takes a
single `statement`.

## Opening balance (money carried over)

Each statement's opening balance is treated as the base amount carried over
from last month, not as income: *money available* = opening balance + income,
and *left at end* = money available − spending. It is taken from the box next
to the file if you type it, otherwise worked out from the statement's Balance
column (first row's balance minus its amount; newest-first statements are
detected), otherwise from an "Opening Balance" line in a PDF. With several
accounts the openings are added up; for several months of one account the
earliest month's opening is used. The Accounts table also shows each account's
closing balance (opening + every transaction), which should match the bank.

## Choosing what to count

Every row in the transactions table has a tick box: ticked rows are counted,
unticked rows are struck through and left out of every total and chart. Untick
any expense or income you don't want in the analysis, or tick an own-account
transfer the app left out if it is really income or spending. *Count all shown*
and *Leave out all shown* apply to the rows matching the current filters (e.g.
one category or account); *Reset* undoes all your changes. The API takes the
ids as repeated `excluded` and `included` form fields.

## Large transactions

Before showing results, the app lists every transaction over ₹50,000 (money in
or out) and asks which to include, e.g. to leave out a one-off property payment
or a loan. Left-out transactions stay in the transactions list, struck through,
but are not in any total or chart. Change your choice later with *Review large
transactions* above the results. The limit is `LARGE_AMOUNT` in
`app/static/index.html`; the API takes the left-out transaction ids as repeated
`excluded` form fields.

## Locations

Places are read from transaction descriptions, offline:

- **City / town / village** names from [`app/data/places.csv`](app/data/places.csv)
  (about 150 cities built in, plus a few example towns and villages). Add your own towns and villages there; the most
  specific match wins (village > town > city). Set `EXPENSE_COPILOT_PLACES` to
  the path of an extra CSV with the same columns to keep your list separate.
- **State** names, and two-letter state codes at the end of POS narrations
  (`... HOSUR TN`).
- **PIN codes** written as `PIN 571401` or `...-571401` are mapped to their
  state by prefix (approximate near state borders).

Online payments (Amazon, Netflix, UPI to a person) usually carry no place, so
they appear as "no location".

## Samples

`samples/` holds fake statements for testing; regenerate them with
`python scripts/make_samples.py`. Upload `statement_bank_style.pdf` together
with `second_account_coop_bank.csv` to see the multi-account view, including a
self transfer and village-level spending.
