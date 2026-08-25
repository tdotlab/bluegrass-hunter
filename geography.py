import json
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


DATA_PATH = (
    Path(__file__).resolve().parent / "data" / "kentucky_settlements.json"
)
STATE_NAME = "Kentucky"


class AnchorLocation(BaseModel):
    query: str
    display_name: str
    latitude: float
    longitude: float


class Settlement(BaseModel):
    name: str
    latitude: float
    longitude: float
    population: str | None = None
    county: str | None = None
    place_status: str | None = None
    searchable: bool = True
    sources: list[str] = Field(default_factory=list)
    source_types: list[str] = Field(default_factory=list)


class RegionExpansion(BaseModel):
    state: str
    dataset_generated_at: str
    anchors: list[AnchorLocation]
    settlements: list[Settlement]
    warnings: list[str] = Field(default_factory=list)
    source_notes: list[str] = Field(default_factory=list)


def _normalize_name(value: str) -> str:
    value = re.sub(r"\s+", " ", value.strip()).casefold()
    return re.sub(
        r"\s+(city|town|village|borough|municipality|cdp)$",
        "",
        value,
    )


def _load_checked_in_parts(payload: dict[str, Any]) -> dict[str, Any]:
    parts = payload.get("parts")
    if not parts:
        return payload

    settlements: list[dict[str, Any]] = []
    for relative_path in parts:
        part_path = DATA_PATH.parent / relative_path
        part_payload = json.loads(part_path.read_text(encoding="utf-8"))
        if isinstance(part_payload, list):
            settlements.extend(part_payload)
        else:
            settlements.extend(part_payload.get("settlements", []))
    payload["settlements"] = settlements
    return payload


@lru_cache(maxsize=1)
def _load_index() -> dict[str, Any]:
    if not DATA_PATH.exists():
        builder = DATA_PATH.parent.parent / "scripts" / "build_place_index.py"
        try:
            subprocess.run(
                [sys.executable, str(builder)],
                cwd=str(builder.parent.parent),
                check=True,
                timeout=180,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError(
                "Settlement index is missing and could not be generated automatically."
            ) from exc
    if not DATA_PATH.exists():
        raise RuntimeError(f"Settlement index was not created at {DATA_PATH}.")
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return _load_checked_in_parts(payload)


def _resolve_anchor(query: str, settlements: list[dict[str, Any]]) -> AnchorLocation:
    normalized_query = _normalize_name(query.split(",")[0])
    matches = [
        item
        for item in settlements
        if _normalize_name(item["name"]) == normalized_query
    ]
    if not matches:
        raise ValueError(
            f"Anchor {query!r} is not in the Kentucky settlement index. "
            "Use a named Kentucky town or add it to the index."
        )

    matches.sort(
        key=lambda item: (
            "incorporated_place" not in item.get("source_types", []),
            "census_designated_place" not in item.get("source_types", []),
            "historical" in item.get("name", "").casefold(),
        )
    )
    match = matches[0]
    return AnchorLocation(
        query=query,
        display_name=f"{match['name']}, Kentucky",
        latitude=float(match["latitude"]),
        longitude=float(match["longitude"]),
    )


def _point_in_polygon(
    longitude: float,
    latitude: float,
    polygon: list[tuple[float, float]],
) -> bool:
    inside = False
    previous = len(polygon) - 1
    for current in range(len(polygon)):
        current_lon, current_lat = polygon[current]
        previous_lon, previous_lat = polygon[previous]
        crosses_latitude = (current_lat > latitude) != (previous_lat > latitude)
        if crosses_latitude:
            intersection_lon = (
                (previous_lon - current_lon)
                * (latitude - current_lat)
                / (previous_lat - current_lat)
                + current_lon
            )
            if longitude < intersection_lon:
                inside = not inside
        previous = current
    return inside


def select_settlements(names: list[str]) -> list[Settlement]:
    index = _load_index()
    searchable = [
        item for item in index.get("settlements", [])
        if item.get("searchable", True)
    ]
    priority = {
        "incorporated_place": 0,
        "census_designated_place": 1,
        "unincorporated_populated_place": 2,
    }
    selected: list[Settlement] = []
    missing: list[str] = []
    for requested in names:
        normalized = _normalize_name(requested)
        matches = [
            item for item in searchable
            if _normalize_name(item["name"]) == normalized
        ]
        if not matches:
            missing.append(requested)
            continue
        match = sorted(
            matches,
            key=lambda item: (
                priority.get(item.get("place_status"), 3),
                item["name"].casefold(),
            ),
        )[0]
        selected.append(Settlement.model_validate(match))
    if missing:
        raise ValueError(f"Settlements were not found in the Kentucky index: {missing}")
    return selected


async def expand_region(anchor_queries: list[str]) -> RegionExpansion:
    if len(anchor_queries) < 3:
        raise ValueError("A region requires at least three named anchor locations.")
    if len(anchor_queries) > 5:
        raise ValueError("Use no more than five anchor locations.")

    index = _load_index()
    indexed_settlements = [
        item for item in index.get("settlements", [])
        if item.get("searchable", True)
    ]
    anchors = [
        _resolve_anchor(query, indexed_settlements)
        for query in anchor_queries
    ]
    polygon = [
        (anchor.longitude, anchor.latitude)
        for anchor in anchors
    ]

    settlements = [
        Settlement.model_validate(item)
        for item in indexed_settlements
        if _point_in_polygon(
            float(item["longitude"]), float(item["latitude"]),
            polygon,
        )
    ]
    settlements.sort(key=lambda item: item.name.casefold())

    warnings: list[str] = []
    if len(settlements) < 10:
        warnings.append(
            "The local gazetteer returned a small settlement set; inspect the "
            "anchors and polygon before launching business searches."
        )

    source_notes = [
        "Anchors and settlements were resolved from a locally generated Kentucky gazetteer index.",
        "The index combines USGS GNIS populated places with the 2025 U.S. Census Gazetteer.",
        "Historical GNIS places are retained in the source index but excluded from the searchable settlement queue.",
        "Settlement inclusion uses deterministic point-in-polygon filtering; no LLM or live map query is involved.",
    ]
    return RegionExpansion(
        state=STATE_NAME,
        dataset_generated_at=index.get("generated_at", "unknown"),
        anchors=anchors,
        settlements=settlements,
        warnings=warnings,
        source_notes=source_notes,
    )
