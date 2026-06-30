from __future__ import annotations

import pandas as pd


PLACEHOLDER_COLUMNS = [
    "Folkmangd",
    "Yta_km2",
    "Befolkningstathet",
    "Veterinarforetag_antal",
    "Smadjur_per_veterinarforetag",
    "Expansion_score",
]


def build_master_municipality_dataset(animals: pd.DataFrame) -> pd.DataFrame:
    master = animals.copy()
    for column in PLACEHOLDER_COLUMNS:
        if column not in master.columns:
            master[column] = pd.NA

    return master.sort_values(
        by="Totalt_registrerade_smadjur_2025",
        ascending=False,
        na_position="last",
    ).reset_index(drop=True)


def build_top_candidates(master: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    ranked = master.copy()
    ranked["Preliminar_rankning"] = (
        ranked["Totalt_registrerade_smadjur_2025"]
        .rank(method="first", ascending=False)
        .astype("Int64")
    )
    return ranked.sort_values("Preliminar_rankning").head(top_n).reset_index(drop=True)


def summary_metrics(master: pd.DataFrame, horses: pd.DataFrame | None = None) -> dict[str, int | float | None]:
    metrics: dict[str, int | float | None] = {
        "municipalities": int(len(master)),
        "total_dogs": _sum_numeric(master, "Registrerade_hundar_2025"),
        "total_cats": _sum_numeric(master, "Registrerade_katter_2025"),
        "total_small_animals": _sum_numeric(master, "Totalt_registrerade_smadjur_2025"),
        "counties_with_horse_data": None,
    }
    if horses is not None:
        metrics["counties_with_horse_data"] = int(horses["Län"].nunique())
    return metrics


def _sum_numeric(df: pd.DataFrame, column: str) -> float:
    if column not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[column], errors="coerce").fillna(0).sum())
