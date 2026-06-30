from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, BinaryIO

import pandas as pd
import plotly.express as px
from plotly.graph_objects import Figure

from .normalization import municipality_match_key


MAP_METRICS = [
    "Expansion_score",
    "Totalt_registrerade_smadjur_2025",
    "Registrerade_hundar_2025",
    "Registrerade_katter_2025",
    "Smadjur_per_veterinarforetag",
    "Smadjur_score",
    "Konkurrens_score",
]

HOVER_COLUMNS = [
    "Kommun",
    "Län",
    "Registrerade_hundar_2025",
    "Registrerade_katter_2025",
    "Totalt_registrerade_smadjur_2025",
    "Veterinarforetag_antal",
    "Smadjur_per_veterinarforetag",
    "Expansion_score",
]

MUNICIPALITY_NAME_PROPERTIES = [
    "Kommun",
    "kommun",
    "KOMMUN",
    "Kommunnamn",
    "kommunnamn",
    "KOMMUNNAMN",
    "name",
    "Name",
    "NAMN",
    "namn",
    "KnNamn",
    "knnamn",
]


def load_geojson(source: BinaryIO) -> dict[str, Any]:
    if hasattr(source, "seek"):
        source.seek(0)
    raw = source.read()
    if isinstance(raw, bytes):
        text = raw.decode("utf-8-sig")
    else:
        text = raw
    return json.loads(text)


def prepare_municipality_geojson(geojson: dict[str, Any]) -> tuple[dict[str, Any], str, set[str]]:
    prepared = deepcopy(geojson)
    features = prepared.get("features", [])
    if not features:
        raise ValueError("GeoJSON-filen saknar features.")

    name_property = _detect_name_property(features)
    if name_property is None:
        raise ValueError("Kunde inte hitta ett kommunnamnsfält i GeoJSON-filen.")

    geojson_names: set[str] = set()
    for feature in features:
        properties = feature.setdefault("properties", {})
        match_name = municipality_match_key(properties.get(name_property))
        properties["__match_name"] = match_name
        if match_name:
            geojson_names.add(match_name)

    return prepared, name_property, geojson_names


def build_map_dataframe(master: pd.DataFrame, geojson_names: set[str]) -> tuple[pd.DataFrame, list[str]]:
    map_df = master.copy()
    map_df["__match_name"] = map_df["Kommun"].map(municipality_match_key)

    for column in HOVER_COLUMNS + MAP_METRICS:
        if column not in map_df.columns:
            map_df[column] = pd.NA

    unmatched = (
        map_df.loc[~map_df["__match_name"].isin(geojson_names), "Kommun"]
        .dropna()
        .astype(str)
        .sort_values()
        .tolist()
    )
    return map_df, unmatched


def create_municipality_choropleth(
    map_df: pd.DataFrame,
    geojson: dict[str, Any],
    metric: str,
) -> Figure:
    if metric not in map_df.columns:
        raise ValueError(f"Måttet {metric} finns inte i masterdata.")

    fig = px.choropleth(
        map_df,
        geojson=geojson,
        locations="__match_name",
        featureidkey="properties.__match_name",
        color=metric,
        hover_name="Kommun",
        hover_data={column: True for column in HOVER_COLUMNS if column in map_df.columns},
        color_continuous_scale="Viridis",
        labels={metric: metric},
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(
        height=650,
        margin={"r": 0, "t": 30, "l": 0, "b": 0},
        title=f"Kommuner färgade efter {metric}",
    )
    return fig


def _detect_name_property(features: list[dict[str, Any]]) -> str | None:
    property_names: set[str] = set()
    for feature in features:
        property_names.update(feature.get("properties", {}).keys())

    for candidate in MUNICIPALITY_NAME_PROPERTIES:
        if candidate in property_names:
            return candidate
    return None
