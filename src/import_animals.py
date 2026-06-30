from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

import pandas as pd

from .validation import normalize_text_columns, require_columns


DOG_COLUMNS = ["Län", "Kommun", "Registrerade_hundar_2025"]
CAT_COLUMNS = ["Län", "Kommun", "Registrerade_katter_2025"]
HORSE_COLUMNS = [
    "Län",
    "Hästar_2016",
    "Hästar_på_jordbruk_2016",
    "Hästar_på_ridskolor_2016",
    "Hästar_per_1000_invånare_2016",
]


def read_csv(source: str | Path | BinaryIO) -> pd.DataFrame:
    try:
        return pd.read_csv(source)
    except UnicodeDecodeError:
        if hasattr(source, "seek"):
            source.seek(0)
        return pd.read_csv(source, encoding="latin-1")


def load_dogs(source: str | Path | BinaryIO) -> pd.DataFrame:
    df = read_csv(source)
    require_columns(df, DOG_COLUMNS, "Hundfilen")
    return normalize_text_columns(df[DOG_COLUMNS], ["Län", "Kommun"])


def load_cats(source: str | Path | BinaryIO) -> pd.DataFrame:
    df = read_csv(source)
    require_columns(df, CAT_COLUMNS, "Kattfilen")
    return normalize_text_columns(df[CAT_COLUMNS], ["Län", "Kommun"])


def load_horses(source: str | Path | BinaryIO) -> pd.DataFrame:
    df = read_csv(source)
    require_columns(df, HORSE_COLUMNS, "Hästfilen")
    return normalize_text_columns(df[HORSE_COLUMNS], ["Län"])


def merge_dogs_and_cats(dogs: pd.DataFrame, cats: pd.DataFrame) -> pd.DataFrame:
    merged = dogs.merge(cats, on=["Län", "Kommun"], how="outer", indicator=True)
    for column in ["Registrerade_hundar_2025", "Registrerade_katter_2025"]:
        merged[column] = pd.to_numeric(merged[column], errors="coerce")

    merged["Totalt_registrerade_smadjur_2025"] = (
        merged["Registrerade_hundar_2025"].fillna(0)
        + merged["Registrerade_katter_2025"].fillna(0)
    )
    return merged
