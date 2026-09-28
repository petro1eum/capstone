"""Coordinate helpers: a metric projection for Moscow and neighbourhood queries."""

import numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree

# Red Square as geocoded with Nominatim in notebook 01, (latitude, longitude).
RED_SQUARE = (55.7536532, 37.6213676671642)

# Moscow lies in UTM zone 37N (36°E-42°E). Notebook 01 used zone 33, whose central
# meridian (15°E) is 22.6° away from Moscow: there every distance comes out ~2.4% too long.
MOSCOW_CRS = "EPSG:32637"

_TO_METRIC = Transformer.from_crs("EPSG:4326", MOSCOW_CRS, always_xy=True)
_TO_WGS84 = Transformer.from_crs(MOSCOW_CRS, "EPSG:4326", always_xy=True)


def to_xy(lat, lon):
    """Project WGS84 latitude/longitude (scalars or arrays) to UTM 37N metres."""
    return _TO_METRIC.transform(np.asarray(lon, dtype=float), np.asarray(lat, dtype=float))


def to_latlon(x, y):
    """Inverse of `to_xy`: UTM 37N metres to WGS84 (latitude, longitude)."""
    lon, lat = _TO_WGS84.transform(np.asarray(x, dtype=float), np.asarray(y, dtype=float))
    return lat, lon


def xy_array(df):
    """Stack the `lat`/`lon` columns of a frame into an (n, 2) array of metric coordinates."""
    x, y = to_xy(df["lat"].to_numpy(), df["lon"].to_numpy())
    return np.column_stack([x, y])


def distance_from(df, lat, lon):
    """Distance in metres from every row of `df` to the point (lat, lon)."""
    x0, y0 = to_xy(lat, lon)
    xy = xy_array(df)
    return np.hypot(xy[:, 0] - x0, xy[:, 1] - y0)


def count_within(centers, points, radius, weights=None):
    """For every centre, count the points (or sum their `weights`) closer than `radius` metres.

    `centers` and `points` are (n, 2) arrays of metric coordinates.
    """
    tree = cKDTree(points)
    if weights is None:
        return tree.query_ball_point(centers, r=radius, return_length=True)
    weights = np.asarray(weights, dtype=float)
    neighbours = tree.query_ball_point(centers, r=radius)
    return np.array([weights[idx].sum() for idx in neighbours])


def nearest(centers, points):
    """Distance in metres from every centre to its nearest point, and that point's position."""
    return cKDTree(points).query(centers, k=1)


# Notebook 01 laid the candidate grid out in UTM zone 33 with 600 m between neighbouring
# centres; the hexagons are regular only in that projection (in Moscow its grid north is
# turned by ~18° from true north, and so is the grid).
GRID_CRS = "+proj=utm +zone=33 +datum=WGS84 +units=m +no_defs"
GRID_SPACING_M = 600

_TO_GRID = Transformer.from_crs("EPSG:4326", GRID_CRS, always_xy=True)
_FROM_GRID = Transformer.from_crs(GRID_CRS, "EPSG:4326", always_xy=True)


def grid_hexagons(lat, lon, spacing=GRID_SPACING_M):
    """(latitude, longitude) vertices of the grid hexagon around every centre, shape (n, 6, 2)."""
    x, y = _TO_GRID.transform(np.asarray(lon, dtype=float), np.asarray(lat, dtype=float))
    size = spacing / np.sqrt(3)  # circumradius of a pointy-top hexagon
    angles = np.radians(30 + 60 * np.arange(6))
    vertex_lon, vertex_lat = _FROM_GRID.transform(
        x[:, None] + size * np.cos(angles), y[:, None] + size * np.sin(angles)
    )
    return np.stack([vertex_lat, vertex_lon], axis=-1)
