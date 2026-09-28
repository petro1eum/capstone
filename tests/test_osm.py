import pytest

from moscow_cafes.osm import (
    bbox_around,
    build_address_query,
    build_query,
    elements_to_frame,
    lines_to_geojson,
)


def test_bbox_contains_the_circle():
    south, west, north, east = bbox_around(55.75, 37.62, 7000)
    assert (north - south) * 111_320 == pytest.approx(14_000, rel=1e-3)
    assert south < 55.75 < north
    assert west < 37.62 < east


def test_queries_filter_the_box():
    bbox = (55.69, 37.51, 55.82, 37.73)
    assert 'nwr["amenity"~"^(cafe|restaurant)$"](55.69,37.51,55.82,37.73);' in build_query(("cafe", "restaurant"), bbox)
    address_query = build_address_query(bbox)
    assert address_query.startswith("[out:csv(")
    assert '["addr:street"]["addr:housenumber"](55.69,37.51,55.82,37.73)' in address_query


def test_elements_to_frame_uses_the_centre_of_ways():
    payload = {
        "elements": [
            {"type": "node", "id": 1, "lat": 55.7, "lon": 37.6, "tags": {"amenity": "cafe", "name": "A"}},
            {"type": "way", "id": 2, "center": {"lat": 55.8, "lon": 37.7}, "tags": {"amenity": "restaurant"}},
            {"type": "relation", "id": 3, "tags": {"amenity": "cafe"}},  # no centre: skipped
        ]
    }
    frame = elements_to_frame(payload)
    assert frame["osm_id"].tolist() == [1, 2]
    assert frame.loc[1, ["lat", "lon"]].tolist() == [55.8, 37.7]
    assert frame.loc[0, "name"] == "A"


def test_lines_to_geojson_splits_ring_relations_into_member_ways():
    line = [{"lat": 55.70, "lon": 37.60}, {"lat": 55.71, "lon": 37.61}]
    payload = {
        "elements": [
            {"type": "way", "id": 1, "tags": {"name": "Яуза"}, "geometry": line},
            {
                "type": "relation",
                "id": 2,
                "tags": {"name": "Садовое кольцо"},
                "members": [{"geometry": line}, {"geometry": line[:1]}],  # a one-point member is dropped
            },
        ]
    }
    features = lines_to_geojson(payload)["features"]
    assert [f["properties"]["kind"] for f in features] == ["river", "ring"]
    assert features[1]["properties"]["name"] == "Садовое кольцо"
    assert features[0]["geometry"]["coordinates"][0] == [37.6, 55.7]
