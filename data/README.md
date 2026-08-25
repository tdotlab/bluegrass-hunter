# Settlement data

`kentucky_settlements.json` is a small manifest for the checked-in settlement index. The records live in numbered JSON parts under `data/kentucky_settlements/` so the full database remains readable and reviewable through GitHub.

The application loads the parts automatically. A local rebuild instead writes one generated JSON file:

```bash
python scripts/build_place_index.py
```

The builder combines:

- USGS Geographic Names Information System populated places.
- The 2025 U.S. Census Gazetteer place file.

The generated JSON records the source URLs and generation timestamp. The public data sources retain their own terms and notices; this repository does not claim ownership of the underlying government data.
