"""Download the OpenStreetMap layers used by the analysis into data/osm/.

The cafés and restaurants of OpenStreetMap show the market of today: notebook 03 compares them with
the catering register of 2019 and builds the 2026 shortlist from them. Universities and colleges
also come from OpenStreetMap, because the education register of 2019 holds only schools.
Re-running this script replaces the snapshot with the current state of OpenStreetMap.

    python scripts/fetch_osm_data.py                      # every layer
    python scripts/fetch_osm_data.py basemap addresses    # only the layers of the report page

Layers: catering, education (analysis inputs); basemap (rivers and ring roads) and
addresses (the nearest Russian street address of every grid cell) for the report page.
"""

import io
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from moscow_cafes.data import load_candidates  # noqa: E402
from moscow_cafes.geo import RED_SQUARE, distance_from, nearest, xy_array  # noqa: E402
from moscow_cafes.osm import (  # noqa: E402
    CATERING_AMENITIES,
    EDUCATION_AMENITIES,
    bbox_around,
    build_address_query,
    build_basemap_query,
    build_query,
    elements_to_frame,
    lines_to_geojson,
    run_query,
)

# The candidate grid reaches 6 km from Red Square and each cell looks 300 m around itself.
RADIUS_M = 7000
AMENITY_LAYERS = {"catering": CATERING_AMENITIES, "education": EDUCATION_AMENITIES}
LAYERS = (*AMENITY_LAYERS, "basemap", "addresses")


def main(layers):
    out_dir = ROOT / "data" / "osm"
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_path = out_dir / "osm_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    meta.update({"source": "OpenStreetMap contributors, ODbL 1.0", "center": RED_SQUARE, "radius_m": RADIUS_M})
    bbox = bbox_around(*RED_SQUARE, RADIUS_M)

    for layer in layers:
        if layer in AMENITY_LAYERS:
            query = build_query(AMENITY_LAYERS[layer], bbox)
            payload = run_query(query)
            frame = elements_to_frame(payload)
            frame = frame[distance_from(frame, *RED_SQUARE) <= RADIUS_M].sort_values(["osm_type", "osm_id"])
            frame.to_csv(out_dir / f"osm_{layer}.csv", index=False)
            meta[layer] = {
                "timestamp_osm_base": payload["osm3s"]["timestamp_osm_base"],
                "records": len(frame),
                "query": query,
            }
        elif layer == "basemap":
            query = build_basemap_query(bbox)
            payload = run_query(query)
            geojson = lines_to_geojson(payload)
            (out_dir / "osm_basemap.geojson").write_text(json.dumps(geojson, ensure_ascii=False), encoding="utf-8")
            meta[layer] = {
                "timestamp_osm_base": payload["osm3s"]["timestamp_osm_base"],
                "records": len(geojson["features"]),
                "query": query,
            }
        elif layer == "addresses":
            query = build_address_query(bbox)
            addresses = nearest_addresses(run_query(query, as_json=False))
            addresses.to_csv(out_dir / "osm_cell_addresses_ru.csv", index=False)
            meta[layer] = {
                "retrieved": date.today().isoformat(),
                "records": int(addresses["address"].notna().sum()),
                "query": query,
            }
        else:
            raise SystemExit(f"Unknown layer {layer!r}; choose from {', '.join(LAYERS)}")
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{layer}: {meta[layer]['records']} records")


def nearest_addresses(text, max_distance_m=250):
    """The OpenStreetMap street address nearest to every grid cell centre (none beyond `max_distance_m`)."""
    points = pd.read_csv(io.StringIO(text), sep="\t", names=["lat", "lon", "street", "housenumber"], dtype=str)
    points = points.dropna().astype({"lat": float, "lon": float})
    cells = load_candidates()
    distances, positions = nearest(xy_array(cells), xy_array(points))
    chosen = points.iloc[positions]
    addresses = pd.DataFrame(
        {
            "cell_id": cells.index,
            "address": (chosen["street"] + ", " + chosen["housenumber"]).to_numpy(),
            "distance_m": distances.round(),
        }
    )
    addresses.loc[addresses["distance_m"] > max_distance_m, "address"] = None
    return addresses


if __name__ == "__main__":
    main(sys.argv[1:] or LAYERS)
