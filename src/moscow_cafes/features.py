"""Per-location features: what surrounds every candidate café site."""

import pandas as pd

from .geo import RED_SQUARE, count_within, distance_from, nearest, xy_array

# The catchment drawn around every candidate in notebook 01: a straight-line radius, not a walking isochrone.
RADIUS_M = 300


def build_features(cells, catering, metro, bus, parking, shops, services, fitness, education, radius=RADIUS_M):
    """Count the objects of every layer within `radius` metres of each cell (one row per cell).

    All frames need `lat`/`lon` columns; `catering` also needs `amenity` and `parking`
    needs `capacity`, which is summed instead of counted.
    """
    centers = xy_array(cells)

    def count(points):
        return count_within(centers, xy_array(points), radius)

    amenity = catering["amenity"]
    features = pd.DataFrame(index=cells.index)
    features["cafes"] = count(catering[amenity == "cafe"])
    features["restaurants"] = count(catering[amenity == "restaurant"])
    features["competitors"] = features["cafes"] + features["restaurants"]
    features["fast_food"] = count(catering[amenity.isin(["fast_food", "food_court"])])
    features["bars"] = count(catering[amenity.isin(["bar", "pub", "biergarten"])])
    features["metro_exits"] = count(metro)
    features["metro_distance"], _ = nearest(centers, xy_array(metro))
    features["bus_stops"] = count(bus)
    features["parking_spaces"] = count_within(centers, xy_array(parking), radius, weights=parking["capacity"])
    features["shops"] = count(shops)
    features["services"] = count(services)
    features["fitness"] = count(fitness)
    features["education"] = count(education)
    features["center_distance"] = distance_from(cells, *RED_SQUARE)
    return features
