from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from app.expense import MAX_FILES, StatementParseError, analyze_statements
from app.models import ExpenseReport

INDEX_HTML = Path(__file__).resolve().parent / "static" / "index.html"

app = FastAPI(title="Expense Copilot", version="0.1.0", description="Private, in-memory bank-statement spending analysis.")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _label(filename: str) -> str:
    return Path(filename).stem.replace("_", " ").strip() or "Statement"


@app.post("/statements/analyze", response_model=ExpenseReport)
async def analyze_statement(statement: UploadFile = File(...)) -> ExpenseReport:
    try:
        filename = statement.filename or "statement"
        return analyze_statements([(_label(filename), filename, await statement.read())])
    except StatementParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await statement.close()


@app.post("/statements/analyze-many", response_model=ExpenseReport)
async def analyze_many(statements: list[UploadFile] = File(...), labels: list[str] = Form(default=[]),
                       account_numbers: list[str] = Form(default=[]), owner_names: str = Form(default=""),
                       other_accounts: str = Form(default=""), excluded: list[str] = Form(default=[]),
                       included: list[str] = Form(default=[]), opening_balances: list[str] = Form(default=[])) -> ExpenseReport:
    """Combine statements from several accounts. labels[i] names the account for statements[i]
    (defaults to the file name); statements with the same label are treated as one account.

    Transfers between the user's own accounts are not income or spending. They are recognised by
    account_numbers[i] (the number of statements[i], last 4 digits are enough; read from the statement
    when blank), other_accounts (comma-separated numbers of the user's accounts with no statement
    uploaded) and owner_names (comma-separated, how banks print the user's name on transfers).
    excluded lists transaction ids (from a previous report) to leave out of every total; included lists ids
    to count even though they look like transfers between the user's own accounts. opening_balances[i] is the
    money carried over into statements[i] (worked out from the statement when blank)."""
    try:
        if len(statements) > MAX_FILES:
            raise StatementParseError(f"Upload at most {MAX_FILES} statements at a time.")
        files = []
        for index, upload in enumerate(statements):
            filename = upload.filename or f"statement-{index + 1}"
            label = labels[index].strip() if index < len(labels) and labels[index].strip() else _label(filename)
            number = account_numbers[index].strip() if index < len(account_numbers) else ""
            opening = opening_balances[index].strip() if index < len(opening_balances) else ""
            files.append((label[:60], filename, await upload.read(), number or None, opening or None))
        others = [number.strip() for number in other_accounts.split(",") if number.strip()]
        return analyze_statements(files, owner_names, others, set(excluded), set(included))
    except StatementParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        for upload in statements:
            await upload.close()
