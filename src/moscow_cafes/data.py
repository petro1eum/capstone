"""Loaders for the project datasets.

Every loader returns a DataFrame with WGS84 `lat`/`lon` columns plus the attributes the
analysis needs. The `Xs`/`Ys` columns stored in the CSV files are ignored: they were
computed in UTM zone 33 (`geo.GRID_CRS`), which distorts distances in Moscow, so the WGS84
coordinates are re-projected to `geo.MOSCOW_CRS` instead.
"""

from pathlib import Path

import pandas as pd

from .names import normalize_chain_name

ROOT = Path(__file__).resolve().parents[2]
MOS_DIR = ROOT / "data" / "mos_open_data"
OSM_DIR = ROOT / "data" / "osm"

# Subsets of the data.mos.ru shopping register (60,320 shops) saved during the 2019 work;
# together they cover clothing, food, general goods, supermarkets and the branded part of
# flowers and specialised stores. df_brandedsup2 is a subset of df_supermarkets.
SHOP_FILES = (
    "df_brandshops.csv",
    "df_notbrandedclouth.csv",
    "df_brandproductshops.csv",
    "df_notbrandproductshops.csv",
    "df_brandedgoods.csv",
    "df_notbrandedgoods.csv",
    "df_supermarkets.csv",
    "df_brandedsup2.csv",
    "df_brandedflowers.csv",
    "df_network.csv",
    "df_otherbrandedfood.csv",
)

# Types of the data.mos.ru catering register kept in notebook 01 as direct competitors.
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
    """Shops from the saved subsets of the shopping register, one row per shop (data.mos.ru, 2019).

    The `Unnamed: 0` column is the row number in the full register (its saved index), so it
    identifies a shop across the overlapping subsets.
    """
    frames = [pd.read_csv(MOS_DIR / filename, index_col="Unnamed: 0") for filename in SHOP_FILES]
    df = pd.concat(frames)
    df = df[~df.index.duplicated()].sort_index()
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
    """Cafés, restaurants, fast food and bars from the OpenStreetMap snapshot in data/osm/.

    `chain` is the brand tag or, failing that, the name, normalised with the chain rules.
    """
    df = pd.read_csv(OSM_DIR / "osm_catering.csv")
    df["chain"] = df["brand"].fillna(df["name"]).map(normalize_chain_name)
    df["is_competitor"] = df["amenity"].isin(COMPETITOR_AMENITIES)
    return df


def load_education():
    """Universities and colleges from the OpenStreetMap snapshot in data/osm/."""
    return pd.read_csv(OSM_DIR / "osm_education.csv")
