from __future__ import annotations

import pandas as pd


SCORE_WEIGHTS = {
    "Smadjur_score": 0.30,
    "Konkurrens_score": 0.25,
    "Folkmangd_score": 0.15,
    "Befolkningstathet_score": 0.15,
    "Djurtagande_score": 0.15,
}

PLACEHOLDER_COLUMNS = [
    "Folkmangd",
    "Yta_km2",
    "Befolkningstathet",
    "Befolkningsforandring_1_ar",
    "Befolkningsforandring_5_ar",
    "Alder_0_17",
    "Alder_18_64",
    "Alder_65_plus",
    "Medianinkomst",
    "Disponibel_inkomst",
    "Hushall_antal",
    "Veterinarforetag_antal",
    "Hundar_per_1000_inv",
    "Katter_per_1000_inv",
    "Smadjur_per_1000_inv",
    "Veterinarforetag_per_10000_smadjur",
    "Smadjur_per_veterinarforetag",
    "Smadjur_score",
    "Konkurrens_score",
    "Folkmangd_score",
    "Befolkningstathet_score",
    "Djurtagande_score",
    "Expansion_score",
]


def build_master_municipality_dataset(animals: pd.DataFrame) -> pd.DataFrame:
    master = animals.copy()
    for column in PLACEHOLDER_COLUMNS:
        if column not in master.columns:
            master[column] = pd.NA

    master = calculate_expansion_scores(master)
    return master.sort_values(
        by=["Expansion_score", "Totalt_registrerade_smadjur_2025"],
        ascending=False,
        na_position="last",
    ).reset_index(drop=True)


def build_top_candidates(master: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    ranked = master.copy()
    ranking_column = "Expansion_score" if ranked["Expansion_score"].notna().any() else "Totalt_registrerade_smadjur_2025"
    ranked = ranked.sort_values(
        by=[ranking_column, "Totalt_registrerade_smadjur_2025"],
        ascending=False,
        na_position="last",
    ).reset_index(drop=True)
    ranked["Preliminar_rankning"] = pd.Series(range(1, len(ranked) + 1), dtype="Int64")
    return ranked.head(top_n).reset_index(drop=True)


def calculate_expansion_scores(df: pd.DataFrame) -> pd.DataFrame:
    scored = df.copy()
    dogs = _numeric_series(scored, "Registrerade_hundar_2025")
    cats = _numeric_series(scored, "Registrerade_katter_2025")
    demand = _numeric_series(scored, "Totalt_registrerade_smadjur_2025")
    population = _numeric_series(scored, "Folkmangd")
    area = _numeric_series(scored, "Yta_km2")
    competition = _numeric_series(scored, "Veterinarforetag_antal")

    scored["Befolkningstathet"] = _numeric_series(scored, "Befolkningstathet").combine_first(
        population.div(area.where(area > 0))
    )
    scored["Hundar_per_1000_inv"] = dogs.div(population.where(population > 0)).mul(1000)
    scored["Katter_per_1000_inv"] = cats.div(population.where(population > 0)).mul(1000)
    scored["Smadjur_per_1000_inv"] = demand.div(population.where(population > 0)).mul(1000)
    scored["Veterinarforetag_per_10000_smadjur"] = competition.div(demand.where(demand > 0)).mul(10000)
    scored["Smadjur_per_veterinarforetag"] = demand.div(competition.where(competition > 0))

    scored["Smadjur_score"] = _normalize_score(demand, higher_is_better=True)
    scored["Konkurrens_score"] = _normalize_score(scored["Smadjur_per_veterinarforetag"], higher_is_better=True)
    scored["Folkmangd_score"] = _normalize_score(population, higher_is_better=True)
    scored["Befolkningstathet_score"] = _normalize_score(
        _numeric_series(scored, "Befolkningstathet"),
        higher_is_better=True,
    )
    scored["Djurtagande_score"] = _normalize_score(scored["Smadjur_per_1000_inv"], higher_is_better=True)

    # Preliminary decision-support indicator only. Missing fields are excluded
    # per row and the remaining component weights are normalized to 100%.
    weighted_sum = pd.Series(0.0, index=scored.index)
    available_weight = pd.Series(0.0, index=scored.index)
    for column, weight in SCORE_WEIGHTS.items():
        component = pd.to_numeric(scored[column], errors="coerce")
        has_value = component.notna()
        weighted_sum = weighted_sum.add(component.fillna(0) * weight)
        available_weight = available_weight.add(has_value.astype(float) * weight)

    scored["Expansion_score"] = weighted_sum.div(available_weight.where(available_weight > 0)).round(1)
    return scored


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


def _numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(pd.NA, index=df.index, dtype="Float64")
    return pd.to_numeric(df[column], errors="coerce")


def _normalize_score(series: pd.Series, higher_is_better: bool) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    valid = values.dropna()
    if valid.empty:
        return pd.Series(pd.NA, index=series.index, dtype="Float64")

    minimum = valid.min()
    maximum = valid.max()
    if minimum == maximum:
        return values.where(values.isna(), 100.0).astype("Float64")

    if higher_is_better:
        normalized = (values - minimum) / (maximum - minimum) * 100
    else:
        normalized = (maximum - values) / (maximum - minimum) * 100
    return normalized.clip(lower=0, upper=100).round(1).astype("Float64")


def _sum_numeric(df: pd.DataFrame, column: str) -> float:
    if column not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[column], errors="coerce").fillna(0).sum())
