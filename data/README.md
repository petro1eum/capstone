# Data

## `mos_open_data/`: Moscow Open Data, 2019

Saved in July-August 2019 from [data.mos.ru](https://data.mos.ru) datasets during the data
collection in [notebook 01](../notebooks/01_data_collection_moscow_open_data.ipynb) and in follow-up
work that split the shopping and services registers into categories. Every file has WGS84
coordinates (`Latitude_WGS84`, `Longitude_WGS84`, or `Latitude`/`Longitude` for the grid) and
metric coordinates (`Xs`/`Ys`, or `X`/`Y`) in **UTM zone 33**. Zone 33 is far from Moscow and
stretches distances by about 2.4%, so the analysis ignores the metric columns and re-projects the
WGS84 coordinates to UTM zone 37 (EPSG:32637).

| File | Records | Content |
|---|---:|---|
| `df_locations.csv` | 364 | Candidate locations: a hexagonal grid with 600 m between centres within 6 km of Red Square, with the address from the Yandex Geocoder |
| `df_subway2.csv` | 1,067 | Metro entrances and exits of 235 stations |
| `df_bus2.csv` | 11,507 | Surface public transport stops |
| `df_parking2.csv` | 9,254 | Paid street parking zones with their capacity (`CarCapacity`) |
| `df_services2.csv` | 14,540 | Consumer services: hairdressers, tailoring, repairs, photo studios, dry cleaning, pawnshops... |
| `df_haircut.csv`, `df_textile_rep.csv`, `df_foto.csv`, `df_complex.csv`, `df_shoes.csv`, `df_chemicals.csv`, `df_repair1.csv`, `df_pawnshop.csv` | | Subsets of `df_services2.csv` by type |
| `df_brandshops.csv`, `df_notbrandedclouth.csv` | 1,884 + 6,383 | Clothing shops, chain and independent |
| `df_brandproductshops.csv`, `df_notbrandproductshops.csv` | 1,256 + 5,125 | Food shops, chain and independent |
| `df_brandedgoods.csv`, `df_notbrandedgoods.csv` | 450 + 2,724 | General goods shops, chain and independent |
| `df_supermarkets.csv` | 2,982 | Supermarkets, universams, department stores, hypermarkets |
| `df_brandedsup2.csv` | 82 | Chain supermarkets (a subset of `df_supermarkets.csv`) |
| `df_brandedflowers.csv` | 238 | Chain flower shops |
| `df_network.csv` | 669 | Chain specialised non-food stores |
| `df_otherbrandedfood.csv` | 398 | Chain specialised food stores |
| `df_fitness3.csv` | 459 | Gym halls of sports centres and fitness clubs (several per facility) |
| `df_kino3.csv` | 14 | Municipal cinemas |

The shop files are subsets of the 60,320-shop register; their `Unnamed: 0` column is the row
number in that register, which identifies a shop across the overlapping subsets. Together they
hold 22,109 shops. The analysis now uses the full register from `dropbox_2019/` instead; a test
checks that every subset row points at the shop of the same name there.

Fixed in 2026:

- `df_bus2.csv` carried the `Ys` column of the metro table (1,067 values followed by empty cells);
  the column was recomputed from the stop coordinates.
- `df_othernotbrandedfood.csv` held exactly the rows of `df_notbrandedgoods.csv` under a food
  name and was removed.

## `dropbox_2019/`: the raw registers of 2019

The downloads that notebook 01 kept in the project's Dropbox, restored in September 2026 from a
local backup of that Dropbox (the commit message of `78118cf` lists the source paths, dates and
SHA-256 checksums). The large files are gzipped.

| File | Records | Content |
|---|---:|---|
| `restaurantsUTF.txt` | 15,366 | The catering register of data.mos.ru as JSON (UTF-8 with BOM): name, type (`TypeObject`), seats (`SeatsCount`), chain flag (`IsNetObject`), address, WGS84 coordinates |
| `df_cafe.csv` | 3,892 | The *кафе* and *ресторан* of the register within 6 km of Red Square, as selected in 2019 (distances in UTM zone 33) |
| `df_shops4.csv.gz` | 60,320 | The shopping register with type, chain flag and coordinates |
| `ShoppingUTF.json.gz` | 60,320 | The same register as downloaded, JSON |
| `EducationUTF.txt.gz` | 620 | Organisations of the city education department, mostly schools (534); not used |

## `osm/`: OpenStreetMap snapshot

Written by [`scripts/fetch_osm_data.py`](../scripts/fetch_osm_data.py) through the Overpass API;
`osm_meta.json` records the snapshot time and the queries. Objects within 7 km of Red Square;
ways and relations (buildings, campuses) are represented by their centre.

| File | Content |
|---|---|
| `osm_catering.csv` | `amenity` = cafe, restaurant, fast_food, bar, pub, biergarten, food_court, ice_cream |
| `osm_education.csv` | `amenity` = university, college |
| `osm_demand.csv` | The footfall layers of 2026, one row per object with its `layer`: entrances of metro, MCC and MCD stations (`railway` = subway_entrance, train_station_entrance) and the stations that name them; bus and tram stops; shops (`shop` = *, except vacant, kiosk and car_repair); consumer services (hairdressers, beauty salons, tailors, repairs, dry cleaning, pawnshops, photo studios, keys, watches, saunas: the categories of the 2019 register); gyms (`leisure` = fitness_centre). The tags are listed in `src/moscow_cafes/osm.py` |
| `osm_basemap.geojson` | The Moskva and Yauza rivers and the Boulevard, Garden and Third ring roads, for the report page |
| `osm_cell_addresses_ru.csv` | The nearest address point (street and house number) to each grid cell centre, within 250 m |

Columns of `osm_catering.csv` and `osm_education.csv`: `osm_type`, `osm_id`, `amenity`, `name`,
`brand`, `cuisine`, `lat`, `lon`; of `osm_demand.csv`: `osm_type`, `osm_id`, `layer`, `kind` (the
tag value), `station`, `name`, `lat`, `lon`. OpenStreetMap rarely records the capacity of street
parking, so the analysis keeps the parking layer of 2019 for 2026 as well.

OpenStreetMap data © OpenStreetMap contributors, available under the
[Open Database License](https://opendatacommons.org/licenses/odbl/).
