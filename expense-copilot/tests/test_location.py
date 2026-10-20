import pytest

from app.location import locate


@pytest.mark.parametrize(("description", "name", "level", "state"), [
    ("SWIGGY FOOD ORDER BENGALURU", "Bengaluru", "city", "Karnataka"),
    ("UBER TRIP BANGALORE KA", "Bengaluru", "city", "Karnataka"),  # alias
    ("POS 4411 DMART NAVI MUMBAI", "Navi Mumbai", "city", "Maharashtra"),  # longest phrase wins over "Mumbai"
    ("FARM SUPPLY STORE HIWARE BAZAR", "Hiware Bazar", "village", "Maharashtra"),
    ("TEMPLE STORE MELUKOTE MANDYA", "Melukote", "town", "Karnataka"),  # town beats city
    ("POS 8812 FUEL STATION KRISHNAGIRI TN", "Tamil Nadu", "state", "Tamil Nadu"),  # trailing state code
    ("HOMESTAY EAST KHASI HILLS MEGHALAYA", "Meghalaya", "state", "Meghalaya"),
])
def test_locate(description: str, name: str, level: str, state: str) -> None:
    location = locate(description)
    assert location is not None
    assert (location.name, location.level, location.state) == (name, level, state)


def test_pin_code_gives_state() -> None:
    location = locate("GRAMEEN KIRANA STORE PIN 571401")
    assert location is not None
    assert (location.state, location.pincode, location.level) == ("Karnataka", "571401", "state")


@pytest.mark.parametrize("description", [
    "METRO CARD TOP UP",  # "UP" is not trusted as a state code
    "UPI TO RAVI KUMAR",
    "COCA-COLA VENDING",
    "PUNJAB NATIONAL BANK NEFT",  # bank names are not places
    "IMPS FROM BANK OF MAHARASHTRA",
    "BIGBASKET ORDER 560001",  # a bare 6-digit number is an order id, not a PIN
])
def test_no_false_locations(description: str) -> None:
    assert locate(description) is None
