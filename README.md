# Where to open a café in central Moscow

Capstone project of the IBM Data Science Professional Certificate (Coursera, *Applied Data Science
Capstone*, "the Battle of the Neighbourhoods"). The data was collected in 2019; the analysis was
completed in 2026.

**Question:** which places within 6 km of Red Square have the footfall generators that usually
support many cafés (metro exits, shops, consumer services, parking, universities), yet host
noticeably fewer cafés and restaurants than comparable places?

![Opportunity map: red cells have fewer cafés and restaurants than expected, numbers mark the shortlist](report/figures/map_screenshot.jpg)

*Map tiles © OpenStreetMap contributors.*

## Findings

- The historic core is saturated: inside the Garden Ring every place already has as many cafés as
  its footfall generators suggest, or more.
- A Poisson model of competitor density explains 58% of the deviance under spatial
  cross-validation. Every kilometre from Red Square takes about 21% off the expected number of
  cafés and restaurants and every 100 m from the metro about 7%; twice as many shops or consumer
  services add about 13-14%.
- The under-served places lie 3.6-5.3 km from Red Square, next to metro stations. The most robust
  candidates are around **Savyolovskaya, Begovaya, Ploshchad Ilyicha, Krasnoselskaya and
  Proletarskaya**; the full top 10 and the caveats are in the report.

Read the [**report**](report/REPORT.md), or the analysis notebook itself:
[`notebooks/03_cafe_location_analysis.ipynb`](notebooks/03_cafe_location_analysis.ipynb)
(the interactive maps render on
[nbviewer](https://nbviewer.org/github/petro1eum/capstone/blob/master/notebooks/03_cafe_location_analysis.ipynb),
not on GitHub).

## Repository

| Path | Content |
|---|---|
| `notebooks/01_data_collection_moscow_open_data.ipynb` | 2019: candidate grid around Red Square, Moscow Open Data layers |
| `notebooks/02_foursquare_central_districts.ipynb` | 2019: Foursquare venues and k-means of the central districts (exploratory) |
| `notebooks/03_cafe_location_analysis.ipynb` | The analysis: features, typology, demand model, opportunity score, shortlist |
| `src/moscow_cafes/` | Data loaders, projection and neighbourhood counts, chain-name cleaning, Overpass client |
| `scripts/fetch_osm_data.py` | Refreshes the OpenStreetMap snapshot in `data/osm/` |
| `data/` | Moscow Open Data CSVs (2019) and the OpenStreetMap snapshot; see [`data/README.md`](data/README.md) |
| `report/` | Report, figures, interactive map, scores of all cells and the shortlist |
| `tests/` | Unit tests of the helpers and data checks |

## Running it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest                                    # helpers and data checks
jupyter lab notebooks/03_cafe_location_analysis.ipynb
python scripts/fetch_osm_data.py          # optional: replace the OpenStreetMap snapshot
```

The notebook runs offline on the committed data in about a minute and a half and rewrites the
figures, the interactive map and the CSV files in `report/`. Notebooks 01 and 02 are kept as they ran in 2019: their download links and the
Foursquare v2 API are gone, and the credentials they used were removed from the code.

## Data sources

- Moscow Open Data portal, [data.mos.ru](https://data.mos.ru) (2019 extracts).
- OpenStreetMap, © OpenStreetMap contributors, [ODbL](https://opendatacommons.org/licenses/odbl/).
- Yandex Geocoder (addresses of the grid cells, 2019).

The code is licensed under the GNU GPL v3, see [LICENSE](LICENSE).

## Кратко по-русски

Капстоун-проект курса IBM Data Science (Coursera): где в центре Москвы открыть кафе. Данные
собраны в 2019 году, анализ завершён в 2026-м.

- Центр в пределах 6 км от Красной площади покрыт сеткой из 364 шестиугольных ячеек. Для каждой
  посчитано, что находится в радиусе 300 м: кафе и рестораны (OpenStreetMap), выходы метро,
  остановки, парковки, магазины, бытовые услуги, фитнес и вузы (портал открытых данных Москвы и
  OpenStreetMap).
- Пуассоновская модель по «генераторам трафика» предсказывает, сколько кафе и ресторанов обычно
  бывает в таком месте. Она объясняет 58% девиансы на пространственной кросс-валидации. Каждый
  километр от центра уменьшает ожидаемое число заведений примерно на 21%, каждые 100 м до метро —
  на 7%.
- Недообеспеченные ячейки, где фактических конкурентов заметно меньше ожидаемого, ранжируются по
  стандартизованному разрыву, усреднённому по радиусам 250, 300 и 400 м.
- Исторический центр насыщен. Самые устойчивые кандидаты находятся у станций **Савёловская,
  Беговая, Площадь Ильича, Красносельская и Пролетарская**, в 3,5–5,5 км от Красной площади.

Подробности — в [отчёте](report/REPORT.md) (на английском).
