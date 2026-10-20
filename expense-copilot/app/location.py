"""Offline location detection from transaction narrations.

Looks for (most specific wins): a village/town/city from data/places.csv, a state
name, a two-letter state code at the end of a POS narration, or a 6-digit PIN code
(mapped to its state by prefix). Nothing leaves the machine.
"""

import csv
import os
import re
from functools import lru_cache
from pathlib import Path

from app.models import Location

PLACES_FILE = Path(__file__).resolve().parent / "data" / "places.csv"
EXTRA_PLACES_ENV = "EXPENSE_COPILOT_PLACES"
LEVEL_RANK = {"state": 0, "city": 1, "town": 2, "village": 3}

STATES = {
    "Andhra Pradesh": ("ANDHRA PRADESH",), "Arunachal Pradesh": ("ARUNACHAL PRADESH",), "Assam": ("ASSAM",),
    "Bihar": ("BIHAR",), "Chhattisgarh": ("CHHATTISGARH", "CHATTISGARH"), "Goa": ("GOA",), "Gujarat": ("GUJARAT",),
    "Haryana": ("HARYANA",), "Himachal Pradesh": ("HIMACHAL PRADESH",), "Jharkhand": ("JHARKHAND",),
    "Karnataka": ("KARNATAKA",), "Kerala": ("KERALA",), "Madhya Pradesh": ("MADHYA PRADESH",),
    "Maharashtra": ("MAHARASHTRA",), "Manipur": ("MANIPUR",), "Meghalaya": ("MEGHALAYA",), "Mizoram": ("MIZORAM",),
    "Nagaland": ("NAGALAND",), "Odisha": ("ODISHA", "ORISSA"), "Punjab": ("PUNJAB",), "Rajasthan": ("RAJASTHAN",),
    "Sikkim": ("SIKKIM",), "Tamil Nadu": ("TAMIL NADU", "TAMILNADU"), "Telangana": ("TELANGANA",), "Tripura": ("TRIPURA",),
    "Uttar Pradesh": ("UTTAR PRADESH",), "Uttarakhand": ("UTTARAKHAND", "UTTARANCHAL"), "West Bengal": ("WEST BENGAL",),
    "Andaman and Nicobar Islands": ("ANDAMAN",), "Chandigarh": (), "Dadra and Nagar Haveli and Daman and Diu": ("DADRA", "DAMAN"),
    "Delhi": (), "Jammu and Kashmir": ("JAMMU AND KASHMIR", "JAMMU KASHMIR"), "Ladakh": ("LADAKH",),
    "Lakshadweep": ("LAKSHADWEEP",), "Puducherry": (),
}
# Only trusted as the final word of a narration ("POS DMART HOSUR TN"). Codes that are
# also common words or abbreviations (UP as in "top up", AS, AP, OR, IN, ...) are left out.
STATE_CODES = {
    "MH": "Maharashtra", "KA": "Karnataka", "TN": "Tamil Nadu", "KL": "Kerala", "TS": "Telangana", "TG": "Telangana",
    "WB": "West Bengal", "GJ": "Gujarat", "RJ": "Rajasthan", "HR": "Haryana", "PB": "Punjab", "MP": "Madhya Pradesh",
    "OD": "Odisha", "JH": "Jharkhand", "CG": "Chhattisgarh", "UK": "Uttarakhand", "HP": "Himachal Pradesh", "GA": "Goa",
    "BR": "Bihar", "JK": "Jammu and Kashmir",
}
# PIN prefix -> state. 3-digit entries override the 2-digit postal circle.
PIN_PREFIXES = {
    "11": "Delhi", "12": "Haryana", "13": "Haryana", "14": "Punjab", "15": "Punjab", "16": "Punjab", "160": "Chandigarh",
    "17": "Himachal Pradesh", "18": "Jammu and Kashmir", "19": "Jammu and Kashmir", "194": "Ladakh",
    **{str(p): "Uttar Pradesh" for p in range(20, 29)}, "246": "Uttarakhand", "248": "Uttarakhand", "249": "Uttarakhand", "263": "Uttarakhand",
    **{str(p): "Rajasthan" for p in range(30, 35)}, **{str(p): "Gujarat" for p in range(36, 40)},
    **{str(p): "Maharashtra" for p in range(40, 45)}, "403": "Goa",
    **{str(p): "Madhya Pradesh" for p in range(45, 49)}, "49": "Chhattisgarh",
    "50": "Telangana", "51": "Andhra Pradesh", "52": "Andhra Pradesh", "53": "Andhra Pradesh",
    **{str(p): "Karnataka" for p in range(56, 60)}, **{str(p): "Tamil Nadu" for p in range(60, 65)},
    "67": "Kerala", "68": "Kerala", "69": "Kerala",
    **{str(p): "West Bengal" for p in range(70, 75)}, "737": "Sikkim", "744": "Andaman and Nicobar Islands",
    "75": "Odisha", "76": "Odisha", "77": "Odisha", "78": "Assam",
    "790": "Arunachal Pradesh", "791": "Arunachal Pradesh", "792": "Arunachal Pradesh", "793": "Meghalaya", "794": "Meghalaya",
    "795": "Manipur", "796": "Mizoram", "797": "Nagaland", "798": "Nagaland", "799": "Tripura",
    **{str(p): "Bihar" for p in range(80, 86)},
    **{p: "Jharkhand" for p in ("814", "815", "816", "822", "825", "826", "827", "828", "829", "831", "832", "833", "834", "835")},
}
PIN_RE = re.compile(r"(?:\bPIN(?:CODE)?\s*[:\-]?\s*|[-,]\s?)([1-8]\d{5})\b")


def _normalise(text: str) -> str:
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", text.upper()).split())


@lru_cache(maxsize=1)
def _places() -> dict[str, Location]:
    index: dict[str, Location] = {}
    for state, aliases in STATES.items():
        for name in (state.upper(), *aliases):
            index[_normalise(name)] = Location(name=state, level="state", state=state)
    files = [PLACES_FILE] + ([Path(os.environ[EXTRA_PLACES_ENV])] if os.environ.get(EXTRA_PLACES_ENV) else [])
    for path in files:
        with open(path, newline="", encoding="utf-8") as handle:
            lines = (line for line in handle if line.strip() and not line.lstrip().startswith("#"))
            for row in csv.DictReader(lines):
                level = (row.get("level") or "city").strip().lower()
                if level not in LEVEL_RANK or not row.get("name") or not row.get("state"):
                    continue
                place = Location(name=row["name"].strip(), level=level, district=(row.get("district") or "").strip() or None, state=row["state"].strip())
                for name in [row["name"], *(row.get("aliases") or "").split("|")]:
                    if name.strip():
                        index[_normalise(name)] = place
    return index


def _is_bank_name(tokens: list[str], start: int, size: int) -> bool:
    """'PUNJAB NATIONAL BANK', 'KERALA GRAMIN BANK', 'BANK OF MAHARASHTRA' name a bank, not a place."""
    after = tokens[start + size:start + size + 2]
    return bool(after and after[0] in {"BANK", "NATIONAL", "GRAMIN", "GRAMEEN", "STATE", "COOPERATIVE", "CO"}) or tokens[max(0, start - 2):start] == ["BANK", "OF"]


def state_from_pin(pincode: str) -> str | None:
    return PIN_PREFIXES.get(pincode[:3]) or PIN_PREFIXES.get(pincode[:2])


def locate(description: str) -> Location | None:
    places = _places()
    tokens = _normalise(description).split()
    best: Location | None = None
    best_rank = (-1, 0)
    for size in range(min(4, len(tokens)), 0, -1):
        for start in range(len(tokens) - size + 1):
            phrase = " ".join(tokens[start:start + size])
            place = places.get(phrase)
            if place and place.level == "state" and _is_bank_name(tokens, start, size):
                continue
            if place and (rank := (LEVEL_RANK[place.level], len(phrase))) > best_rank:
                best, best_rank = place, rank
    if best is None and len(tokens) >= 3 and tokens[-1] in STATE_CODES:
        state = STATE_CODES[tokens[-1]]
        best = Location(name=state, level="state", state=state)

    pin_match = PIN_RE.search(description.upper())
    pincode = pin_match.group(1) if pin_match else None
    if pincode and (pin_state := state_from_pin(pincode)):
        if best is None:
            return Location(name=pin_state, level="state", state=pin_state, pincode=pincode)
        if best.state == pin_state:
            return best.model_copy(update={"pincode": pincode})
    return best
