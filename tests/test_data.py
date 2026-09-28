import numpy as np
import pandas as pd
from pyproj import Transformer

from moscow_cafes import data
from moscow_cafes.geo import GRID_CRS


def test_candidates_are_the_364_grid_cells():
    cells = data.load_candidates()
    assert len(cells) == 364
    assert not cells["address"].str.startswith("Russia").any()


def test_shops_are_counted_once_across_overlapping_subsets():
    shops = data.load_shops()
    assert shops.index.is_unique
    assert len(shops) == 22_109


def test_bus_stop_grid_coordinates_match_their_position():
    # df_bus2.csv used to carry the metro exits' Ys column.
    raw = pd.read_csv(data.MOS_DIR / "df_bus2.csv")
    to_grid = Transformer.from_crs("EPSG:4326", GRID_CRS, always_xy=True)
    x, y = to_grid.transform(raw["Longitude_WGS84"].to_numpy(), raw["Latitude_WGS84"].to_numpy())
    np.testing.assert_allclose(x, raw["Xs"], atol=0.01)
    np.testing.assert_allclose(y, raw["Ys"], atol=0.01)


def test_fitness_halls_are_merged_into_facilities():
    assert len(data.load_fitness()) == 385


def test_competitors_are_cafes_and_restaurants():
    catering = data.load_catering()
    assert set(catering.loc[catering["is_competitor"], "amenity"]) == {"cafe", "restaurant"}
    assert catering["chain"].notna().sum() >= catering["name"].notna().sum()
