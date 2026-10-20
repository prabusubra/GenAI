"""In-memory parsing and deterministic expense analysis."""

import csv
import io
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.location import locate
from app.own_accounts import OwnAccounts, find_account_number
from app.models import AccountSummary, CategorySpend, ExpenseReport, LocationSpend, Transaction
from app.pdf_statement import PdfStatementError, extract_rows, header_text

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%y", "%d-%m-%y", "%d %b %Y", "%d-%b-%Y", "%d %b %y", "%d-%b-%y")
# Order matters: the first category with a matching keyword wins. Keywords match at
# the start of a word, so "ola" matches "OLA CABS" but not "COCA-COLA".
CATEGORY_KEYWORDS = {
    "Rent": ("rent", "house rent", "landlord"),
    "Groceries": ("grocery", "groceries", "supermarket", "mart", "bigbasket", "dmart", "kirana", "blinkit", "zepto", "fresh"),
    "Dining": ("restaurant", "cafe", "coffee", "swiggy", "zomato", "food"),
    "Transport": ("uber", "ola", "rapido", "metro", "fuel", "petrol", "diesel", "parking", "toll", "fastag"),
    "Travel": ("irctc", "makemytrip", "goibibo", "redbus", "airline", "indigo", "air india", "hotel", "homestay", "oyo"),
    "Entertainment": ("netflix", "spotify", "cinema", "hotstar", "prime video", "pvr", "inox", "bookmyshow"),
    "Shopping": ("amazon", "flipkart", "myntra", "ajio", "nykaa", "retail"),
    "Bills & Utilities": ("electric", "water", "internet", "broadband", "fibernet", "mobile", "recharge", "insurance", "gas", "dth"),
    "Health": ("pharmacy", "hospital", "clinic", "medical", "diagnostic", "apollo"),
    "Fitness": ("gym", "fitness", "cult", "yoga"),
    "Education": ("school", "college", "tuition", "course", "udemy", "coursera"),
    "Farming": ("farm", "fertiliser", "fertilizer", "seeds", "tractor", "agri"),
    "Cash withdrawal": ("atm", "cash withdrawal", "cash wdl"),
    "Transfers": ("transfer", "upi", "neft", "imps", "rtgs"),
}
INCOME_KEYWORDS = {
    "Salary": ("salary", "payroll", "sal cr"),
    "Interest": ("interest", "int cr", "int pd"),
    "Refunds & cashback": ("refund", "cashback", "reversal"),
    "Freelance & business": ("freelance", "invoice", "consulting", "payment received"),
    "Transfers in": ("transfer", "upi", "neft", "imps", "rtgs"),
}
INTERNAL_TRANSFER = "Own account transfer"
# Only plain transfers can be own-account moves - never salary, interest, refunds or merchant payments,
# even when their narration mentions the user's name or account number.
TRANSFER_CATEGORIES = {"Transfers", "Transfers in", "Other", "Other income"}
SELF_HINT_RE = re.compile(r"(?<![a-z0-9])(self|own a/?c|own account)", re.IGNORECASE)
TRANSFER_HINT_RE = re.compile(r"(?<![a-z0-9])(self|own a/?c|own account|transfer|trf|upi|neft|imps|rtgs|ift)", re.IGNORECASE)
INTERNAL_TRANSFER_DAYS = 3
MAX_FILES = 20


class StatementParseError(ValueError):
    pass


def _date(value: object):
    for pattern in DATE_FORMATS:
        try:
            return datetime.strptime(str(value).strip(), pattern).date()
        except ValueError:
            continue
    raise StatementParseError(f"Unsupported transaction date: {value!r}.")


def _amount(value: object) -> Decimal:
    if value is None or str(value).strip() in ("", "-"):
        return Decimal("0")
    cleaned = str(value).strip().replace(",", "").replace("₹", "").replace("$", "")
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    try:
        result = Decimal(cleaned.strip("() "))
    except InvalidOperation as exc:
        raise StatementParseError(f"Invalid amount: {value!r}.") from exc
    return -result if negative else result


def _field(row: dict[str, object], *names: str) -> object | None:
    normalized = {str(key).strip().lower().replace(" ", "_"): value for key, value in row.items()}
    return next((normalized[name] for name in names if normalized.get(name) not in (None, "")), None)


def _row_to_transaction(row: dict[str, object]) -> Transaction:
    value_date = _field(row, "date", "transaction_date", "txn_date", "value_date")
    description = _field(row, "description", "narration", "particulars", "details", "transaction_details", "remarks", "merchant")
    if value_date is None or description is None:
        raise StatementParseError("Each transaction needs a date and description/narration column.")
    debit = _amount(_field(row, "debit", "debits", "withdrawal", "withdrawals", "withdrawal_amt", "withdrawal_amount", "debit_amount"))
    credit = _amount(_field(row, "credit", "credits", "deposit", "deposits", "deposit_amt", "deposit_amount", "credit_amount"))
    if debit or credit:
        amount = credit - debit
    else:
        amount = _amount(_field(row, "amount", "transaction_amount", "value"))
        kind = str(_field(row, "type", "transaction_type", "dr_cr", "direction") or "").lower()
        if kind in {"debit", "dr", "withdrawal", "expense"}:
            amount = -abs(amount)
        elif kind in {"credit", "cr", "deposit", "income"}:
            amount = abs(amount)
    if not amount:
        raise StatementParseError("Each transaction needs a non-zero amount, debit, or credit.")
    return Transaction(date=_date(value_date), description=str(description), amount=amount, currency=str(_field(row, "currency") or "INR").upper(),
                       balance=_balance(_field(row, "balance", "closing_balance", "running_balance", "available_balance")))


def _balance(value: object) -> Decimal | None:
    """A running balance such as "1,234.50", "1,234.50 Cr" or "(500.00) Dr"; None when missing or unreadable."""
    if value is None or str(value).strip() in ("", "-"):
        return None
    text = str(value).strip()
    overdrawn = bool(re.search(r"\bdr\.?$", text, re.IGNORECASE))
    text = re.sub(r"\s*(cr|dr)\.?$", "", text, flags=re.IGNORECASE)
    try:
        result = _amount(text)
    except StatementParseError:
        return None
    return -abs(result) if overdrawn else result


def parse_statement(filename: str, content: bytes) -> list[Transaction]:
    if not content:
        raise StatementParseError("The uploaded file is empty.")
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise StatementParseError("The file exceeds the 10 MB upload limit.")
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    try:
        if extension == "csv":
            rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
        elif extension == "json":
            data = json.loads(content)
            rows = data.get("transactions") if isinstance(data, dict) else data
        elif extension == "pdf":
            rows = extract_rows(content)
        else:
            raise StatementParseError("Upload a CSV, JSON, or PDF statement.")
    except PdfStatementError as exc:
        raise StatementParseError(str(exc)) from exc
    except (UnicodeDecodeError, csv.Error, json.JSONDecodeError) as exc:
        raise StatementParseError("The uploaded statement could not be read.") from exc
    if not isinstance(rows, list) or not rows:
        raise StatementParseError("The statement has no transaction rows.")
    if not all(isinstance(row, dict) for row in rows):
        raise StatementParseError("Every transaction must be an object/row.")
    transactions = []
    for number, row in enumerate(rows, start=1):
        try:
            transactions.append(_row_to_transaction(row))
        except StatementParseError as exc:
            date = _field(row, "date", "transaction_date", "txn_date", "value_date")
            raise StatementParseError(f"Row {number}{f' ({date})' if date else ''}: {exc}") from exc
    return transactions


def _keyword_pattern(keywords: tuple[str, ...]) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(keyword) for keyword in keywords) + ")", re.IGNORECASE)


EXPENSE_PATTERNS = {category: _keyword_pattern(keywords) for category, keywords in CATEGORY_KEYWORDS.items()}
INCOME_PATTERNS = {category: _keyword_pattern(keywords) for category, keywords in INCOME_KEYWORDS.items()}


def _category(description: str, amount: Decimal) -> str:
    patterns = INCOME_PATTERNS if amount > 0 else EXPENSE_PATTERNS
    return next((category for category, pattern in patterns.items() if pattern.search(description)), "Other income" if amount > 0 else "Other")


def _own_transfer_reason(t: Transaction, own: OwnAccounts) -> str | None:
    """Why this transaction is a move to/from one of the user's own accounts, or None."""
    if t.category not in TRANSFER_CATEGORIES:
        return None
    if digits := own.mentioned_account(t.description, t.account):
        return f"{'To' if t.amount < 0 else 'From'} your account ••{digits}"
    if TRANSFER_HINT_RE.search(t.description):
        if SELF_HINT_RE.search(t.description):
            return "Marked as a self transfer"
        if own.mentions_name(t.description):
            return f"{'To' if t.amount < 0 else 'From'} your own name"
    return None


def _link_internal_transfers(transactions: list[Transaction], own: OwnAccounts) -> tuple[list[Transaction], Decimal, int]:
    """Mark money moved between the user's own accounts so it is not income or spending.

    1. A transfer-like debit in one uploaded account is paired with the same amount credited to
       another uploaded account within a few days, when either side is recognisably the user's own
       (self transfer, one of their account numbers, or their own name).
    2. Any other transfer that is recognisably to/from the user's own account is excluded on its own,
       e.g. a transfer to an account whose statement was not uploaded.
    Returns the transactions, the total amount moved and the number of moves (a pair counts once).
    """
    result = list(transactions)
    skip = lambda t: t.user_excluded or t.user_included  # noqa: E731 - the user decided this one
    reasons = {i: None if skip(t) else _own_transfer_reason(t, own) for i, t in enumerate(result)}
    used: set[int] = set()
    total, count = Decimal("0"), 0
    debits = sorted((i for i, t in enumerate(result) if t.amount < 0 and not skip(t) and TRANSFER_HINT_RE.search(t.description)), key=lambda i: result[i].date)
    for d in debits:
        debit = result[d]
        candidates = [i for i, t in enumerate(result) if i not in used and i != d and not skip(t) and t.amount == -debit.amount and t.account != debit.account
                      and abs((t.date - debit.date).days) <= INTERNAL_TRANSFER_DAYS and TRANSFER_HINT_RE.search(t.description)
                      and (reasons[d] or reasons[i])]
        if not candidates or d in used:
            continue
        c = min(candidates, key=lambda i: abs((result[i].date - debit.date).days))
        used.update((c, d))
        credit = result[c]
        result[d] = debit.model_copy(update={"internal_transfer": True, "category": INTERNAL_TRANSFER,
                                              "transfer_note": f"Moved to {credit.account} (arrived {credit.date:%d %b})"})
        result[c] = credit.model_copy(update={"internal_transfer": True, "category": INTERNAL_TRANSFER,
                                               "transfer_note": f"Moved from {debit.account} (sent {debit.date:%d %b})"})
        total += -debit.amount
        count += 1
    for i, reason in reasons.items():
        if reason and i not in used:
            result[i] = result[i].model_copy(update={"internal_transfer": True, "category": INTERNAL_TRANSFER, "transfer_note": reason})
            total += abs(result[i].amount)
            count += 1
    return result, total, count


def _shares(totals: dict, counts: dict, whole: Decimal) -> list[CategorySpend]:
    return sorted((CategorySpend(category=name, amount=value, percentage=round(value / whole * 100, 2) if whole else Decimal("0"), count=counts[name])
                   for name, value in totals.items()), key=lambda item: item.amount, reverse=True)


def _money(value: Decimal) -> str:
    return f"₹{value:,.2f}"


def analyze(transactions: list[Transaction], warnings: list[str] | None = None, own: OwnAccounts | None = None,
            openings: dict[str, Decimal] | None = None) -> ExpenseReport:
    """openings maps account label -> opening balance (money carried over from last month)."""
    own = own or OwnAccounts()
    openings = openings or {}
    prepared = [t.model_copy(update={"category": t.category or _category(t.description, t.amount), "location": t.location or locate(t.description)}) for t in transactions]
    prepared, internal_total, internal_count = _link_internal_transfers(prepared, own)
    prepared = sorted(prepared, key=lambda t: t.date)  # stable: same-day rows keep file order
    counted = [t for t in prepared if not t.internal_transfer and not t.user_excluded]
    left_out = [t for t in prepared if t.user_excluded]
    left_in = sum((t.amount for t in left_out if t.amount > 0), Decimal("0"))
    left_spent = sum((-t.amount for t in left_out if t.amount < 0), Decimal("0"))
    expenses = [t for t in counted if t.amount < 0]
    income = [t for t in counted if t.amount > 0]
    spending = sum((-t.amount for t in expenses), Decimal("0"))
    earned = sum((t.amount for t in income), Decimal("0"))

    def group(items: list[Transaction], key) -> tuple[dict, dict]:
        totals: dict = defaultdict(Decimal)
        counts: dict = defaultdict(int)
        for t in items:
            totals[key(t)] += abs(t.amount)
            counts[key(t)] += 1
        return totals, counts

    categories = _shares(*group(expenses, lambda t: t.category or "Other"), spending)
    income_sources = _shares(*group(income, lambda t: t.category or "Other income"), earned)

    accounts = []
    for name in dict.fromkeys(t.account or "Statement" for t in prepared):
        rows = [t for t in prepared if (t.account or "Statement") == name]
        own_counted = [t for t in rows if not t.internal_transfer and not t.user_excluded]
        out = sum((-t.amount for t in own_counted if t.amount < 0), Decimal("0"))
        into = sum((t.amount for t in own_counted if t.amount > 0), Decimal("0"))
        top, _ = group([t for t in own_counted if t.amount < 0], lambda t: t.category or "Other")
        opening = openings.get(name)
        closing = opening + sum((t.amount for t in rows), Decimal("0")) if opening is not None else None
        accounts.append(AccountSummary(account=name, account_number=own.masked(name), opening_balance=opening, closing_balance=closing, statement_start=min(t.date for t in rows), statement_end=max(t.date for t in rows), transaction_count=len(rows),
                                       total_income=into, total_spending=out, net_cash_flow=into - out, top_category=max(top, key=top.get) if top else None))

    located = [t for t in expenses if t.location]
    by_state, state_counts = group(located, lambda t: t.location.state)
    state_spend = sorted((LocationSpend(name=state, level="state", state=state, amount=value, percentage=round(value / spending * 100, 2), count=state_counts[state])
                          for state, value in by_state.items()), key=lambda item: item.amount, reverse=True)
    places = [t for t in located if t.location.level != "state"]
    by_place, place_counts = group(places, lambda t: (t.location.name, t.location.level, t.location.district, t.location.state))
    place_spend = sorted((LocationSpend(name=name, level=level, district=district, state=state, amount=value, percentage=round(value / spending * 100, 2), count=place_counts[(name, level, district, state)])
                          for (name, level, district, state), value in by_place.items()), key=lambda item: item.amount, reverse=True)
    unlocated = spending - sum(by_state.values(), Decimal("0"))

    insights = [f"{categories[0].category} is your largest spending category ({categories[0].percentage}% of spending)."] if categories else ["No debit transactions were detected."]
    if earned and spending > earned:
        insights.append(f"Spending is higher than income by {_money(spending - earned)} across these statements.")
    known = [a.opening_balance for a in accounts if a.opening_balance is not None]
    opening_total = sum(known, Decimal("0")) if known else None
    available = opening_total + earned if opening_total is not None else None
    left_at_end = available - spending if available is not None else None
    without_opening = [a.account for a in accounts if a.opening_balance is None]
    if opening_total is not None:
        if left_at_end >= 0:
            insights.append(f"You started with {_money(opening_total)} carried over; with {_money(earned)} income and {_money(spending)} spending, {_money(left_at_end)} is left.")
        else:
            insights.append(f"Spending used up the {_money(opening_total)} carried over and all income; you are short by {_money(-left_at_end)}.")
        if earned < spending <= available:
            insights.append(f"This period's income didn't cover spending; {_money(spending - earned)} came out of the money carried over.")
    if left_out:
        parts = [f"{_money(left_in)} in" if left_in else "", f"{_money(left_spent)} out" if left_spent else ""]
        insights.append(f"You left out {len(left_out)} transaction{'s' if len(left_out) != 1 else ''} ({' and '.join(p for p in parts if p)}); they are not in any total.")
    if internal_count:
        insights.append(f"{_money(internal_total)} moved between your own accounts in {internal_count} transfer{'s' if internal_count != 1 else ''}; it is excluded from income and spending.")
    for account in accounts if len(accounts) > 1 else []:
        if account.net_cash_flow < 0:
            insights.append(f"{account.account} ran a deficit of {_money(-account.net_cash_flow)}.")
    if place_spend:
        top_place = place_spend[0]
        insights.append(f"Most location-tagged spending was in {top_place.name}, {top_place.state} ({_money(top_place.amount)}).")
    if spending and unlocated / spending > Decimal("0.5"):
        insights.append(f"{round(unlocated / spending * 100)}% of spending has no place in its description (online payments usually don't).")

    return ExpenseReport(
        statement_start=min((t.date for t in prepared), default=None), statement_end=max((t.date for t in prepared), default=None),
        transaction_count=len(prepared), total_income=earned, total_spending=spending, net_cash_flow=earned - spending,
        category_spend=categories, income_sources=income_sources, accounts=accounts,
        internal_transfer_total=internal_total, internal_transfer_count=internal_count,
        excluded_count=len(left_out), excluded_income=left_in, excluded_spending=left_spent,
        opening_balance=opening_total, money_available=available, left_at_end=left_at_end, accounts_without_opening=without_opening if known else [],
        state_spend=state_spend, place_spend=place_spend, unlocated_spending=unlocated,
        largest_expenses=sorted(expenses, key=lambda t: t.amount)[:5], insights=insights, warnings=warnings or [], transactions=prepared,
    )


OPENING_TEXT_RE = re.compile(r"opening\s+balance[^0-9\-]{0,80}?(-?[\d,]+\.\d{2})", re.IGNORECASE | re.DOTALL)


def _opening_balance(transactions: list[Transaction], header: str = "") -> Decimal | None:
    """Money in the account before its first transaction.

    From the running balance: the first row's balance minus its amount. Statements listed newest-first
    are detected by checking which order makes every balance follow from the previous one. Falls back
    to an "Opening Balance" line in the statement text.
    """
    rows = [t for t in transactions if t.balance is not None]
    if rows:
        def consistent(seq: list[Transaction]) -> bool:
            return all(seq[i].balance == seq[i - 1].balance + seq[i].amount for i in range(1, len(seq)))
        if consistent(rows):
            first = rows[0]
        elif consistent(rows[::-1]):
            first = rows[-1]
        else:  # a row is missing or out of order; trust the date order
            first = rows[0] if rows[0].date <= rows[-1].date else rows[-1]
        return first.balance - first.amount
    match = OPENING_TEXT_RE.search(header or "")
    return Decimal(match.group(1).replace(",", "")) if match else None


def _statement_account_number(filename: str, content: bytes) -> str | None:
    """Account number printed on the statement itself (PDF header, or "account_number" in JSON)."""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension == "pdf":
        return find_account_number(header_text(content))
    if extension == "json":
        try:
            data = json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        value = data.get("account_number") if isinstance(data, dict) else None
        return find_account_number(f"account {value}") if value else None
    return None


def _with_ids(transactions: list[Transaction], label: str) -> list[Transaction]:
    """Give each transaction an id that stays the same when the same statements are analyzed again."""
    seen: dict[tuple, int] = defaultdict(int)
    result = []
    for t in transactions:
        key = (label, t.date, t.amount, t.description)
        seen[key] += 1  # identical rows (two equal coffees on one day) still get distinct ids
        raw = "|".join(map(str, (*key, seen[key])))
        result.append(t.model_copy(update={"account": label, "id": hashlib.sha1(raw.encode()).hexdigest()[:12]}))
    return result


def analyze_statements(files: list[tuple], owner_names: list[str] | str | None = None, other_account_numbers: list[str] | None = None,
                       excluded_ids: set[str] | None = None, included_ids: set[str] | None = None) -> ExpenseReport:
    """Analyze several statements together.

    Each item is (account label, filename, content[, account number[, opening balance]]). The opening balance
    (money carried over from last month) is worked out from the statement when not given.
    The account number may be just its last 4 digits; when missing it is read from the statement if printed
    there. owner_names are how the bank prints the user's own name on transfers; other_account_numbers are
    the user's accounts whose statements were not uploaded. Both help recognise own-account transfers.
    excluded_ids are transaction ids the user chose to leave out of every total; included_ids are ids the user
    chose to count even though they look like own-account transfers. Leaving out wins if an id is in both.
    """
    if not files:
        raise StatementParseError("Upload at least one statement.")
    if len(files) > MAX_FILES:
        raise StatementParseError(f"Upload at most {MAX_FILES} statements at a time.")
    transactions: list[Transaction] = []
    warnings: list[str] = []
    seen: dict[str, str] = {}
    keys_by_account: dict[str, set] = defaultdict(set)  # same label = same account, e.g. two months of one account
    numbers: dict[str, str | None] = {number: None for number in other_account_numbers or [] if number}
    openings: dict[str, tuple] = {}  # label -> (first date, opening balance) of that account's earliest statement
    for label, filename, content, *rest in files:
        if number := (rest[0] if rest and rest[0] else None) or _statement_account_number(filename, content):
            numbers[number] = label
        digest = hashlib.sha256(content).hexdigest()
        if digest in seen:
            warnings.append(f"{filename} is identical to {seen[digest]} and was skipped.")
            continue
        seen[digest] = filename
        try:
            parsed = parse_statement(filename, content)
        except StatementParseError as exc:
            warnings.append(f"{filename} was skipped: {exc}")
            continue
        typed = rest[1] if len(rest) > 1 and rest[1] not in (None, "") else None
        try:
            opening = _amount(typed) if typed is not None else _opening_balance(parsed, header_text(content) if filename.lower().endswith(".pdf") else "")
        except StatementParseError:
            warnings.append(f"The opening balance typed for {filename} ({typed!r}) is not a number and was ignored.")
            opening = _opening_balance(parsed)
        first_date = min(t.date for t in parsed)
        if opening is not None and (label not in openings or first_date < openings[label][0]):
            openings[label] = (first_date, opening)
        earlier = keys_by_account[label]
        keys = [(t.date, t.amount, t.description) for t in parsed]
        fresh = [t for t, key in zip(parsed, keys) if key not in earlier]
        if len(fresh) < len(parsed):
            warnings.append(f"{len(parsed) - len(fresh)} transaction(s) in {filename} were already in another {label} statement and were counted once.")
        earlier.update(keys)
        transactions.extend(t.model_copy(update={"account": label}) for t in fresh)
    if not transactions:
        raise StatementParseError(" ".join(warnings) or "No transactions were found.")
    by_label: dict[str, list[Transaction]] = defaultdict(list)
    for t in transactions:
        by_label[t.account].append(t)
    excluded_ids, included_ids = excluded_ids or set(), (included_ids or set()) - (excluded_ids or set())
    transactions = [t.model_copy(update={"user_excluded": t.id in excluded_ids, "user_included": t.id in included_ids})
                    for label, rows in by_label.items() for t in _with_ids(rows, label)]
    return analyze(transactions, warnings, OwnAccounts.build(numbers, owner_names), {label: value for label, (_, value) in openings.items()})
