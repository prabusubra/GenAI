# Development guide

## Set up (once)

```bash
cd expense-copilot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`requirements.txt` holds both the runtime libraries (FastAPI, Uvicorn,
python-multipart, pdfplumber) and the development ones (pytest, fpdf2).

## Run

```bash
.venv/bin/uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. `--reload` restarts the server when a Python file
changes. `app/static/index.html` is read fresh on every request, so front-end
edits only need a browser refresh.

* API documentation: http://127.0.0.1:8000/docs
* Health check: http://127.0.0.1:8000/health
* "Address already in use": another server is on port 8000. Stop it
  (`kill $(lsof -t -iTCP:8000 -sTCP:LISTEN)`) or use `--port 8001`.

In the Claude desktop app the same server is defined in
`.claude/launch.json` as `expense-copilot`.

## Test

```bash
.venv/bin/python -m pytest -q
```

| Test file | Covers |
|---|---|
| `test_expense.py` | A basic CSV analysis |
| `test_pdf_statement.py` | PDF tables (with and without row lines), plain-text PDFs, Dr/Cr markers, scanned, corrupt and password-protected files |
| `test_samples.py` | Every file in `samples/` gives the same totals |
| `test_location.py` | Cities, aliases, villages, towns, state codes, PIN codes, and phrases that must *not* be places |
| `test_multi_account.py` | Combining accounts, transfer pairing, merging months, duplicate files, date-ordered timeline |
| `test_own_accounts.py` | Account numbers from PDF headers, transfers to other own accounts, the user's name, false-positive guards |
| `test_opening_balance.py` | Opening balance from the balance column, newest-first statements, Cr/Dr balances, typed values, money left |
| `test_excluded.py` | Stable IDs, leaving transactions out, counting a detected transfer anyway |

## Sample data

`samples/` holds fake statements (made-up names, banks and numbers) in every
supported format: CSV with a signed amount column, CSV with debit/credit
columns, JSON, a ruled-table PDF, a table PDF with no row lines, a plain-text
PDF, a bank-style PDF, and a second account. Regenerate them after editing the
transaction lists in the script:

```bash
.venv/bin/python scripts/make_samples.py
```

## Common changes

| To… | Edit |
|---|---|
| Add or reorder a spending/income category | `CATEGORY_KEYWORDS` / `INCOME_KEYWORDS` in `app/expense.py` (first match wins) |
| Add towns or villages | `app/data/places.csv`, or a separate CSV set in `EXPENSE_COPILOT_PLACES` |
| Recognise another column name | the name lists in `_row_to_transaction` (`app/expense.py`) and `_canonical_header` (`app/pdf_statement.py`) |
| Accept another date format | `DATE_FORMATS` in `app/expense.py` and `DATE_PATTERN` in `app/pdf_statement.py` |
| Change the large-transaction limit | `LARGE_AMOUNT` in `app/static/index.html` |
| Change the own-transfer pairing window | `INTERNAL_TRANSFER_DAYS` in `app/expense.py` |
| Change upload limits | `MAX_FILE_SIZE_BYTES`, `MAX_FILES` (`app/expense.py`), `MAX_PAGES` (`app/pdf_statement.py`) |

## Conventions

* Money is always `Decimal`; convert to a number only for display in the browser.
* Analysis steps return new objects (`model_copy(update=...)`) instead of
  changing existing ones.
* Anything decided for the user carries a reason that the page shows
  (`transfer_note`, location, category), and the user can override it.
* Add a test for each new rule, including at least one case it must *not*
  match.
