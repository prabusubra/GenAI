"""Extract transaction rows from text-based (not scanned) PDF bank statements.

Rows are returned as plain dicts with canonical keys (date, description, debit,
credit, amount, type) so they go through the same validation as CSV rows.
"""

import io
import re
from decimal import Decimal, InvalidOperation

import pdfplumber

MAX_PAGES = 200
DATE_PATTERN = r"(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}[ -][A-Za-z]{3}[ -]\d{2,4})"
DATE_RE = re.compile(rf"^\s*({DATE_PATTERN})\b")
AMOUNT_RE = re.compile(r"(?<![\w.])(-?\(?[\d,]*\d\.\d{2}\)?)(?:\s*(Dr|Cr|DR|CR)\b)?")
CREDIT_HINTS = ("salary", "refund", "interest", "cashback", "deposit", "reversal", "received", "credit")


class PdfStatementError(ValueError):
    pass


def _canonical_header(header: str) -> str | None:
    text = re.sub(r"[^a-z]+", " ", header.lower()).strip()
    words = set(text.split())
    if not text:
        return None
    if "balance" in text:
        return "balance"  # running/closing balance: used to work out the opening balance
    if "date" in words:
        return "date"
    if words & {"narration", "description", "particulars", "details", "remarks", "transaction"}:
        return "description"
    if words & {"withdrawal", "withdrawals", "debit", "debits", "dr"}:
        return "debit"
    if words & {"deposit", "deposits", "credit", "credits", "cr"}:
        return "credit"
    if "amount" in words:
        return "amount"
    if "type" in words:
        return "type"
    return None


def _header_mapping(cells: list[str]) -> dict[int, str] | None:
    mapping: dict[int, str] = {}
    for index, cell in enumerate(cells):
        key = _canonical_header(cell)
        if key and key not in mapping.values():
            mapping[index] = key
    has_amount = {"debit", "credit", "amount"} & set(mapping.values())
    return mapping if {"date", "description"} <= set(mapping.values()) and has_amount else None


def _inside(word: dict, bbox: tuple) -> bool:
    x0, top, x1, bottom = bbox
    return x0 <= (word["x0"] + word["x1"]) / 2 <= x1 and top <= (word["top"] + word["bottom"]) / 2 <= bottom


def _lines(words: list[dict], tolerance: float = 3) -> list[list[dict]]:
    lines: list[list[dict]] = []
    for word in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if lines and abs(lines[-1][0]["top"] - word["top"]) <= tolerance:
            lines[-1].append(word)
        else:
            lines.append([word])
    return lines


def _column_texts(words: list[dict], columns: list[tuple[float, float, str]]) -> dict[str, str]:
    """Assign each word to the column whose x-range is closest to the word's centre."""
    texts: dict[str, list[str]] = {}
    for word in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        centre = (word["x0"] + word["x1"]) / 2
        _, _, key = min(columns, key=lambda col: 0 if col[0] <= centre <= col[1] else min(abs(centre - col[0]), abs(centre - col[1])))
        texts.setdefault(key, []).append(word["text"])
    return {key: " ".join(parts) for key, parts in texts.items()}


def _rows_from_tables(pdf) -> list[dict[str, str]]:
    """Read ruled tables by word position, not by cell text.

    Many bank PDFs only draw vertical column lines, so pdfplumber sees the whole
    table body as one row whose cells hold many stacked values. Positions let us
    split that back into one transaction per date line, even when sparse
    debit/credit columns have fewer values than there are dates.
    """
    rows: list[dict[str, str]] = []
    columns: list[tuple[float, float, str]] | None = None  # (x0, x1, canonical key); "" = ignored column
    for page in pdf.pages:
        words = page.extract_words()
        for table in page.find_tables():
            for row in table.rows:
                row_words = [word for word in words if _inside(word, row.bbox)]
                cells = [cell for cell in row.cells if cell]
                texts = [" ".join(w["text"] for w in sorted(row_words, key=lambda w: (round(w["top"]), w["x0"])) if _inside(w, cell)) for cell in cells]
                if header := _header_mapping(texts):
                    columns = [(cell[0], cell[2], header.get(index, "")) for index, cell in enumerate(cells)]
                    continue
                if columns is None or not row_words:
                    continue
                # A normal row (one date) is kept whole, so a vertically centred date
                # still gets all its narration lines. A merged row is split at each
                # date line; wrapped narration lines join the date line above them.
                groups: list[list[dict]] = []
                for line in _lines(row_words):
                    if DATE_RE.match(_column_texts(line, columns).get("date", "")) or not groups:
                        groups.append(list(line))
                    else:
                        groups[-1].extend(line)
                if sum(bool(DATE_RE.match(_column_texts(g, columns).get("date", ""))) for g in groups) <= 1:
                    groups = [row_words]
                elif not DATE_RE.match(_column_texts(groups[0], columns).get("date", "")):
                    groups[1][:0] = groups.pop(0)  # lines above the first date belong to it
                for group in groups:
                    record = {key: text for key, text in _column_texts(group, columns).items() if key}
                    if DATE_RE.match(record.get("date", "")):
                        rows.append(record)
                    elif rows and record.get("description") and not record.get("date"):
                        rows[-1]["description"] += " " + record["description"]
    return rows


def _decimal(token: str) -> Decimal:
    negative = token.startswith("-") or (token.startswith("(") and token.endswith(")"))
    value = Decimal(token.strip("-() ").replace(",", ""))
    return -value if negative else value


def _rows_from_text(pdf) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    previous_balance: Decimal | None = None
    for page in pdf.pages:
        for line in (page.extract_text() or "").splitlines():
            amounts = list(AMOUNT_RE.finditer(line))
            if "opening balance" in line.lower() and amounts:
                previous_balance = _decimal(amounts[-1].group(1))
                continue
            date_match = DATE_RE.match(line)
            if not date_match or not amounts:
                continue
            rest = line[date_match.end():amounts[0].start()]
            description = DATE_RE.sub("", rest, count=1).strip(" -|")
            if not description:
                continue
            amount = _decimal(amounts[-2 if len(amounts) > 1 else -1].group(1))
            marker = (amounts[0].group(2) or "").lower()
            if amount < 0 or marker == "dr":
                kind = "debit"
            elif marker == "cr":
                kind = "credit"
            elif len(amounts) > 1 and previous_balance is not None:
                kind = "credit" if _decimal(amounts[-1].group(1)) > previous_balance else "debit"
            else:
                kind = "credit" if any(hint in description.lower() for hint in CREDIT_HINTS) else "debit"
            if len(amounts) > 1:
                previous_balance = _decimal(amounts[-1].group(1))
            row = {"date": date_match.group(1), "description": description, "amount": str(abs(amount)), "type": kind}
            if len(amounts) > 1:
                row["balance"] = str(_decimal(amounts[-1].group(1)))
            rows.append(row)
    return rows


def extract_rows(content: bytes) -> list[dict[str, str]]:
    try:
        pdf = pdfplumber.open(io.BytesIO(content))
    except Exception as exc:
        # pdfplumber wraps pdfminer's PDFPasswordIncorrect, whose message is empty.
        if "password" in " ".join(type(error).__name__ for error in (exc, *exc.args)).lower():
            raise PdfStatementError("This PDF is password-protected. Remove the password and upload again.") from exc
        raise PdfStatementError("The uploaded PDF could not be read.") from exc
    with pdf:
        if len(pdf.pages) > MAX_PAGES:
            raise PdfStatementError(f"The PDF has more than {MAX_PAGES} pages.")
        try:
            rows = _rows_from_tables(pdf) or _rows_from_text(pdf)
        except (InvalidOperation, ValueError) as exc:
            raise PdfStatementError("The PDF transactions could not be read.") from exc
        if not rows and not any((page.extract_text() or "").strip() for page in pdf.pages):
            raise PdfStatementError("This PDF has no selectable text (it may be scanned). OCR is not supported yet; export CSV from your bank instead.")
    if not rows:
        raise PdfStatementError("No transactions were found in this PDF. Export CSV from your bank for the most reliable results.")
    return rows


def header_text(content: bytes) -> str:
    """Text of the first page, for reading details such as the account number. Empty if unreadable."""
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return (pdf.pages[0].extract_text() or "") if pdf.pages else ""
    except Exception:
        return ""
