from __future__ import annotations

import re
from typing import Any

import pandas as pd


MUNICIPALITY_ALIASES = {
    "upplands-väsby": "Upplands Väsby",
    "upplands väsby": "Upplands Väsby",
}

MUNICIPALITY_CORRECTIONS = {
    "g otland": "Gotland",
    "v arberg": "Varberg",
    "v ärnamo": "Värnamo",
    "ö rebro": "Örebro",
    "ö steråker": "Österåker",
    "å sele": "Åsele",
    "s öderhamn": "Söderhamn",
}


def normalize_county_name(value: Any) -> str | pd.NA:
    if value is None or pd.isna(value):
        return pd.NA
    return _collapse_spaces(str(value))


def normalize_municipality_name(value: Any) -> str | pd.NA:
    if value is None or pd.isna(value):
        return pd.NA

    name = _collapse_spaces(str(value))
    name = re.sub(r"\s+kommun$", "", name, flags=re.IGNORECASE)

    lookup_key = name.casefold()
    if lookup_key in MUNICIPALITY_ALIASES:
        return MUNICIPALITY_ALIASES[lookup_key]
    if lookup_key in MUNICIPALITY_CORRECTIONS:
        return MUNICIPALITY_CORRECTIONS[lookup_key]

    name = _fix_single_letter_split(name)
    lookup_key = name.casefold()
    return MUNICIPALITY_ALIASES.get(lookup_key, MUNICIPALITY_CORRECTIONS.get(lookup_key, name))


def municipality_match_key(value: Any) -> str:
    normalized = normalize_municipality_name(value)
    if pd.isna(normalized):
        return ""
    return str(normalized).casefold()


def _collapse_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _fix_single_letter_split(value: str) -> str:
    if not re.match(r"^[A-Za-zÅÄÖåäö]\s+\S{2,}", value):
        return value

    first, rest = value.split(" ", 1)
    candidate = first + rest
    if candidate.casefold() in {corrected.casefold() for corrected in MUNICIPALITY_CORRECTIONS.values()}:
        return candidate

    # PDF extraction often inserts one false space after the first letter.
    # Preserve legitimate multi-word names by only applying this to a known
    # Swedish first-word pattern or a single remaining word.
    if " " not in rest or rest.casefold().split(" ", 1)[0] in {
        "rebro",
        "steråker",
        "sele",
        "öderhamn",
        "otland",
        "arberg",
        "ärnamo",
    }:
        return candidate
    return value
