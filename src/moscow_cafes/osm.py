"""Download points of interest from OpenStreetMap through the Overpass API."""

import math
import time

import numpy as np
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
# Landmarks drawn under the grid on the report page.
BASEMAP_RIVERS = ("Москва", "Яуза")
BASEMAP_RINGS = ("Бульварное кольцо", "Садовое кольцо", "Третье транспортное кольцо")

TAG_COLUMNS = ("amenity", "name", "brand", "cuisine")

# The footfall layers of 2026, with the tags closest to the Moscow registers of 2019. Consumer
# services follow the categories of the 2019 services register (hairdressers and beauty salons,
# tailors, photo studios, repairs, dry cleaning, pawnshops, keys, watches, saunas); every other shop
# is retail, except empty premises, street kiosks and car repair.
RAIL_ENTRANCES = ("subway_entrance", "train_station_entrance")
SERVICE_SHOPS = (
    "hairdresser", "beauty", "massage", "tattoo", "tailor", "dry_cleaning", "laundry", "shoe_repair", "pawnbroker",
    "repair", "photo", "photo_studio", "copyshop", "locksmith", "funeral_directors",
)
SERVICE_CRAFTS = (
    "electronics_repair", "photographer", "photographic_laboratory", "key_cutter", "tailor", "dressmaker",
    "shoemaker", "jeweller", "clockmaker", "watchmaker", "locksmith", "atelier",
)
NOT_SHOPS = ("vacant", "kiosk", "car_repair")
DEMAND_TAGS = ("railway", "highway", "shop", "craft", "leisure", "amenity", "station", "name")


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


def build_basemap_query(bbox, timeout_s=120):
    """Overpass QL for the rivers and the ring roads inside `bbox`, with their geometry."""
    south, west, north, east = bbox
    box = f"({south},{west},{north},{east})"
    return (
        f"[out:json][timeout:{timeout_s}];("
        f'way["waterway"="river"]["name"~"^({"|".join(BASEMAP_RIVERS)})$"]{box};'
        f'relation["type"="route"]["route"="road"]["name"~"^({"|".join(BASEMAP_RINGS)})$"]{box};'
        ");out geom;"
    )


def build_address_query(bbox, timeout_s=180):
    """Overpass QL listing every object with a street address inside `bbox` as tab-separated text."""
    south, west, north, east = bbox
    return (
        f'[out:csv(::lat,::lon,"addr:street","addr:housenumber";false;"\\t")][timeout:{timeout_s}];'
        f'nwr["addr:street"]["addr:housenumber"]({south},{west},{north},{east});out center;'
    )


def build_demand_query(bbox, timeout_s=600):
    """Overpass QL for the footfall layers inside `bbox` (see `classify_demand`) as tab-separated text."""
    south, west, north, east = bbox
    box = f"({south},{west},{north},{east})"
    columns = ",".join(["::type", "::id", "::lat", "::lon", *(f'"{tag}"' for tag in DEMAND_TAGS)])
    return (
        f'[out:csv({columns};true;"\\t")][timeout:{timeout_s}];('
        f'node["railway"~"^({"|".join(RAIL_ENTRANCES)})$"]{box};'
        f'nwr["railway"~"^(station|halt)$"]{box};'
        f'node["highway"="bus_stop"]{box};node["railway"="tram_stop"]{box};'
        f'nwr["shop"]{box};nwr["craft"]{box};'
        f'nwr["leisure"~"^(fitness_centre|sauna)$"]{box};nwr["amenity"="public_bath"]{box};'
        ");out center;"
    )


def classify_demand(frame):
    """The footfall layer of every object of a `build_demand_query` answer (missing if none).

    rail_entrance: entrances of metro, MCC and MCD stations; station: the stations themselves,
    which name the entrances; stop: bus, trolleybus and tram stops; service; shop; fitness: gyms.
    """
    shop, craft = frame["shop"], frame["craft"]
    service = (
        shop.isin(SERVICE_SHOPS)
        | craft.isin(SERVICE_CRAFTS)
        | frame["leisure"].eq("sauna")
        | frame["amenity"].eq("public_bath")
    )
    conditions = [
        frame["railway"].isin(RAIL_ENTRANCES),
        frame["railway"].isin(["station", "halt"]),
        frame["highway"].eq("bus_stop") | frame["railway"].eq("tram_stop"),
        service,
        shop.notna() & ~shop.isin(NOT_SHOPS),
        frame["leisure"].eq("fitness_centre"),
    ]
    names = ["rail_entrance", "station", "stop", "service", "shop", "fitness"]
    return pd.Series(np.select(conditions, names, default=None), index=frame.index, name="layer")


def run_query(query, endpoints=OVERPASS_ENDPOINTS, attempts=3, as_json=True):
    """POST `query` to the first endpoint that answers; returns the decoded JSON payload (or the text)."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    errors = []
    for endpoint in endpoints:
        for attempt in range(attempts):
            try:
                response = requests.post(endpoint, data={"data": query}, headers=headers, timeout=300)
                response.raise_for_status()
                return response.json() if as_json else response.content.decode("utf-8")  # CSV comes without a charset
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


def lines_to_geojson(payload):
    """River ways and the member ways of ring-road relations as GeoJSON line features."""
    features = []
    for element in payload["elements"]:
        if element["type"] == "way":
            kind, parts = "river", [element.get("geometry", [])]
        else:
            kind, parts = "ring", [member.get("geometry", []) for member in element["members"]]
        name = element.get("tags", {}).get("name")
        for part in parts:
            if len(part) < 2:
                continue
            coordinates = [[round(point["lon"], 6), round(point["lat"], 6)] for point in part]
            features.append(
                {
                    "type": "Feature",
                    "properties": {"name": name, "kind": kind},
                    "geometry": {"type": "LineString", "coordinates": coordinates},
                }
            )
    return {"type": "FeatureCollection", "features": features}

