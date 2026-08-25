#!/usr/bin/env python3
"""Build a local Kentucky populated-place index from public government data."""

from __future__ import annotations

import csv
import io
import json
import re
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT = DATA_DIR / "kentucky_settlements.json"

GNIS_URL = (
    "https://prd-tnm.s3.amazonaws.com/"
    "StagedProducts/GeographicNames/DomesticNames/DomesticNames_KY_Text.zip"
)
CENSUS_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
    "2025_Gazetteer/2025_gaz_place_21.txt"
)


def download(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "kentucky-web-scout/0.2"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def normalize_name(name: str) -> str:
    value = re.sub(r"\s+", " ", name.strip()).casefold()
    value = re.sub(
        r"\s+(city|town|village|borough|municipality|cdp)$",
        "",
        value,
    )
    return value


def classify_record(record: dict) -> dict:
    name = record["name"].casefold()
    source_types = set(record.get("source_types", []))
    if "incorporated_place" in source_types:
        place_status = "incorporated_place"
    elif "census_designated_place" in source_types:
        place_status = "census_designated_place"
    elif "historical" in name or "(historical)" in name:
        place_status = "historical_place"
    else:
        place_status = "unincorporated_populated_place"
    record["place_status"] = place_status
    record["searchable"] = place_status != "historical_place"
    return record


def add_record(records: dict[str, dict], record: dict) -> None:
    if not record["name"] or record["latitude"] is None or record["longitude"] is None:
        return
    record = classify_record(record)
    key = (
        normalize_name(record["name"]),
        round(record["latitude"], 3),
        round(record["longitude"], 3),
    )
    current = records.get(key)
    if current is None:
        records[key] = record
        return

    sources = sorted(set(current["sources"] + record["sources"]))
    source_types = sorted(set(current["source_types"] + record["source_types"]))
    current["sources"] = sources
    current["source_types"] = source_types
    current = classify_record(current)
    current["population"] = current.get("population") or record.get("population")
    current["county"] = current.get("county") or record.get("county")


def read_gnis(records: dict[str, dict]) -> None:
    archive = zipfile.ZipFile(io.BytesIO(download(GNIS_URL)))
    with archive.open("Text/DomesticNames_KY.txt") as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
        reader = csv.DictReader(text, delimiter="|")
        for row in reader:
            if row.get("feature_class") != "Populated Place":
                continue
            try:
                latitude = float(row["prim_lat_dec"])
                longitude = float(row["prim_long_dec"])
            except (KeyError, TypeError, ValueError):
                continue
            add_record(
                records,
                {
                    "name": row.get("feature_name", "").strip(),
                    "latitude": latitude,
                    "longitude": longitude,
                    "population": None,
                    "county": row.get("county_name") or None,
                    "sources": ["USGS GNIS"],
                    "source_types": ["populated_place"],
                },
            )


def read_census(records: dict[str, dict]) -> None:
    text = download(CENSUS_URL).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text), delimiter="|")
    for row in reader:
        name = row.get("NAME", "").strip()
        try:
            latitude = float(row["INTPTLAT"])
            longitude = float(row["INTPTLONG"])
        except (KeyError, TypeError, ValueError):
            continue

        place_type = "census_designated_place" if row.get("LSAD") == "57" else "incorporated_place"
        add_record(
            records,
            {
                "name": re.sub(
                    r"\s+(city|town|village|borough|municipality|CDP)$",
                    "",
                    name,
                    flags=re.IGNORECASE,
                ),
                "latitude": latitude,
                "longitude": longitude,
                "population": None,
                "county": None,
                "sources": ["U.S. Census Gazetteer 2025"],
                "source_types": [place_type],
            },
        )


def main() -> None:
    records: dict[str, dict] = {}
    read_gnis(records)
    read_census(records)

    settlements = sorted(
        records.values(),
        key=lambda record: (record["name"].casefold(), record["latitude"]),
    )
    if len(settlement := settlements) < 100:
        raise RuntimeError(f"Settlement index unexpectedly small: {len(settlement)}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "state": "Kentucky",
        "generated_at": datetime.now(UTC).isoformat(),
        "sources": [
            {"name": "USGS GNIS", "url": GNIS_URL},
            {"name": "U.S. Census Gazetteer 2025", "url": CENSUS_URL},
        ],
        "settlements": settlements,
        "searchable_count": sum(1 for record in settlements if record["searchable"]),
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(settlements)} settlements to {OUTPUT}")


if __name__ == "__main__":
    main()
