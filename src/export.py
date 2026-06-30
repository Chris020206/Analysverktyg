from __future__ import annotations

import json
from io import BytesIO
from typing import Any

import pandas as pd


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def dataframes_to_excel_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet_name, df in sheets.items():
            df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
    return buffer.getvalue()


def build_markdown_summary(
    master: pd.DataFrame,
    top_candidates: pd.DataFrame,
    metrics: dict[str, int | float | None],
) -> str:
    top_rows = top_candidates.head(10)
    lines = [
        "# Expansion analysis context",
        "",
        "## Business question",
        "Where should Härryda Djurklinik AB expand?",
        "",
        "## Data status",
        f"- Municipalities in master dataset: {metrics['municipalities']}",
        f"- Registered dogs 2025: {metrics['total_dogs']:.0f}",
        f"- Registered cats 2025: {metrics['total_cats']:.0f}",
        f"- Registered small animals 2025: {metrics['total_small_animals']:.0f}",
        "- SCB PxWeb population can be included when fetched in the app. Other SCB fields and the veterinary business register remain placeholders.",
        "",
        "## Preliminary top candidates",
    ]

    if top_rows.empty:
        lines.append("No candidates available.")
    else:
        for _, row in top_rows.iterrows():
            lines.append(
                "- "
                f"{row.get('Kommun', '')}, {row.get('Län', '')}: "
                f"Expansion score {_format_number(row.get('Expansion_score'))}; "
                f"small animals {_format_number(row.get('Smadjur_score'))}, "
                f"competition {_format_number(row.get('Konkurrens_score'))}, "
                f"population {_format_number(row.get('Folkmangd_score'))}, "
                f"density {_format_number(row.get('Befolkningstathet_score'))}, "
                f"animal ownership intensity {_format_number(row.get('Djurtagande_score'))}. "
                f"Registered dogs and cats: {_format_number(row.get('Totalt_registrerade_smadjur_2025'), decimals=0)}"
            )

    lines.extend(
        [
            "",
            "## Method note",
            "The preliminary Expansion_score is a decision-support indicator, not a final recommendation. "
            "It combines available component scores for small animal demand, veterinary competition, population, "
            "population density, and animal ownership intensity per 1,000 inhabitants. When SCB or competitor fields are missing, those components "
            "are excluded and the remaining weights are normalized.",
            "",
            "## Missing-data limitations",
            "This version must not be interpreted as a complete market assessment until SCB demographics, "
            "veterinary business register data, travel time, premises, revenue, and staffing constraints have been added.",
        ]
    )
    return "\n".join(lines)


def build_json_context(
    master: pd.DataFrame,
    top_candidates: pd.DataFrame,
    horses: pd.DataFrame | None,
    metrics: dict[str, int | float | None],
) -> bytes:
    context = {
        "business_question": "Where should Härryda Djurklinik AB expand?",
        "data_status": {
            "local_dogs_csv": True,
            "local_cats_csv": True,
            "local_horses_csv": horses is not None,
            "scb_pxweb_population": "included" if _has_field(master, "Folkmangd") else "not_fetched",
            "scb_pxweb_area": "included" if _has_field(master, "Yta_km2") else "not_available",
            "scb_pxweb_density": "included" if _has_field(master, "Befolkningstathet") else "not_available",
            "scb_pxweb_population_change": "included" if _has_field(master, "Befolkningsforandring_1_ar") else "not_fetched",
            "scb_pxweb_age_structure": "included" if _has_field(master, "Alder_0_17") else "not_fetched",
            "scb_pxweb_income": "placeholder_not_active",
            "scb_pxweb_households": "placeholder_not_active",
            "scb_pxweb_housing": "placeholder_not_active",
            "scb_pxweb_other_demographics": "not_implemented",
            "scb_business_register_api": "not_implemented",
        },
        "metrics": metrics,
        "top_candidates": top_candidates.head(20).to_dict(orient="records"),
        "horse_data_by_county": [] if horses is None else horses.to_dict(orient="records"),
        "schema": {
            "master_municipality_columns": list(master.columns),
            "ranking_basis": "Expansion_score descending when available; otherwise Totalt_registrerade_smadjur_2025 descending",
        },
    }
    text = json.dumps(context, ensure_ascii=False, indent=2, default=str)
    return text.encode("utf-8")


def _format_number(value: Any, decimals: int = 1) -> str:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return "missing"
    return f"{numeric:.{decimals}f}"


def _has_field(master: pd.DataFrame, column: str) -> bool:
    return column in master.columns and master[column].notna().any()
