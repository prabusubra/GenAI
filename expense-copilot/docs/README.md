# Expense Copilot — technical documentation

Expense Copilot is a private, local web app that analyzes bank statements from
all of one person's accounts together. It reads CSV, JSON and PDF statements,
categorizes every transaction, finds where the money was spent (state, city,
town, village), removes transfers between the person's own accounts, and shows
income, spending, money carried over and money left, with charts.

Everything runs on the user's own machine. Uploaded statements are processed in
memory and never written to disk or sent to any other service.

| Document | What it covers |
|---|---|
| [architecture.md](architecture.md) | Folder layout, request flow, each module's job, the processing pipeline, data model, API, front end, and the key algorithms |
| [technologies.md](technologies.md) | Every technology and library used, what it is used for, why it was chosen, and the alternatives that were considered |
| [development.md](development.md) | Setting up, running, testing, sample data, and how to extend the app |

## At a glance

| | |
|---|---|
| Language | Python 3.13 (back end), plain HTML/CSS/JavaScript (front end) |
| Web framework | FastAPI on Uvicorn |
| PDF reading | pdfplumber (on pdfminer.six) |
| Data validation | Pydantic v2 |
| Charts | Hand-written inline SVG, no chart library |
| Storage | None; statements live in memory for the length of one request |
| Tests | pytest, 51 tests; fpdf2 builds test PDFs |
| Size | ~1,000 lines of Python, ~1,200 lines of HTML/CSS/JS, 160+ built-in places |

## Design principles

1. **Private by default.** No database, no file storage, no external APIs, no
   CDN scripts. The browser only talks to the local server.
2. **Deterministic.** The same statements always give the same report. Rules
   (keywords, regular expressions, balance arithmetic) are used instead of
   machine learning, so every number can be traced back to a transaction.
3. **Money is exact.** All amounts are `Decimal`, never floating point.
4. **Explainable.** Anything the app decides on the user's behalf (an own-account
   transfer, a location, a category) is shown with its reason, and the user can
   override it.
5. **Small dependency footprint.** Four runtime libraries; the front end needs
   no build step.
