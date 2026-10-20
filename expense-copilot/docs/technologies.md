# Technologies and libraries

Versions are the ones installed in `.venv` at the time of writing. Allowed
ranges are in [`requirements.txt`](../requirements.txt).

## Summary

| Technology | Version | Used for | Runtime or dev |
|---|---|---|---|
| Python | 3.13 | All server-side code | runtime |
| FastAPI | 0.141 | HTTP endpoints, request parsing, response validation, API docs | runtime |
| Starlette | 1.6 | The web toolkit underneath FastAPI (comes with it) | runtime |
| Pydantic | 2.13 | Data models, validation, JSON serialization (comes with FastAPI) | runtime |
| Uvicorn (`[standard]`) | 0.52 | The web server that runs the app | runtime |
| python-multipart | 0.0.32 | Reading uploaded files from forms | runtime |
| pdfplumber | 0.11 | Reading text, words and tables out of PDF statements | runtime |
| pdfminer.six | 20260107 | PDF parsing engine underneath pdfplumber (comes with it) | runtime |
| pytest | 8.4 | Running the test suite | dev |
| fpdf2 | 2.8 | Generating PDF statements for tests and samples | dev |
| HTML, CSS, JavaScript | — | The whole user interface, in one file | runtime (browser) |
| SVG | — | All charts, drawn by hand-written code | runtime (browser) |

## Back end

### Python 3.13
**Purpose:** the language for the server, parsing and analysis.

**Why:**
* `decimal.Decimal` gives exact money arithmetic out of the box. A rupee
  amount like 0.10 + 0.20 must be exactly 0.30, which binary floats can't
  guarantee.
* The standard library already covers most of the work: `csv`, `json`, `re`
  (regular expressions), `datetime`, `hashlib`, `dataclasses`, `functools` and
  `pathlib`.
* The best PDF-reading libraries are in Python.
* Modern syntax keeps the code short: `X | None` types, the walrus operator
  `:=` and f-strings.

**Standard-library modules and what they do here:**

| Module | Used for |
|---|---|
| `decimal` | Every amount, balance and total |
| `csv`, `json` | Reading CSV and JSON statements; loading `places.csv` |
| `re` | Matching column names, dates, amounts, keywords, account numbers, PIN codes |
| `datetime` | Parsing ten date formats (`2026-09-01`, `01/09/26`, `1 Sep 2026`, …) |
| `hashlib` | SHA-256 to spot the same file uploaded twice; SHA-1 for stable transaction IDs |
| `collections.defaultdict` | Grouping totals by category, account, place and day |
| `dataclasses` | The small `OwnAccounts` helper |
| `functools.lru_cache` | Loading and indexing the places list once per process |
| `io`, `pathlib` | Handing uploaded bytes to the PDF reader; locating data files |

### FastAPI
**Purpose:** defines the endpoints (`/`, `/health`, `/statements/analyze`,
`/statements/analyze-many`), reads the uploaded files and form fields, and
returns the report as JSON.

**Why:**
* Declaring a parameter as `list[UploadFile]` or `list[str] = Form(...)` is
  enough; FastAPI parses and validates the request.
* `response_model=ExpenseReport` validates every response against the Pydantic
  model, so the front end always gets the shape it expects.
* Interactive API documentation is generated at `/docs` for free.
* It's fast and needs very little code: `main.py` is about 70 lines.

**Alternatives considered:**
* **Flask:** manual request parsing, and no validation or API docs without extra plugins.
* **Django:** a full framework with an ORM and admin, far more than an app with no database needs.

### Pydantic v2
**Purpose:** the data models in `models.py` (`Transaction`, `ExpenseReport`,
…). They validate statement rows (for example, a description must not be empty
and a currency is 3 letters) and serialize `Decimal` and `date` values to JSON
safely.

**Why:** it comes with FastAPI, gives type-checked models with one line per
field, and `model_copy(update=...)` keeps the analysis steps free of side
effects: each step returns new transactions instead of changing old ones.

### Uvicorn (with the `standard` extras)
**Purpose:** the web server that runs the app (`uvicorn app.main:app`).

**Why:** it's the standard server for FastAPI, and `--reload` restarts it when
code changes. The `standard` extras add:
* `uvloop` and `httptools`: a faster event loop and HTTP parser.
* `watchfiles`: efficient file watching for `--reload`.
* `websockets`: not used by this app, but part of the standard bundle.

It listens on `127.0.0.1` by default, so the app is reachable only from the
same computer.

### python-multipart
**Purpose:** decodes `multipart/form-data`, the format browsers use to upload
files.

**Why:** FastAPI needs it for any `File(...)` or `Form(...)` parameter; there is
no upload support without it.

## PDF reading

### pdfplumber (on pdfminer.six)
**Purpose:** reads PDF statements. The app uses:
* `page.extract_tables()` / `page.find_tables()`: finds ruled tables and the
  position of every row and cell.
* `page.extract_words()`: every word with its x/y position. This is what lets
  the app put each amount under the right column when a bank's table has no
  horizontal lines.
* `page.extract_text()`: the plain-text fallback, plus the statement header
  (account number, "Opening Balance").

**Why:**
* It exposes word **positions**, not just text. Bank statements are laid out
  visually, and positions are the only reliable way to tell a Withdrawal
  amount from a Deposit amount.
* It's pure Python plus pdfminer.six, so there is nothing else to install: no
  Java, Ghostscript or OpenCV.
* It reports password-protected and corrupt files as distinct errors, which
  the app turns into clear messages.

It also installs `pypdfium2` and `Pillow`. pdfplumber uses them for rendering
pages to images, which the app doesn't need for parsing; they were used once
during development to preview sample PDFs.

**Alternatives considered:**

| Library | Why not |
|---|---|
| PyPDF2 / pypdf | Text only, no word positions or table detection |
| Camelot | Needs Ghostscript/OpenCV, heavy to install |
| tabula-py | Needs a Java runtime |
| PyMuPDF | Capable, but AGPL-licensed |
| OCR (Tesseract) | Needed only for scanned PDFs; heavy and less accurate; left out on purpose (CSV export is recommended instead) |

## Testing and sample data

### pytest
**Purpose:** runs the 51 tests in `tests/`. They cover:
* every file format, and PDFs with and without row lines;
* categories and locations;
* own-account transfers;
* opening balances, duplicates and merged statements;
* user choices about what to count.

**Why:** the standard Python test runner. Plain `assert` statements,
`@pytest.mark.parametrize` for table-driven tests such as the location cases,
and `pytest.raises` for error messages.

Tests call the analysis functions directly instead of going through HTTP. This
keeps them fast (about 0.6 s for the whole suite) and avoids an extra HTTP
client dependency.

### fpdf2
**Purpose:**
* builds real PDF statements inside tests: ruled tables, tables with no row
  lines, plain-text layouts, scanned-like pages with no text, and
  password-protected files;
* generates the sample PDFs in `samples/` (`scripts/make_samples.py`).

**Why:** it's pure Python, can draw tables with different border layouts (which
reproduced a real bank-statement bug), and can encrypt files. Tests therefore
don't depend on anyone's real statements, which would be private.

## Front end

### Plain HTML, CSS and JavaScript (one file)
**Purpose:** the whole user interface in `app/static/index.html`:
* uploading files and naming accounts;
* the review window for large transactions;
* tiles, charts and tables;
* filters and tick boxes.

**Why:**
* **Privacy:** no scripts, fonts or styles are loaded from other sites, so
  nothing about the user's finances can leak to a CDN.
* **No build step:** no Node.js, bundler or `node_modules`. The server just
  reads the file, so editing it and reloading the browser is enough.
* **Small:** about 1,200 lines in total, using modern browser features instead
  of libraries.

**Browser features used:**

| Feature | Used for |
|---|---|
| `fetch` + `FormData` | Uploading files and choices to the API |
| `Intl.NumberFormat("en-IN")` | Indian currency formatting (₹1,01,606.90) and compact labels (₹1.2L) |
| `Intl.DateTimeFormat` | Dates like "Tue, 1 Sept" |
| `<dialog>` | The large-transaction review window (focus handling and Escape key built in) |
| `ResizeObserver` | Redrawing charts when their container changes size |
| CSS custom properties + `prefers-color-scheme` | Light and dark themes from one set of colour tokens |
| CSS grid | Tiles, upload rows and two-column layouts that collapse on phones |
| `localStorage` | Remembering only the user's name and other account numbers between visits |
| Drag and drop (`dragover` / `drop`) | Dropping statement files onto the upload box |

### SVG charts, written by hand
**Purpose:**
* **horizontal bars:** categories, locations, spending days sorted by amount;
* **paired bars:** income and spending per account;
* **stacked columns:** spending by date, split by category, with income markers;
* **line chart:** cumulative money available vs spending.

**Why not a chart library (Chart.js, D3, ECharts)?**
* It would have to be bundled or loaded from a CDN; a CDN goes against the
  privacy rule above.
* The charts need details that are simpler to write than to configure:
  * a fixed colour per category that survives filtering;
  * ▲ markers for income days;
  * a 2px gap between stacked segments;
  * tooltips listing the day's biggest expenses;
  * clicking a bar to filter the transactions table.
* Each chart is 50–100 lines of plain code, which is easy to read and change.

The category colours come from a validated palette, checked for colour-blind
separation and contrast in both light and dark modes. Blue always means
income, orange spending, and green/red only surplus/deficit.

## Data files

### `app/data/places.csv`
**Purpose:** the list of places the app recognises in narrations (about 150
cities, plus example towns and villages, with aliases such as Bangalore →
Bengaluru and Bombay → Mumbai), along with district and state.

**Why a CSV:** anyone can add their own towns and villages in a text editor or
spreadsheet without touching code. India has hundreds of thousands of villages,
so the list is meant to be extended by the user. A second file can be added
with the `EXPENSE_COPILOT_PLACES` environment variable.

## Deliberately not used

| Not used | Reason |
|---|---|
| Database (SQLite, PostgreSQL) | Statements are private; keeping them only in memory for one request means nothing can leak later |
| AI / LLM categorisation | Sending bank narrations to an external model would break the privacy promise; keyword rules are predictable, explainable and free |
| OCR | Only needed for scanned PDFs; heavy to install and error-prone on financial tables |
| Front-end framework (React, Vue) | One page with no build step is enough and easier to maintain |
| CDN-hosted libraries | Would let a third party see that the page was opened |
| Floating-point money | `Decimal` avoids rounding errors in totals |
