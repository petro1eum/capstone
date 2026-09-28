"""Loaders for the project datasets.

Every loader returns a DataFrame with WGS84 `lat`/`lon` columns plus the attributes the
analysis needs. The `Xs`/`Ys` columns stored in the CSV files are ignored: they were
computed in UTM zone 33 (`geo.GRID_CRS`), which distorts distances in Moscow, so the WGS84
coordinates are re-projected to `geo.MOSCOW_CRS` instead.
"""

import json
from pathlib import Path

import pandas as pd

from .names import normalize_chain_name

ROOT = Path(__file__).resolve().parents[2]
MOS_DIR = ROOT / "data" / "mos_open_data"
REGISTER_DIR = ROOT / "data" / "dropbox_2019"
OSM_DIR = ROOT / "data" / "osm"

# Types of the data.mos.ru catering register. Notebook 01 kept кафе and ресторан as the
# direct competitors; the other quick-service and drinking places are described separately.
CATERING_TYPES = {
    "кафе": "cafe",
    "ресторан": "restaurant",
    "предприятие быстрого обслуживания": "fast_food",
    "закусочная": "fast_food",
    "бар": "bar",
    "столовая": "other",
    "буфет": "other",
    "кафетерий": "other",
    "магазин (отдел кулинарии)": "other",
}
COMPETITOR_AMENITIES = ("cafe", "restaurant")


def _read_mos(filename):
    return pd.read_csv(MOS_DIR / filename, index_col=0)


def load_candidates():
    """364 candidate locations: a hexagonal grid within 6 km of Red Square built in notebook 01."""
    df = _read_mos("df_locations.csv")
    address = df["Address"].str.replace(r"^Russia, Moscow, ", "", regex=True)
    return pd.DataFrame({"address": address, "lat": df["Latitude"], "lon": df["Longitude"]}).rename_axis("cell_id")


def load_metro_exits():
    """Metro entrances/exits (data.mos.ru, 2019)."""
    df = _read_mos("df_subway2.csv")
    return pd.DataFrame(
        {"station": df["NameOfStation"], "name": df["Name"], "lat": df["Latitude_WGS84"], "lon": df["Longitude_WGS84"]}
    )


def load_bus_stops():
    """Surface public transport stops (data.mos.ru, 2019)."""
    df = _read_mos("df_bus2.csv")
    return pd.DataFrame({"name": df["Name"], "lat": df["Latitude_WGS84"], "lon": df["Longitude_WGS84"]})


def load_parking():
    """Paid street parking zones with their capacity in cars (data.mos.ru, 2019)."""
    df = _read_mos("df_parking2.csv")
    return pd.DataFrame(
        {
            "name": df["ParkingName"],
            "capacity": df["CarCapacity"],
            "lat": df["Latitude_WGS84"],
            "lon": df["Longitude_WGS84"],
        }
    )


def load_shops():
    """The shopping register of data.mos.ru, all 60,320 shops (2019)."""
    df = pd.read_csv(REGISTER_DIR / "df_shops4.csv.gz", index_col=0)
    return pd.DataFrame(
        {
            "name": df["Name"],
            "type": df["TypeObject"],
            "is_chain": df["IsNetObject"].eq("да"),
            "lat": df["Latitude_WGS84"],
            "lon": df["Longitude_WGS84"],
        }
    ).rename_axis("register_row")


def load_services():
    """Consumer services: hairdressers, dry cleaning, repairs, photo studios... (data.mos.ru, 2019)."""
    df = _read_mos("df_services2.csv")
    return pd.DataFrame(
        {"name": df["Name"], "type": df["TypeObject"], "lat": df["Latitude_WGS84"], "lon": df["Longitude_WGS84"]}
    )


def load_fitness():
    """Fitness clubs and sports centres with a gym (data.mos.ru, 2019).

    The register lists gym halls, several per club, so halls are merged into facilities.
    """
    df = _read_mos("df_fitness3.csv").drop_duplicates(["ObjectName", "Address"])
    return pd.DataFrame({"name": df["ObjectName"], "lat": df["Latitude_WGS84"], "lon": df["Longitude_WGS84"]})


def load_catering():
    """The catering register of data.mos.ru, 15,366 venues with type, seats and chain flag (2019).

    `amenity` puts the register types into the categories of `CATERING_TYPES`; `chain` is the
    name normalised with the chain rules.
    """
    df = pd.DataFrame(json.loads((REGISTER_DIR / "restaurantsUTF.txt").read_text(encoding="utf-8-sig")))
    amenity = df["TypeObject"].map(CATERING_TYPES)
    return pd.DataFrame(
        {
            "name": df["Name"],
            "type": df["TypeObject"],
            "amenity": amenity,
            "is_competitor": amenity.isin(COMPETITOR_AMENITIES),
            "is_chain": df["IsNetObject"].eq("да"),
            "chain": df["Name"].map(normalize_chain_name),
            "seats": pd.to_numeric(df["SeatsCount"], errors="coerce"),
            "lat": pd.to_numeric(df["Latitude_WGS84"]),
            "lon": pd.to_numeric(df["Longitude_WGS84"]),
        }
    )


def load_osm_catering():
    """Cafés, restaurants, fast food and bars from the OpenStreetMap snapshot in data/osm/ (2026).

    `chain` is the brand tag or, failing that, the name, normalised with the chain rules.
    """
    df = pd.read_csv(OSM_DIR / "osm_catering.csv")
    df["chain"] = df["brand"].fillna(df["name"]).map(normalize_chain_name)
    df["is_competitor"] = df["amenity"].isin(COMPETITOR_AMENITIES)
    return df


def load_education():
    """Universities and colleges from the OpenStreetMap snapshot in data/osm/."""
    return pd.read_csv(OSM_DIR / "osm_education.csv")
