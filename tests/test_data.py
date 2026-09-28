import numpy as np
import pandas as pd
from pyproj import Transformer

from moscow_cafes import data
from moscow_cafes.geo import GRID_CRS


def test_candidates_are_the_364_grid_cells():
    cells = data.load_candidates()
    assert len(cells) == 364
    assert not cells["address"].str.startswith("Russia").any()


SHOP_SUBSETS = [
    "df_brandshops.csv", "df_notbrandedclouth.csv", "df_brandproductshops.csv", "df_notbrandproductshops.csv",
    "df_brandedgoods.csv", "df_notbrandedgoods.csv", "df_supermarkets.csv", "df_brandedsup2.csv",
    "df_brandedflowers.csv", "df_network.csv", "df_otherbrandedfood.csv",
]


def test_shops_are_the_whole_register():
    shops = data.load_shops()
    assert shops.index.is_unique
    assert len(shops) == 60_320


def test_shop_subsets_of_2019_are_rows_of_the_restored_register():
    # The category files of 2019 keep the register row number in `Unnamed: 0`.
    shops = data.load_shops()
    subsets = pd.concat(pd.read_csv(data.MOS_DIR / name, usecols=["Unnamed: 0", "Name"]) for name in SHOP_SUBSETS)
    subsets = subsets.drop_duplicates("Unnamed: 0").set_index("Unnamed: 0")
    assert len(subsets) == 22_109
    assert (shops.loc[subsets.index, "name"] == subsets["Name"]).all()


def test_bus_stop_grid_coordinates_match_their_position():
    # df_bus2.csv used to carry the metro exits' Ys column.
    raw = pd.read_csv(data.MOS_DIR / "df_bus2.csv")
    to_grid = Transformer.from_crs("EPSG:4326", GRID_CRS, always_xy=True)
    x, y = to_grid.transform(raw["Longitude_WGS84"].to_numpy(), raw["Latitude_WGS84"].to_numpy())
    np.testing.assert_allclose(x, raw["Xs"], atol=0.01)
    np.testing.assert_allclose(y, raw["Ys"], atol=0.01)


def test_fitness_halls_are_merged_into_facilities():
    assert len(data.load_fitness()) == 385


def test_catering_register_types_are_all_mapped():
    catering = data.load_catering()
    assert len(catering) == 15_366
    assert catering["amenity"].notna().all()
    assert catering[["lat", "lon"]].notna().all().all()


def test_competitors_are_cafes_and_restaurants():
    for catering in (data.load_catering(), data.load_osm_catering()):
        assert set(catering.loc[catering["is_competitor"], "amenity"]) == {"cafe", "restaurant"}
        assert catering["chain"].notna().sum() >= catering["name"].notna().sum()


def test_osm_demand_layers_match_the_arguments_of_build_features():
    layers = data.load_osm_demand()
    assert set(layers) == {"metro", "bus", "shops", "services", "fitness"}
    assert all(len(frame) > 100 and frame[["lat", "lon"]].notna().all().all() for frame in layers.values())
    assert layers["metro"]["station"].notna().all()
