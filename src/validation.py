from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from .normalization import normalize_county_name, normalize_municipality_name


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    missing_columns: list[str]


def validate_columns(df: pd.DataFrame, required_columns: Iterable[str]) -> ValidationResult:
    required = list(required_columns)
    missing = [column for column in required if column not in df.columns]
    return ValidationResult(is_valid=not missing, missing_columns=missing)


def require_columns(df: pd.DataFrame, required_columns: Iterable[str], dataset_name: str) -> None:
    result = validate_columns(df, required_columns)
    if not result.is_valid:
        missing = ", ".join(result.missing_columns)
        raise ValueError(f"{dataset_name} saknar obligatoriska kolumner: {missing}")


def normalize_text_columns(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    normalized = df.copy()
    for column in columns:
        if column in normalized.columns:
            if column == "Kommun":
                normalized[column] = normalized[column].map(normalize_municipality_name).astype("string")
            elif column == "Län":
                normalized[column] = normalized[column].map(normalize_county_name).astype("string")
            else:
                normalized[column] = normalized[column].astype("string").str.strip()
    return normalized
