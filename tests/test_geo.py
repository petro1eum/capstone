import numpy as np
import pandas as pd
import pytest
from pyproj import Transformer

from moscow_cafes.geo import (
    GRID_CRS,
    RED_SQUARE,
    count_within,
    distance_from,
    grid_hexagons,
    nearest,
    to_latlon,
    to_xy,
)


def great_circle_m(lat1, lon1, lat2, lon2):
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((phi2 - phi1) / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6_371_008.8 * np.arcsin(np.sqrt(a))


def test_projected_distances_match_the_great_circle():
    # Sparrow Hills, about 6 km south-west of Red Square: zone 33 would be 2.4% off here.
    lat, lon = 55.7105, 37.5530
    projected = distance_from(pd.DataFrame({"lat": [lat], "lon": [lon]}), *RED_SQUARE)[0]
    assert projected == pytest.approx(great_circle_m(*RED_SQUARE, lat, lon), rel=3e-3)


def test_projection_round_trip():
    lat, lon = to_latlon(*to_xy(*RED_SQUARE))
    assert (float(lat), float(lon)) == pytest.approx(RED_SQUARE)


def test_count_within_counts_and_sums_weights():
    centers = np.array([[0.0, 0.0], [1000.0, 0.0]])
    points = np.array([[100.0, 0.0], [0.0, 250.0], [0.0, 400.0], [1000.0, 50.0]])
    assert list(count_within(centers, points, 300)) == [2, 1]
    assert list(count_within(centers, points, 300, weights=[1, 2, 4, 8])) == [3, 8]


def test_nearest_returns_distance_and_position():
    distances, positions = nearest(np.array([[0.0, 0.0]]), np.array([[5.0, 0.0], [3.0, 4.0], [0.0, 2.0]]))
    assert distances[0] == pytest.approx(2.0)
    assert positions[0] == 2


def test_neighbouring_grid_hexagons_share_an_edge():
    # Two centres 600 m apart along a row of the notebook 01 grid.
    to_grid = Transformer.from_crs("EPSG:4326", GRID_CRS, always_xy=True)
    from_grid = Transformer.from_crs(GRID_CRS, "EPSG:4326", always_xy=True)
    x, y = to_grid.transform(RED_SQUARE[1], RED_SQUARE[0])
    lon, lat = from_grid.transform(np.array([x, x + 600]), np.array([y, y]))
    hexagons = grid_hexagons(lat, lon)
    assert hexagons.shape == (2, 6, 2)
    np.testing.assert_allclose(hexagons[0, 0], hexagons[1, 2], atol=1e-9)
    np.testing.assert_allclose(hexagons[0, 5], hexagons[1, 3], atol=1e-9)
