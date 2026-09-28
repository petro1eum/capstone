import pandas as pd
import pytest

from moscow_cafes.features import build_features
from moscow_cafes.geo import RED_SQUARE, to_latlon, to_xy

X0, Y0 = to_xy(*RED_SQUARE)


def points(*offsets_m, **columns):
    """Frame of points at (east, north) metre offsets from Red Square."""
    lat, lon = zip(*(to_latlon(X0 + dx, Y0 + dy) for dx, dy in offsets_m), strict=True)
    return pd.DataFrame({"lat": [float(v) for v in lat], "lon": [float(v) for v in lon], **columns})


def test_build_features_counts_each_layer_within_the_radius():
    cells = points((0, 0))
    catering = points(
        (100, 0), (0, 100), (-100, 0), (0, -100), (0, 1000), amenity=["cafe", "restaurant", "fast_food", "bar", "cafe"]
    )
    empty = points((5000, 5000))

    features = build_features(
        cells,
        catering=catering,
        metro=points((200, 0), (0, 350)),
        bus=points((0, 50)),
        parking=points((50, 50), (-50, 50), (0, 900), capacity=[5, 7, 100]),
        shops=points((10, 10), (20, 20)),
        services=empty,
        fitness=empty,
        education=points((0, 299)),
    ).iloc[0]

    assert features["cafes"] == 1
    assert features["competitors"] == 2
    assert features["fast_food"] == 1
    assert features["bars"] == 1
    assert features["metro_exits"] == 1
    assert features["metro_distance"] == pytest.approx(200, abs=0.01)
    assert features["bus_stops"] == 1
    assert features["parking_spaces"] == 12
    assert features["shops"] == 2
    assert features["services"] == 0
    assert features["education"] == 1
    assert features["center_distance"] == pytest.approx(0, abs=0.01)
