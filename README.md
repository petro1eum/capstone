# Where to open a café in central Moscow

Capstone project of the IBM Data Science Professional Certificate (Coursera, *Applied Data Science
Capstone*), started in 2019 and finished in 2026. [По-русски ниже](#по-русски).

Central Moscow within 6 km of Red Square is divided into 364 hexagonal areas about 600 m across. For
each area we count the cafés and restaurants within a five-minute walk (300 m) and everything that
brings people there: metro exits, shops, hairdressers and repair shops, bus stops. Comparing the
areas, a model learns how many cafés a place with such surroundings usually has. Where there are
markedly fewer cafés than usual, a new café would get the same footfall with fewer competitors.

![Map of central Moscow: red areas have fewer cafés than usual for their surroundings, blue areas more; numbers mark the ten places for 2026](report/figures/map_screenshot.jpg)

*Red: fewer cafés than usual for such surroundings; blue: more. Numbers mark the ten places for
2026. Map tiles © OpenStreetMap contributors.*

## Results

- **The historic centre is taken.** Inside the Garden Ring there are as many cafés as the metro and
  the shops suggest, or more. The gaps lie next to metro stations 3-5 km from Red Square.
- **What brings cafés.** Each kilometre from Red Square takes about 22% off the usual number of
  cafés, each 100 m from the metro about 4.5%; twice as many shops add 26%, twice as many consumer
  services 18%. The surroundings explain two thirds of the differences between areas.
- **Seven years later.** Where cafés were most lacking in 2019, there were 69% more by 2026; where
  they were in surplus, 11% fewer. The pandemic, the war and sanctions and the exit of foreign chains
  moved cafés the same way on their own, so this supports the method without proving it.
- **Ten places for 2026.** Built on 2026 data from OpenStreetMap, the most robust candidates are
  near Kutuzovskaya, Maryina Roshcha and Savyolovskaya; new gaps have opened next to stations built
  since 2019 (Lefortovo on the Big Circle Line, Mitkovo on the MCD).

## Read more

| | |
|---|---|
| [Report](report/REPORT.md) | The full analysis: data, method, results, caveats |
| [Отчёт](report/REPORT.ru.md) | The same report in Russian |
| [`report/report_ru.html`](report/report_ru.html) | A Russian page with an interactive map; download it and open it in a browser |
| [Notebook 03](notebooks/03_cafe_location_analysis.ipynb) | The code behind every number ([nbviewer](https://nbviewer.org/github/petro1eum/capstone/blob/master/notebooks/03_cafe_location_analysis.ipynb) shows its interactive maps) |

## Repository

| Path | Content |
|---|---|
| `notebooks/01_data_collection_moscow_open_data.ipynb` | 2019: the grid of areas around Red Square and the Moscow Open Data layers |
| `notebooks/02_foursquare_central_districts.ipynb` | 2019: Foursquare venues of the central districts (exploratory) |
| `notebooks/03_cafe_location_analysis.ipynb` | The analysis: features, typology, demand model, the 2019 shortlist, the check against 2026, the 2026 shortlist |
| `src/moscow_cafes/` | Data loaders, projection and neighbourhood counts, chain-name cleaning, OpenStreetMap client |
| `scripts/fetch_osm_data.py` | Refreshes the OpenStreetMap snapshot in `data/osm/` |
| `scripts/build_report_page.py`, `scripts/report_page/` | Build `report/report_ru.html` from the notebook's outputs |
| `data/` | Moscow Open Data of 2019 and the OpenStreetMap snapshot of 2026; see [`data/README.md`](data/README.md) |
| `report/` | Reports, figures, interactive maps, the scores of all areas and both shortlists |
| `tests/` | Tests of the helpers and checks of the data |

## Running it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest                                    # helpers and data checks
jupyter lab notebooks/03_cafe_location_analysis.ipynb
python scripts/build_report_page.py       # the Russian page, after the notebook
python scripts/fetch_osm_data.py          # optional: replace the OpenStreetMap snapshot
```

The notebook runs offline on the committed data in a few minutes and rewrites the figures, the
interactive map and the CSV files in `report/`. Notebooks 01 and 02 are kept as they ran in 2019:
their download links and the Foursquare v2 API are gone, and the credentials they used were removed
from the code.

## Data and license

- Moscow Open Data portal, [data.mos.ru](https://data.mos.ru): extracts of 2019; the catering and
  shopping registers were restored from the project's 2019 Dropbox.
- OpenStreetMap, © OpenStreetMap contributors, [ODbL](https://opendatacommons.org/licenses/odbl/):
  a snapshot of 28 September 2026.
- Yandex Geocoder: addresses of the grid areas, 2019.

The code is licensed under the GNU GPL v3, see [LICENSE](LICENSE).

## По-русски

**Где открыть кафе в центре Москвы.** Выпускной проект курса IBM Data Science (Coursera): начат
в 2019 году, закончен в 2026-м.

Центр Москвы в радиусе 6 км от Красной площади разбит на 364 участка по 600 м. Для каждого посчитано,
сколько в пяти минутах ходьбы кафе и ресторанов и сколько того, что приводит туда людей: выходов метро,
магазинов, парикмахерских и мастерских, остановок. Сравнивая участки, модель узнаёт, сколько кафе
обычно бывает при таком окружении. Где кафе заметно меньше обычного, новое кафе получит тот же поток
людей при меньшем числе конкурентов.

- **Исторический центр занят.** Внутри Садового кольца кафе столько, сколько обещают метро и магазины,
  или больше. Свободные места лежат у станций метро в 3–5 км от Красной площади.
- **Что влияет на число кафе.** Каждый километр от Красной площади уменьшает его примерно на 22%,
  каждые 100 м до метро на 4,5%; вдвое больше магазинов прибавляет 26%.
- **Проверка временем.** Там, где в 2019 году кафе не хватало, к 2026 году их стало на 69% больше,
  где был избыток, на 11% меньше. Пандемия, война, санкции и уход иностранных сетей сами двигали кафе
  в ту же сторону, так что это подкрепляет метод, но не доказывает его.
- **Десять мест на 2026 год.** Самые надёжные находятся у станций Кутузовская, Марьина Роща
  и Савёловская, а новые ниши появились у станций, открытых после 2019 года (Лефортово, Митьково).

Подробно: [отчёт на русском](report/REPORT.ru.md) и страница с интерактивной картой
[`report/report_ru.html`](report/report_ru.html) (скачайте и откройте в браузере).
