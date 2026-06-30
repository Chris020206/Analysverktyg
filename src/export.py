from __future__ import annotations

import json
from io import BytesIO

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
        "- SCB municipality and veterinary business register fields are placeholders in this initial version.",
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
                f"{row.get('Totalt_registrerade_smadjur_2025', 0):.0f} registered dogs and cats"
            )

    lines.extend(
        [
            "",
            "## Method note",
            "The preliminary ranking sorts municipalities by registered dogs and cats in 2025. "
            "It does not yet include SCB demographics, competitors, travel time, premises, revenue, or staffing constraints.",
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
            "scb_pxweb_api": "not_implemented",
            "scb_business_register_api": "not_implemented",
        },
        "metrics": metrics,
        "top_candidates": top_candidates.head(20).to_dict(orient="records"),
        "horse_data_by_county": [] if horses is None else horses.to_dict(orient="records"),
        "schema": {
            "master_municipality_columns": list(master.columns),
            "ranking_basis": "Totalt_registrerade_smadjur_2025 descending",
        },
    }
    text = json.dumps(context, ensure_ascii=False, indent=2, default=str)
    return text.encode("utf-8")
