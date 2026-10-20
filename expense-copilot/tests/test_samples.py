from decimal import Decimal
from pathlib import Path

import pytest

from app.expense import analyze, parse_statement

SAMPLES = sorted((Path(__file__).resolve().parent.parent / "samples").glob("statement*"))


@pytest.mark.parametrize("path", SAMPLES, ids=lambda path: path.name)
def test_every_sample_format_gives_the_same_report(path: Path) -> None:
    report = analyze(parse_statement(path.name, path.read_bytes()))
    assert report.transaction_count == 28
    assert report.total_income == Decimal("86511.40")
    assert report.total_spending == Decimal("57313.17")  # the "UPI TO SELF ACCOUNT" transfer is excluded even when uploaded alone
