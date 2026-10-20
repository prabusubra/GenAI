from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class Location(BaseModel):
    name: str
    level: Literal["state", "city", "town", "village"]
    district: str | None = None
    state: str
    pincode: str | None = None


class Transaction(BaseModel):
    id: str | None = None  # stable across re-analysis of the same files, used to leave a transaction out
    date: date
    description: str = Field(min_length=1, max_length=500)
    amount: Decimal
    currency: str = Field(default="INR", min_length=3, max_length=3)
    balance: Decimal | None = None  # running balance after this transaction, when the statement prints it
    category: str | None = None
    account: str | None = None
    location: Location | None = None
    internal_transfer: bool = False
    transfer_note: str | None = None  # why it counts as a move between the user's own accounts
    user_excluded: bool = False  # the user chose to leave it out of the analysis
    user_included: bool = False  # the user chose to count it, overriding own-account-transfer detection


class CategorySpend(BaseModel):
    category: str
    amount: Decimal
    percentage: Decimal
    count: int = 0


class AccountSummary(BaseModel):
    account: str
    account_number: str | None = None  # masked, e.g. "••1234"
    statement_start: date | None
    statement_end: date | None
    transaction_count: int
    total_income: Decimal
    total_spending: Decimal
    net_cash_flow: Decimal
    top_category: str | None = None
    opening_balance: Decimal | None = None  # money carried over from before the first statement
    closing_balance: Decimal | None = None  # opening balance + every transaction (what the bank shows at the end)


class LocationSpend(BaseModel):
    name: str
    level: Literal["state", "city", "town", "village"]
    district: str | None = None
    state: str
    amount: Decimal
    percentage: Decimal
    count: int


class ExpenseReport(BaseModel):
    statement_start: date | None
    statement_end: date | None
    transaction_count: int
    total_income: Decimal
    total_spending: Decimal
    net_cash_flow: Decimal
    category_spend: list[CategorySpend]
    income_sources: list[CategorySpend] = []
    accounts: list[AccountSummary] = []
    internal_transfer_total: Decimal = Decimal("0")
    internal_transfer_count: int = 0
    opening_balance: Decimal | None = None  # sum of the accounts' opening balances (None if none is known)
    money_available: Decimal | None = None  # opening balance + income
    left_at_end: Decimal | None = None  # money available - spending
    accounts_without_opening: list[str] = []
    excluded_count: int = 0
    excluded_income: Decimal = Decimal("0")
    excluded_spending: Decimal = Decimal("0")
    state_spend: list[LocationSpend] = []
    place_spend: list[LocationSpend] = []
    unlocated_spending: Decimal = Decimal("0")
    largest_expenses: list[Transaction]
    insights: list[str]
    warnings: list[str] = []
    transactions: list[Transaction]
