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
from src.mapping import (
    MAP_METRICS,
    build_map_dataframe,
    create_municipality_choropleth,
    load_geojson,
    prepare_municipality_geojson,
)
from src.scb_pxweb import ScbDatasetResult, fetch_demographic_datasets, merge_demographics


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


def show_scb_status(result: ScbDatasetResult | None) -> None:
    if result is None:
        st.info("Inte hämtad")
    elif result.status == "available" and result.data is not None:
        years = ", ".join(sorted(result.data.get("Ar", pd.Series(dtype="string")).dropna().astype(str).unique()))
        suffix = f" ({years})" if years else ""
        st.success(f"{len(result.data):,} rader{suffix}".replace(",", " "))
    elif result.status == "not_available":
        st.warning(result.explanation or "Inte tillgänglig")
    else:
        st.error(result.explanation or "Fel vid hämtning")


if "scb_demographics" not in st.session_state:
    st.session_state.scb_demographics = {}


with st.sidebar:
    st.header("Filuppladdning")
    dogs_file = st.file_uploader("Hundar per kommun", type=["csv"])
    cats_file = st.file_uploader("Katter per kommun", type=["csv"])
    horses_file = st.file_uploader("Hästar per län", type=["csv"])
    geojson_file = st.file_uploader("Kommungränser GeoJSON", type=["geojson", "json"])

    st.header("SCB")
    fetch_population = st.button("Hämta folkmängd från SCB")

    st.header("Analyskontroller")
    top_n = st.slider("Antal kandidater i topplistan", min_value=5, max_value=50, value=20, step=5)
    map_metric = st.selectbox("Kartmått", MAP_METRICS, index=0)


if fetch_population:
    with st.spinner("Hämtar nödvändiga SCB-råvariabler..."):
        st.session_state.scb_demographics = fetch_demographic_datasets()


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

scb_demographics = st.session_state.scb_demographics


st.subheader("Datastatus")
status_cols = st.columns(3)
with status_cols[0]:
    show_data_status("Hundfil", dogs_file, dogs_df, dog_error)
with status_cols[1]:
    show_data_status("Kattfil", cats_file, cats_df, cat_error)
with status_cols[2]:
    show_data_status("Hästfil", horses_file, horses_df, horse_error)

st.markdown("**SCB rådata**")
scb_status_cols = st.columns(4)
scb_keys = [
    ("population", "Folkmängd"),
    ("area", "Yta"),
    ("density", "Täthet"),
    ("population_change", "Förändring"),
]
for column, (key, label) in zip(scb_status_cols, scb_keys, strict=False):
    with column:
        st.caption(label)
        show_scb_status(scb_demographics.get(key))

st.info("SCB-strategin är förenklad: hämta nödvändiga råvariabler och beräkna indikatorer internt. Bred table discovery visas inte i normal UI.")


can_analyze = dogs_df is not None and cats_df is not None and dog_error is None and cat_error is None

if not can_analyze:
    st.warning("Ladda upp giltiga hund- och kattfiler för att skapa masterdata och rankning.")
    st.stop()


animals_df = merge_dogs_and_cats(dogs_df, cats_df)
animals_df = merge_demographics(animals_df, scb_demographics)
master_df = build_master_municipality_dataset(animals_df)

population_result = scb_demographics.get("population")
if population_result is not None and population_result.is_available:
    missing_population = (
        master_df.loc[master_df["Folkmangd"].isna(), "Kommun"]
        .dropna()
        .astype(str)
        .sort_values()
        .tolist()
    )
    if missing_population:
        st.warning("SCB folkmängd saknas efter matchning för: " + ", ".join(missing_population))

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
    "Smadjur_score",
    "Konkurrens_score",
    "Folkmangd_score",
    "Befolkningstathet_score",
    "Djurtagande_score",
    "Folkmangd",
    "Yta_km2",
    "Befolkningstathet",
    "Hundar_per_1000_inv",
    "Katter_per_1000_inv",
    "Smadjur_per_1000_inv",
    "Veterinarforetag_antal",
    "Veterinarforetag_per_10000_smadjur",
    "Smadjur_per_veterinarforetag",
    "Expansion_score",
]
available_display_columns = [column for column in display_columns if column in top_candidates_df.columns]
st.dataframe(top_candidates_df[available_display_columns], use_container_width=True, hide_index=True)


st.subheader("Interaktiv karta")
if geojson_file is None:
    st.info("Ladda upp en svensk kommun-GeoJSON för att visa den interaktiva kartan. Resten av analysen fungerar utan geografi.")
else:
    try:
        municipality_geojson, name_property, geojson_names = prepare_municipality_geojson(load_geojson(geojson_file))
        map_df, unmatched_municipalities = build_map_dataframe(master_df, geojson_names)

        if unmatched_municipalities:
            st.warning(
                "Följande kommuner i masterdata matchades inte mot GeoJSON-filen: "
                + ", ".join(unmatched_municipalities)
            )

        st.caption(f"GeoJSON matchas på kommunnamn via fältet `{name_property}`.")
        map_fig = create_municipality_choropleth(map_df, municipality_geojson, map_metric)
        st.plotly_chart(map_fig, use_container_width=True)
    except Exception as exc:
        st.error(f"Kunde inte skapa kartan: {exc}")


chart_df = top_candidates_df.sort_values("Expansion_score", ascending=True)
fig = px.bar(
    chart_df,
    x="Expansion_score",
    y="Kommun",
    color="Län",
    orientation="h",
    labels={
        "Expansion_score": "Preliminär expansionspoäng",
        "Kommun": "Kommun",
    },
    title="Topplista baserad på preliminär expansionspoäng",
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
        **{
            f"scb_{key}": result.data
            for key, result in scb_demographics.items()
            if result.is_available and result.data is not None
        },
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
