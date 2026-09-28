"""Normalisation of café and restaurant chain names.

The rules were collected by hand while cleaning the data.mos.ru catering register in
notebook 01 (formerly CleaningData.py). Each pattern catches the spelling variants of
one chain: upper case, Cyrillic or Latin, with or without the venue type in the name.
Matching is case-insensitive and the first matching rule wins.
"""

import re

CHAIN_RULES = (
    ("Шоколадница", "Шоколадница"),
    ("Хлеб насущный", "Хлеб насущный"),
    ("Starbucks|Старбак", "Starbucks"),
    ("Чайхона №1|Chaihona №1", "Чайхона №1"),
    ("Кофе Хау[сз]", "Кофе Хауз"),
    ("KFC|КФС", "KFC"),
    ("Прайм|PRIME", "Прайм стар"),
    ("Бургер Кинг|Burger King", "Burger King"),
    ("Domino|Домино", "Domino's Pizza"),
    ("Караваевы", "Кулинарная лавка братьев Караваевых"),
    ("Патио|PATIO", "Il Patio"),
    ("Му[- ]Му", "Му-Му"),
    ("Теремок", "Теремок"),
    ("Крошка картошка", "Крошка Картошка"),
    ("Макд|donald|донал", "Макдоналдс"),
    ("Азбука вкуса", "Азбука вкуса"),
    ("Дабл ?би", "Даблби"),
    ("Кафе Хинкальная", "Кафе «Хинкальная»"),
    ("Планета суши", "Планета суши"),
    ("Якитория", "Якитория"),
    ("чма Тарас|Бульба", "Корчма Тарас Бульба"),
    ("Кофемания", "Кофемания"),
    ("Goodman|Гудман", "Goodman"),
    ("Две палочки", "Две палочки"),
    # A bare "BB" used to swallow every "BBQ ..." venue, hence the word boundaries.
    (r"BBBurgers|В&В|\bBB\b|ББ и Бургерс", "BB&Burgers"),
    ("Папа Джонс", "Папа Джонс"),
    ("Бизон", 'Стейкхаус "Бизон"'),
    ("Frayda", "TGI Fridays"),
    ("Академия", 'Пиццерия "Академия"'),
    ("Бутчер", "Бутчер"),
    ("Сабвей", "Subway"),
)

_COMPILED_RULES = [(re.compile(pattern, re.IGNORECASE), canonical) for pattern, canonical in CHAIN_RULES]


def normalize_chain_name(name):
    """Return the canonical chain name for `name`, or `name` unchanged when no rule matches."""
    if not isinstance(name, str):
        return name
    for pattern, canonical in _COMPILED_RULES:
        if pattern.search(name):
            return canonical
    return name
