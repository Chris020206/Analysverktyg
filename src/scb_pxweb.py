from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import pandas as pd
import requests

from .normalization import normalize_municipality_name


POPULATION_URL = "https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101A/BefolkningNy"
POPULATION_CONTENT_CODE = "BE0101N1"
SOURCE_POPULATION = "SCB PxWeb: BefolkningNy"
REQUEST_DELAY_SECONDS = 0.4


class ScbPxWebError(RuntimeError):
    pass


@dataclass(frozen=True)
class ScbDatasetResult:
    key: str
    label: str
    status: str
    data: pd.DataFrame | None = None
    explanation: str | None = None

    @property
    def is_available(self) -> bool:
        return self.status == "available" and self.data is not None


@dataclass(frozen=True)
class PxWebClient:
    base_url: str
    timeout_seconds: int = 30
    request_delay_seconds: float = REQUEST_DELAY_SECONDS

    def get_metadata(self) -> dict[str, Any]:
        self._polite_delay()
        try:
            response = requests.get(self.base_url, timeout=self.timeout_seconds)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise ScbPxWebError(f"Kunde inte hämta metadata från SCB: {exc}") from exc
        except ValueError as exc:
            raise ScbPxWebError("SCB returnerade metadata som inte kunde tolkas som JSON.") from exc

    def post_query(self, query: dict[str, Any]) -> dict[str, Any]:
        self._polite_delay()
        headers = {"Content-Type": "application/json"}
        try:
            response = requests.post(self.base_url, json=query, headers=headers, timeout=self.timeout_seconds)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise ScbPxWebError(f"Kunde inte hämta data från SCB: {exc}") from exc
        except ValueError as exc:
            raise ScbPxWebError("SCB returnerade data som inte kunde tolkas som JSON.") from exc

    def _polite_delay(self) -> None:
        if self.request_delay_seconds > 0:
            time.sleep(self.request_delay_seconds)


def fetch_population_by_municipality() -> pd.DataFrame:
    metadata = _population_metadata()
    region_values, region_labels = _municipality_regions(metadata)
    year = _latest_year(metadata)
    payload = _fetch_population_values(metadata, region_values, [year])
    values = _json_stat_values(payload)

    if len(values) != len(region_values):
        raise ScbPxWebError("SCB-svaret hade oväntad längd och kunde inte matchas mot kommunlistan.")

    return pd.DataFrame(
        {
            "Kommunkod": region_values,
            "Kommun": [normalize_municipality_name(region_labels[code]) for code in region_values],
            "Folkmangd": pd.Series(pd.to_numeric(values, errors="coerce"), dtype="Int64"),
            "Ar": year,
            "Source": SOURCE_POPULATION,
        }
    )


def fetch_population_change_by_municipality() -> ScbDatasetResult:
    try:
        metadata = _population_metadata()
        region_values, region_labels = _municipality_regions(metadata)
        years = _latest_years(metadata, count=6)
        payload = _fetch_population_values(metadata, region_values, years)
        wide = _population_values_to_wide(payload, region_values, years)
        latest_year = years[-1]
        one_year_before = str(int(latest_year) - 1)
        five_years_before = str(int(latest_year) - 5)

        wide["Befolkningsforandring_1_ar"] = wide[latest_year] - wide[one_year_before]
        wide["Befolkningsforandring_5_ar"] = wide[latest_year] - wide[five_years_before]
        result = pd.DataFrame(
            {
                "Kommunkod": wide["Kommunkod"],
                "Kommun": wide["Kommunkod"].map(lambda code: normalize_municipality_name(region_labels[code])),
                "Ar": latest_year,
                "Source": SOURCE_POPULATION,
                "Befolkningsforandring_1_ar": wide["Befolkningsforandring_1_ar"],
                "Befolkningsforandring_5_ar": wide["Befolkningsforandring_5_ar"],
            }
        )
        return ScbDatasetResult("population_change", "Befolkningsförändring", "available", result)
    except ScbPxWebError as exc:
        return ScbDatasetResult("population_change", "Befolkningsförändring", "error", explanation=str(exc))


def fetch_age_structure_by_municipality() -> ScbDatasetResult:
    try:
        metadata = _population_metadata()
        region_values, region_labels = _municipality_regions(metadata)
        year = _latest_year(metadata)
        age_values = [str(age) for age in range(0, 101)] + ["100+"]
        payload = _fetch_population_values(metadata, region_values, [year], age_values=age_values)
        values = _json_stat_values(payload)
        expected = len(region_values) * len(age_values)
        if len(values) != expected:
            raise ScbPxWebError("SCB-svaret för åldersstruktur hade oväntad längd.")

        rows = []
        position = 0
        for region_code in region_values:
            ages = pd.Series(pd.to_numeric(values[position : position + len(age_values)], errors="coerce")).fillna(0)
            position += len(age_values)
            rows.append(
                {
                    "Kommunkod": region_code,
                    "Kommun": normalize_municipality_name(region_labels[region_code]),
                    "Ar": year,
                    "Source": SOURCE_POPULATION,
                    "Alder_0_17": int(ages.iloc[0:18].sum()),
                    "Alder_18_64": int(ages.iloc[18:65].sum()),
                    "Alder_65_plus": int(ages.iloc[65:].sum()),
                }
            )
        return ScbDatasetResult("age_structure", "Åldersstruktur", "available", pd.DataFrame(rows))
    except ScbPxWebError as exc:
        return ScbDatasetResult("age_structure", "Åldersstruktur", "error", explanation=str(exc))


def fetch_area_by_municipality() -> ScbDatasetResult:
    return ScbDatasetResult(
        "area",
        "Kommunareal",
        "not_available",
        explanation="Ingen stabil SCB PxWeb-tabell för kommunal yta har verifierats i detta steg.",
    )


def calculate_population_density(
    population: pd.DataFrame | None,
    area: pd.DataFrame | None,
) -> ScbDatasetResult:
    if population is None or area is None or area.empty:
        return ScbDatasetResult(
            "density",
            "Befolkningstäthet",
            "not_available",
            explanation="Befolkningstäthet kräver både Folkmangd och Yta_km2. Yta_km2 är inte tillgänglig ännu.",
        )

    merged = _merge_scb_frames(population, area)
    if "Folkmangd" not in merged.columns or "Yta_km2" not in merged.columns:
        return ScbDatasetResult(
            "density",
            "Befolkningstäthet",
            "not_available",
            explanation="Befolkningstäthet kunde inte beräknas eftersom nödvändiga kolumner saknas.",
        )

    merged["Befolkningstathet"] = pd.to_numeric(merged["Folkmangd"], errors="coerce") / pd.to_numeric(
        merged["Yta_km2"],
        errors="coerce",
    )
    result = merged[["Kommunkod", "Kommun", "Ar", "Source", "Befolkningstathet"]].copy()
    result["Source"] = "Beräknad: Folkmangd / Yta_km2"
    return ScbDatasetResult("density", "Befolkningstäthet", "available", result)


def fetch_income_by_municipality() -> ScbDatasetResult:
    return ScbDatasetResult(
        "income",
        "Inkomst",
        "not_available",
        explanation="Ingen stabil SCB PxWeb-tabell för medianinkomst eller disponibel inkomst har verifierats i detta steg.",
    )


def fetch_households_by_municipality() -> ScbDatasetResult:
    return ScbDatasetResult(
        "households",
        "Hushåll",
        "not_available",
        explanation="Ingen stabil SCB PxWeb-tabell för hushåll per kommun har verifierats i detta steg.",
    )


def fetch_demographic_datasets() -> dict[str, ScbDatasetResult]:
    results: dict[str, ScbDatasetResult] = {}

    try:
        population = fetch_population_by_municipality()
        results["population"] = ScbDatasetResult("population", "Folkmängd", "available", population)
    except ScbPxWebError as exc:
        results["population"] = ScbDatasetResult("population", "Folkmängd", "error", explanation=str(exc))
        population = None

    results["area"] = fetch_area_by_municipality()
    area_data = results["area"].data if results["area"].is_available else None
    results["density"] = calculate_population_density(population, area_data)
    results["population_change"] = fetch_population_change_by_municipality()
    results["age_structure"] = fetch_age_structure_by_municipality()
    results["income"] = fetch_income_by_municipality()
    results["households"] = fetch_households_by_municipality()
    return results


def merge_demographics(master_source: pd.DataFrame, results: dict[str, ScbDatasetResult]) -> pd.DataFrame:
    merged = master_source.copy()
    for result in results.values():
        if not result.is_available or result.data is None:
            continue
        scb_frame = result.data.copy()
        scb_frame = scb_frame.rename(
            columns={
                "Ar": f"{result.key}_Ar",
                "Source": f"{result.key}_Source",
            }
        )
        merged = _merge_scb_frames(merged, scb_frame)
    return merged


def _population_metadata() -> dict[str, Any]:
    return PxWebClient(POPULATION_URL).get_metadata()


def _fetch_population_values(
    metadata: dict[str, Any],
    region_values: list[str],
    years: list[str],
    age_values: list[str] | None = None,
) -> dict[str, Any]:
    query_items = [
        {"code": "Region", "selection": {"filter": "item", "values": region_values}},
        {"code": "ContentsCode", "selection": {"filter": "item", "values": [POPULATION_CONTENT_CODE]}},
        {"code": "Tid", "selection": {"filter": "item", "values": years}},
    ]
    if age_values is not None:
        _assert_age_values_available(metadata, age_values)
        query_items.insert(1, {"code": "Alder", "selection": {"filter": "item", "values": age_values}})

    query = {"query": query_items, "response": {"format": "JSON-stat2"}}
    return PxWebClient(POPULATION_URL).post_query(query)


def _municipality_regions(metadata: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    region = _metadata_variable(metadata, "Region")
    values = region.get("values", [])
    labels = region.get("valueTexts", [])
    if not values or not labels or len(values) != len(labels):
        raise ScbPxWebError("SCB-metadata saknar en giltig kommunlista.")

    municipality_values = [code for code in values if isinstance(code, str) and len(code) == 4 and code.isdigit()]
    municipality_labels = dict(zip(values, labels, strict=False))
    if not municipality_values:
        raise ScbPxWebError("SCB-metadata innehöll inga kommunkoder.")

    return municipality_values, municipality_labels


def _latest_year(metadata: dict[str, Any]) -> str:
    return _latest_years(metadata, count=1)[-1]


def _latest_years(metadata: dict[str, Any], count: int) -> list[str]:
    time_variable = _metadata_variable(metadata, "Tid")
    years = [str(year) for year in time_variable.get("values", [])]
    if len(years) < count:
        raise ScbPxWebError(f"SCB-metadata saknar minst {count} årtal.")
    return years[-count:]


def _metadata_variable(metadata: dict[str, Any], code: str) -> dict[str, Any]:
    for variable in metadata.get("variables", []):
        if variable.get("code") == code:
            return variable
    raise ScbPxWebError(f"SCB-metadata saknar variabeln {code}.")


def _assert_age_values_available(metadata: dict[str, Any], age_values: list[str]) -> None:
    age_variable = _metadata_variable(metadata, "Alder")
    available = set(age_variable.get("values", []))
    missing = [age for age in age_values if age not in available]
    if missing:
        raise ScbPxWebError("SCB-metadata saknar åldersvärden: " + ", ".join(missing))


def _json_stat_values(payload: dict[str, Any]) -> list[Any]:
    values = payload.get("value")
    if values is None:
        raise ScbPxWebError("SCB-svaret saknar värden.")
    if isinstance(values, dict):
        size = payload.get("size", [])
        expected_length = 1
        for dimension_size in size:
            expected_length *= int(dimension_size)
        dense = [None] * expected_length
        for index, value in values.items():
            dense[int(index)] = value
        return dense
    return list(values)


def _population_values_to_wide(payload: dict[str, Any], region_values: list[str], years: list[str]) -> pd.DataFrame:
    values = _json_stat_values(payload)
    expected = len(region_values) * len(years)
    if len(values) != expected:
        raise ScbPxWebError("SCB-svaret för befolkningsförändring hade oväntad längd.")

    rows = []
    position = 0
    for region_code in region_values:
        row = {"Kommunkod": region_code}
        for year in years:
            row[year] = pd.to_numeric(values[position], errors="coerce")
            position += 1
        rows.append(row)
    return pd.DataFrame(rows)


def _merge_scb_frames(left: pd.DataFrame, right: pd.DataFrame) -> pd.DataFrame:
    if "Kommunkod" in left.columns and "Kommunkod" in right.columns:
        right_for_merge = right.drop(columns=["Kommun"], errors="ignore")
        return left.merge(right_for_merge, on="Kommunkod", how="left", suffixes=("", "_scb"))

    left_for_merge = left.copy()
    right_for_merge = right.drop(columns=["Kommunkod"], errors="ignore").copy()
    left_for_merge["Kommun"] = left_for_merge["Kommun"].map(normalize_municipality_name)
    right_for_merge["Kommun"] = right_for_merge["Kommun"].map(normalize_municipality_name)
    return left_for_merge.merge(right_for_merge, on="Kommun", how="left", suffixes=("", "_scb"))
