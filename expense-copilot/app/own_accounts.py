"""Recognise money moved between the user's own accounts.

The user's accounts are known from account numbers (typed in, or read from a
statement header such as "Account number XXXX XXXX 1234") and, optionally, the
name their bank prints on transfers to and from themselves.
"""

import re
from dataclasses import dataclass, field

# "Account number XXXX XXXX 1234", "A/C No: 50100012341234", "Acct # ****1234"
ACCOUNT_NUMBER_RE = re.compile(r"(?:account|a/c|acct)\s*(?:number|no\.?|num|#)?\s*[:\-]?\s*([x*\d][x*\d \-]{3,}\d)", re.IGNORECASE)
FULL_NUMBER_DIGITS = 9  # a number at least this long is matched in full, not just by its last 4 digits


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text or "")


def find_account_number(text: str) -> str | None:
    """The account number (digits only, possibly just the unmasked tail) from statement header text."""
    for match in ACCOUNT_NUMBER_RE.finditer(text or ""):
        digits = _digits(match.group(1))
        if len(digits) >= 4:
            return digits
    return None


def _normalise(text: str) -> str:
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", text.upper()).split())


@dataclass
class OwnAccounts:
    """numbers maps account digits -> the account label they belong to (None if no statement was uploaded)."""
    numbers: dict[str, str | None] = field(default_factory=dict)
    names: list[str] = field(default_factory=list)

    @classmethod
    def build(cls, numbers: dict[str, str | None], names: list[str] | str | None) -> "OwnAccounts":
        if isinstance(names, str):
            names = names.split(",")
        cleaned = [_normalise(name) for name in names or []]
        return cls({d: label for number, label in numbers.items() if len(d := _digits(number)) >= 4}, [n for n in cleaned if len(n) >= 3])

    def _patterns(self, digits: str) -> re.Pattern:
        tail = re.escape(digits[-4:])
        # Masked ("XXXXXX1234", "**1234") or labelled ("A/C 1234", "ACCOUNT NO 501001234") references.
        forms = [rf"[X*]{{2,}}[X*\d]*?{tail}", rf"(?:A/?C|ACCOUNT|ACCT)\s*(?:NO\.?)?\s*[:\-]?\s*[X*\d]*?{tail}"]
        if len(digits) >= FULL_NUMBER_DIGITS:
            forms.append(re.escape(digits))
        return re.compile(r"(?<![A-Z0-9])(?:" + "|".join(forms) + r")(?!\d)")

    def mentioned_account(self, description: str, own_account: str | None) -> str | None:
        """Last 4 digits of one of the user's *other* accounts mentioned in the narration, if any."""
        text = (description or "").upper()
        for digits, label in self.numbers.items():
            if label is not None and label == own_account:
                continue  # a statement mentioning its own account number is not a transfer
            if self._patterns(digits).search(text):
                return digits[-4:]
        return None

    def mentions_name(self, description: str) -> bool:
        text = f" {_normalise(description or '')} "
        return any(f" {name} " in text for name in self.names)

    def masked(self, label: str) -> str | None:
        return next(("••" + digits[-4:] for digits, owner in self.numbers.items() if owner == label), None)
