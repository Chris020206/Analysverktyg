from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import pandas as pd
import requests


SCB_ROOT_URL = "https://api.scb.se/OV0104/v1/doris/sv/ssd/START"
REQUEST_DELAY_SECONDS = 0.25

DISCOVERY_TOPICS = {
    "area": {
        "label": "Area",
        "keywords": ["area", "yta", "areal", "landareal"],
    },
    "income": {
        "label": "Inkomst",
        "keywords": ["inkomst", "medianinkomst", "disponibel"],
    },
    "households": {
        "label": "Hushåll",
        "keywords": ["hushåll", "hushall"],
    },
    "housing": {
        "label": "Boendeform / småhus",
        "keywords": ["småhus", "smahus", "boendeform", "bostad"],
    },
}


class ScbDiscoveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class ScbTableCandidate:
    topic: str
    table_id: str
    table_name: str
    path: str
    url: str
    dimensions: list[str]


def discover_tables(topic: str, max_depth: int = 5, max_results: int = 25) -> pd.DataFrame:
    if topic not in DISCOVERY_TOPICS:
        raise ScbDiscoveryError(f"Okänt discovery-område: {topic}")

    candidates: list[ScbTableCandidate] = []
    _walk_returned_nodes(
        topic=topic,
        keywords=DISCOVERY_TOPICS[topic]["keywords"],
        url=SCB_ROOT_URL,
        path=[],
        depth=0,
        max_depth=max_depth,
        max_results=max_results,
        candidates=candidates,
    )
    return pd.DataFrame([candidate.__dict__ for candidate in candidates])


def list_metadata_path(path: list[str] | None = None) -> pd.DataFrame:
    payload = _get_json(_build_url(path or []))
    if not isinstance(payload, list):
        raise ScbDiscoveryError("Metadata-sökvägen pekar på en tabell, inte en listbar nod.")

    return pd.DataFrame(
        {
            "id": item.get("id"),
            "type": item.get("type"),
            "text": item.get("text"),
            "path": "/".join([*(path or []), str(item.get("id", ""))]),
        }
        for item in payload
    )


def get_table_dimensions(path: list[str]) -> list[str]:
    payload = _get_json(_build_url(path), allow_missing=True)
    if not isinstance(payload, dict):
        return []

    return [
        f"{variable.get('code', '')}: {variable.get('text', '')}".strip(": ")
        for variable in payload.get("variables", [])
    ]


def _walk_returned_nodes(
    topic: str,
    keywords: list[str],
    url: str,
    path: list[str],
    depth: int,
    max_depth: int,
    max_results: int,
    candidates: list[ScbTableCandidate],
) -> None:
    if depth > max_depth or len(candidates) >= max_results:
        return

    payload = _get_json(url, allow_missing=True)
    if payload is None or not isinstance(payload, list):
        return

    for item in payload:
        if len(candidates) >= max_results:
            return

        node_id = str(item.get("id", "")).strip()
        node_text = str(item.get("text", "")).strip()
        node_type = str(item.get("type", "")).lower()
        if not node_id:
            continue

        next_path = [*path, node_id]
        next_url = _build_url(next_path)

        if node_type == "t":
            if _matches_keywords(node_text, keywords):
                candidates.append(
                    ScbTableCandidate(
                        topic=topic,
                        table_id=node_id,
                        table_name=node_text,
                        path="/".join(next_path),
                        url=next_url,
                        dimensions=get_table_dimensions(next_path),
                    )
                )
            continue

        if node_type == "l":
            _walk_returned_nodes(
                topic=topic,
                keywords=keywords,
                url=next_url,
                path=next_path,
                depth=depth + 1,
                max_depth=max_depth,
                max_results=max_results,
                candidates=candidates,
            )


def _matches_keywords(text: str, keywords: list[str]) -> bool:
    normalized = text.casefold()
    return any(keyword.casefold() in normalized for keyword in keywords)


def _build_url(path: list[str]) -> str:
    if not path:
        return SCB_ROOT_URL
    return f"{SCB_ROOT_URL}/{'/'.join(path)}"


def _get_json(url: str, allow_missing: bool = False) -> Any:
    time.sleep(REQUEST_DELAY_SECONDS)
    try:
        response = requests.get(url, timeout=30)
        if allow_missing and response.status_code in {400, 404}:
            return None
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if allow_missing and status_code in {400, 404}:
            return None
        raise ScbDiscoveryError(f"Kunde inte läsa SCB-metadata: {exc}") from exc
    except ValueError as exc:
        raise ScbDiscoveryError("SCB-metadata kunde inte tolkas som JSON.") from exc
