from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.analysis import build_master_municipality_dataset, build_top_candidates, summary_metrics
from src.export import (
    build_json_context,
    build_markdown_summary,
    dataframe_to_csv_bytes,
    dataframes_to_excel_bytes,
)
from src.import_animals import load_cats, load_dogs, load_horses, merge_dogs_and_cats


APP_TITLE = "Expansion analys - Härryda Djurklinik AB"
OUTPUT_DIR = Path("output")


st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)
st.caption("Internt beslutsstöd för en första analys av möjliga expansionsorter.")


def show_data_status(label: str, uploaded_file, loaded: pd.DataFrame | None, error: str | None) -> None:
    if error:
        st.error(f"{label}: {error}")
    elif loaded is not None:
        st.success(f"{label}: {len(loaded):,} rader inlästa".replace(",", " "))
    elif uploaded_file is None:
        st.info(f"{label}: ingen fil uppladdad")


with st.sidebar:
    st.header("Filuppladdning")
    dogs_file = st.file_uploader("Hundar per kommun", type=["csv"])
    cats_file = st.file_uploader("Katter per kommun", type=["csv"])
    horses_file = st.file_uploader("Hästar per län", type=["csv"])

    st.header("Analyskontroller")
    top_n = st.slider("Antal kandidater i topplistan", min_value=5, max_value=50, value=20, step=5)


dogs_df = cats_df = horses_df = None
dog_error = cat_error = horse_error = None

if dogs_file is not None:
    try:
        dogs_df = load_dogs(dogs_file)
    except Exception as exc:
        dog_error = str(exc)

if cats_file is not None:
    try:
        cats_df = load_cats(cats_file)
    except Exception as exc:
        cat_error = str(exc)

if horses_file is not None:
    try:
        horses_df = load_horses(horses_file)
    except Exception as exc:
        horse_error = str(exc)


st.subheader("Datastatus")
status_cols = st.columns(3)
with status_cols[0]:
    show_data_status("Hundfil", dogs_file, dogs_df, dog_error)
with status_cols[1]:
    show_data_status("Kattfil", cats_file, cats_df, cat_error)
with status_cols[2]:
    show_data_status("Hästfil", horses_file, horses_df, horse_error)

st.info("SCB PxWeb och SCB Företagsregister är inte aktiverade i denna första version. Fälten finns som tomma platshållare.")


can_analyze = dogs_df is not None and cats_df is not None and dog_error is None and cat_error is None

if not can_analyze:
    st.warning("Ladda upp giltiga hund- och kattfiler för att skapa masterdata och rankning.")
    st.stop()


animals_df = merge_dogs_and_cats(dogs_df, cats_df)
master_df = build_master_municipality_dataset(animals_df)
top_candidates_df = build_top_candidates(master_df, top_n=top_n)
metrics = summary_metrics(master_df, horses_df)
markdown_summary = build_markdown_summary(master_df, top_candidates_df, metrics)
json_context = build_json_context(master_df, top_candidates_df, horses_df, metrics)


st.subheader("Sammanfattande nyckeltal")
metric_cols = st.columns(4)
metric_cols[0].metric("Kommuner", f"{metrics['municipalities']:.0f}")
metric_cols[1].metric("Hundar 2025", f"{metrics['total_dogs']:.0f}")
metric_cols[2].metric("Katter 2025", f"{metrics['total_cats']:.0f}")
metric_cols[3].metric("Hundar + katter", f"{metrics['total_small_animals']:.0f}")


st.subheader("Preliminär rankning")
display_columns = [
    "Preliminar_rankning",
    "Län",
    "Kommun",
    "Registrerade_hundar_2025",
    "Registrerade_katter_2025",
    "Totalt_registrerade_smadjur_2025",
    "Folkmangd",
    "Befolkningstathet",
    "Veterinarforetag_antal",
    "Expansion_score",
]
st.dataframe(top_candidates_df[display_columns], use_container_width=True, hide_index=True)


st.subheader("Interaktiv karta")
st.info("Kartvy kommer i nästa steg när geodata eller kommunkoder finns på plats.")

chart_df = top_candidates_df.sort_values("Totalt_registrerade_smadjur_2025", ascending=True)
fig = px.bar(
    chart_df,
    x="Totalt_registrerade_smadjur_2025",
    y="Kommun",
    color="Län",
    orientation="h",
    labels={
        "Totalt_registrerade_smadjur_2025": "Registrerade hundar och katter 2025",
        "Kommun": "Kommun",
    },
    title="Topplista baserad på registrerade hundar och katter",
)
fig.update_layout(height=max(420, 24 * len(chart_df)), title_x=0)
st.plotly_chart(fig, use_container_width=True)


st.subheader("Export")
OUTPUT_DIR.mkdir(exist_ok=True)
excel_bytes = dataframes_to_excel_bytes(
    {
        "master_municipality_dataset": master_df,
        "top_expansion_candidates": top_candidates_df,
        "horses_by_county": pd.DataFrame() if horses_df is None else horses_df,
    }
)

export_cols = st.columns(4)
with export_cols[0]:
    st.download_button(
        "Master CSV",
        dataframe_to_csv_bytes(master_df),
        file_name="master_municipality_dataset.csv",
        mime="text/csv",
    )
with export_cols[1]:
    st.download_button(
        "Toppkandidater CSV",
        dataframe_to_csv_bytes(top_candidates_df),
        file_name="top_expansion_candidates.csv",
        mime="text/csv",
    )
with export_cols[2]:
    st.download_button(
        "Excel",
        excel_bytes,
        file_name="analysverktyg_export.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
with export_cols[3]:
    st.download_button(
        "AI JSON",
        json_context,
        file_name="ai_context.json",
        mime="application/json",
    )

st.download_button(
    "AI Markdown-sammanfattning",
    markdown_summary.encode("utf-8"),
    file_name="ai_summary.md",
    mime="text/markdown",
)
