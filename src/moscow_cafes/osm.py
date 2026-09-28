"""Download points of interest from OpenStreetMap through the Overpass API."""

import math
import time

import pandas as pd
import requests

OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)
# overpass-api.de answers "406 Not Acceptable" to requests without a descriptive User-Agent.
USER_AGENT = "moscow-cafe-capstone/1.0 (+https://github.com/petro1eum/capstone)"

CATERING_AMENITIES = ("cafe", "restaurant", "fast_food", "bar", "pub", "biergarten", "food_court", "ice_cream")
EDUCATION_AMENITIES = ("university", "college")

TAG_COLUMNS = ("amenity", "name", "brand", "cuisine")


def bbox_around(lat, lon, radius_m):
    """(south, west, north, east) box that contains the circle of `radius_m` metres around a point."""
    dlat = radius_m / 111_320
    dlon = radius_m / (111_320 * math.cos(math.radians(lat)))
    return round(lat - dlat, 5), round(lon - dlon, 5), round(lat + dlat, 5), round(lon + dlon, 5)


def build_query(amenities, bbox, timeout_s=180):
    """Overpass QL for every node, way and relation with one of `amenities` inside `bbox`.

    A bounding box is much cheaper for Overpass than an `around` filter, which times out
    on a 7 km radius.
    """
    pattern = "|".join(amenities)
    south, west, north, east = bbox
    return (
        f"[out:json][timeout:{timeout_s}];"
        f'nwr["amenity"~"^({pattern})$"]({south},{west},{north},{east});'
        "out center tags;"
    )


def run_query(query, endpoints=OVERPASS_ENDPOINTS, attempts=3):
    """POST `query` to the first endpoint that answers; returns the decoded JSON payload."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    errors = []
    for endpoint in endpoints:
        for attempt in range(attempts):
            try:
                response = requests.post(endpoint, data={"data": query}, headers=headers, timeout=300)
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                errors.append(f"{endpoint}: {exc}")
                time.sleep(10 * (attempt + 1))
    raise RuntimeError("All Overpass endpoints failed:\n" + "\n".join(errors))


def elements_to_frame(payload):
    """Flatten Overpass elements into one row per object; ways and relations get their centre."""
    rows = []
    for element in payload["elements"]:
        point = element if element["type"] == "node" else element.get("center")
        if point is None:
            continue
        tags = element.get("tags", {})
        row = {"osm_type": element["type"], "osm_id": element["id"]}
        row.update({tag: tags.get(tag) for tag in TAG_COLUMNS})
        row.update({"lat": point["lat"], "lon": point["lon"]})
        rows.append(row)
    return pd.DataFrame(rows, columns=["osm_type", "osm_id", *TAG_COLUMNS, "lat", "lon"])
