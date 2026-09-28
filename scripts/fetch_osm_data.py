"""Download the OpenStreetMap layers used by the analysis into data/osm/.

The data.mos.ru catering register used in 2019 is no longer reachable (the Dropbox copy
was disabled), so cafés, restaurants and universities come from an OpenStreetMap snapshot.
Re-running this script replaces the snapshot with the current state of OpenStreetMap.

    python scripts/fetch_osm_data.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from moscow_cafes.geo import RED_SQUARE, distance_from  # noqa: E402
from moscow_cafes.osm import (  # noqa: E402
    CATERING_AMENITIES,
    EDUCATION_AMENITIES,
    bbox_around,
    build_query,
    elements_to_frame,
    run_query,
)

# The candidate grid reaches 6 km from Red Square and each cell looks 300 m around itself.
RADIUS_M = 7000
LAYERS = {"catering": CATERING_AMENITIES, "education": EDUCATION_AMENITIES}


def main():
    out_dir = ROOT / "data" / "osm"
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {"source": "OpenStreetMap contributors, ODbL 1.0", "center": RED_SQUARE, "radius_m": RADIUS_M}
    for layer, amenities in LAYERS.items():
        query = build_query(amenities, bbox_around(*RED_SQUARE, RADIUS_M))
        payload = run_query(query)
        frame = elements_to_frame(payload)
        frame = frame[distance_from(frame, *RED_SQUARE) <= RADIUS_M].sort_values(["osm_type", "osm_id"])
        frame.to_csv(out_dir / f"osm_{layer}.csv", index=False)
        meta[layer] = {
            "timestamp_osm_base": payload["osm3s"]["timestamp_osm_base"],
            "records": len(frame),
            "query": query,
        }
        print(f"{layer}: {len(frame)} objects, OSM snapshot {meta[layer]['timestamp_osm_base']}")
    (out_dir / "osm_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
