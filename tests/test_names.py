import math

import pytest

from moscow_cafes.names import normalize_chain_name


@pytest.mark.parametrize(
    ("raw", "canonical"),
    [
        ("ШОКОЛАДНИЦА", "Шоколадница"),
        ("Кафе «Шоколадница»", "Шоколадница"),
        ("Старбакс", "Starbucks"),
        ("Vasilchuki Chaihona №1", "Чайхона №1"),
        ("McDonald's", "Макдоналдс"),
        ("IL Патио", "Il Patio"),
        ("Кофе Хаус", "Кофе Хауз"),
        ("BB&Burgers", "BB&Burgers"),
    ],
)
def test_spelling_variants_map_to_one_chain(raw, canonical):
    assert normalize_chain_name(raw) == canonical


def test_bbq_venues_are_not_bb_burgers():
    assert normalize_chain_name("BBQ Grill") == "BBQ Grill"


def test_other_names_and_missing_values_pass_through():
    assert normalize_chain_name("Брусника") == "Брусника"
    assert normalize_chain_name(None) is None
    assert math.isnan(normalize_chain_name(float("nan")))
