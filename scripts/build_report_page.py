"""Build the Russian report page from the outputs of notebook 03.

    python scripts/build_report_page.py                   # report/report_ru.html, a standalone page
    python scripts/build_report_page.py --fragment PATH   # the same page without <html>/<head>/<body>

Inputs: report/summary.json, report/cell_scores.csv and report/shortlist_{2019,2026}.csv (written
by the notebook), data/osm/osm_basemap.geojson and data/osm/osm_cell_addresses_ru.csv (written by
scripts/fetch_osm_data.py) and the data layers themselves, for the record counts. The page's text,
style and script are in scripts/report_page/: template.html, style.css and script.js.
"""

import argparse
import json
import sys
from html import escape
from pathlib import Path
from string import Template

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from moscow_cafes import data  # noqa: E402
from moscow_cafes.geo import RED_SQUARE, grid_hexagons, to_xy  # noqa: E402

PAGE = Path(__file__).resolve().parent / "report_page"
REPORT = ROOT / "report"
OSM = ROOT / "data" / "osm"
EXTENT_KM = 6.6
YEARS = (2019, 2026)
RADII = (250, 300, 400)
METRO_FILTER_M = 500  # the shortlist wants a station entrance this close

TYPES_RU = {
    "Transit hubs": "Транспортные узлы",
    "Central neighbourhoods": "Центральные кварталы",
    "Residential belt": "Жилой пояс",
    "Parks, rail and industrial land": "Парки, железные дороги и промзоны",
}
EFFECTS_RU = {
    "center_distance_km": "На 1 км дальше от Красной площади",
    "metro_distance_km": "На 100 м дальше от выхода метро",
    "shops": "Магазины",
    "services": "Бытовые услуги",
    "parking_spaces": "Парковочные места",
    "metro_exits": "Выходы метро",
    "education": "Вузы и колледжи",
    "bus_stops": "Остановки",
    "fitness": "Спортзалы",
}
MODELS_RU = {
    "Poisson GLM, log1p distances": "Пуассоновская регрессия, log1p расстояний",
    "Poisson GLM, linear distances": "Пуассоновская регрессия, линейные расстояния",
    "Gradient boosting, Poisson loss": "Градиентный бустинг с пуассоновской функцией потерь",
}
# Station names as the metro signs spell them.
METRO_NAMES = {
    "Марьина роща": "Марьина Роща",
    "Савеловская": "Савёловская",
    "Крестьянская Застава": "Крестьянская застава",
    "Кузнецкий Мост": "Кузнецкий мост",
    "Красные Ворота": "Красные ворота",
    "Парк Культуры": "Парк культуры",
}
MONTHS_RU = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября",
             "ноября", "декабря"]

CENTER_X, CENTER_Y = to_xy(*RED_SQUARE)


# ---------------------------------------------------------------- formatting


def num(value, digits=0, sign=False):
    """A number in Russian typography: narrow spaces between thousands, decimal comma, true minus."""
    text = f"{value:+,.{digits}f}" if sign else f"{value:,.{digits}f}"
    return text.replace(",", " ").replace(".", ",").replace("-", "−")


def pct(share, digits=0):
    return f"{num(100 * share, digits)}%"


def plural(n, one, few, many):
    n = abs(int(n)) % 100
    if 11 <= n <= 14:
        return many
    n %= 10
    return one if n == 1 else few if 2 <= n <= 4 else many


def counted(n, one, few, many):
    return f"{num(n)} {plural(n, one, few, many)}"


def listing(items):
    """'a, b и c'."""
    items = list(items)
    if not items:
        return "нет"
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " и " + items[-1]


def swatch(css_class):
    return f'<span class="swatch {css_class}" aria-hidden="true"></span>'


def score_class(score):
    edges = [-1.2, -0.7, -0.25, 0.25, 0.7, 1.2]  # the same bins as the map
    return f"d{sum(score > edge for edge in edges)}"


def table(header, rows, css_class="compact", caption=None):
    """A table from a header of (title, numeric) pairs and rows of ready <td> strings.

    The caption says what the numbers are; it sits above the table, outside its scroll box.
    """
    head = "".join(f'<th class="num">{title}</th>' if numeric else f"<th>{title}</th>" for title, numeric in header)
    caption = f'<p class="table-caption">{caption}</p>' if caption else ""
    return (
        f'{caption}<div class="table-wrap"><table class="{css_class}"><thead><tr>{head}</tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def td(content, numeric=False, css_class=None):
    classes = " ".join(filter(None, ["num" if numeric else None, css_class]))
    return f'<td class="{classes}">{content}</td>' if classes else f"<td>{content}</td>"


# ---------------------------------------------------------------- geometry


def to_km(lat, lon):
    x, y = to_xy(lat, lon)
    return (np.asarray(x) - CENTER_X) / 1000, (np.asarray(y) - CENTER_Y) / 1000


def simplify(points, tolerance):
    """Douglas-Peucker simplification of an (n, 2) polyline."""
    points = np.asarray(points, dtype=float)
    if len(points) < 3:
        return points
    keep = np.zeros(len(points), dtype=bool)
    keep[[0, -1]] = True
    stack = [(0, len(points) - 1)]
    while stack:
        start, end = stack.pop()
        if end - start < 2:
            continue
        a, b = points[start], points[end]
        between = points[start + 1 : end]
        length = np.hypot(*(b - a))
        if length == 0:
            distances = np.hypot(*(between - a).T)
        else:
            distances = np.abs((b - a)[0] * (between[:, 1] - a[1]) - (b - a)[1] * (between[:, 0] - a[0])) / length
        worst = int(np.argmax(distances))
        if distances[worst] > tolerance:
            middle = start + 1 + worst
            keep[middle] = True
            stack += [(start, middle), (middle, end)]
    return points[keep]


def basemap():
    """Rivers and ring roads as simplified polylines in km from Red Square."""
    geojson = json.loads((OSM / "osm_basemap.geojson").read_text(encoding="utf-8"))
    rivers, rings = [], {}
    for feature in geojson["features"]:
        lon, lat = np.array(feature["geometry"]["coordinates"]).T
        x, y = to_km(lat, lon)
        if np.all(np.maximum(np.abs(x), np.abs(y)) > EXTENT_KM + 0.5):
            continue
        line = np.round(simplify(np.column_stack([x, y]), 0.008), 3).tolist()
        if feature["properties"]["kind"] == "river":
            rivers.append(line)
        else:
            rings.setdefault(feature["properties"]["name"], []).append(line)
    return rivers, rings


def stations(year):
    """Metro stations as the mean position of their exits."""
    exits = data.load_metro_exits() if year == 2019 else data.load_osm_demand()["metro"]
    x, y = to_km(exits["lat"].to_numpy(), exits["lon"].to_numpy())
    grouped = exits.assign(x=x, y=y).groupby("station")[["x", "y"]].mean()
    inside = grouped[np.maximum(grouped["x"].abs(), grouped["y"].abs()) < EXTENT_KM]
    return [{"name": name, "x": round(row.x, 3), "y": round(row.y, 3)} for name, row in inside.iterrows()]


# ---------------------------------------------------------------- data


def load():
    summary = json.loads((REPORT / "summary.json").read_text(encoding="utf-8"))
    scores = pd.read_csv(REPORT / "cell_scores.csv", index_col="cell_id")
    shortlists = {year: pd.read_csv(REPORT / f"shortlist_{year}.csv", index_col="cell_id") for year in YEARS}
    for year in YEARS:
        scores[f"rank_{year}"] = shortlists[year]["rank"].reindex(scores.index).astype("Int64")
    # Russian street addresses from OpenStreetMap; the English ones of the 2019 geocoder as a fallback.
    addresses = pd.read_csv(OSM / "osm_cell_addresses_ru.csv", index_col="cell_id")["address"]
    scores["address"] = addresses.reindex(scores.index).fillna(scores["address"])
    for year in YEARS:
        scores[f"nearest_metro_{year}"] = scores[f"nearest_metro_{year}"].replace(METRO_NAMES)
    return summary, scores


def cell_records(scores):
    cells = data.load_candidates().loc[scores.index]
    hexagons = grid_hexagons(cells["lat"], cells["lon"])
    hex_x, hex_y = to_km(hexagons[..., 0], hexagons[..., 1])
    center_x, center_y = to_km(cells["lat"].to_numpy(), cells["lon"].to_numpy())
    types = list(TYPES_RU)
    records = []
    for i, (cell_id, row) in enumerate(scores.iterrows()):
        record = {
            "id": int(cell_id),
            "hex": np.round(np.column_stack([hex_x[i], hex_y[i]]), 3).tolist(),
            "x": round(float(center_x[i]), 3),
            "y": round(float(center_y[i]), 3),
            "address": row["address"],
            "type": types.index(row["type"]),
            "center_km": float(row["center_km"]),
        }
        for year in YEARS:
            record[f"y{year}"] = {
                "metro": row[f"nearest_metro_{year}"],
                "metro_m": int(row[f"metro_m_{year}"]),
                "shops": int(row[f"shops_{year}"]),
                "services": int(row[f"services_{year}"]),
                "competitors": int(row[f"competitors_{year}"]),
                "expected": float(row[f"expected_{year}"]),
                "score": float(row[f"score_{year}"]),
                "eligible": bool(row[f"eligible_{year}"]),
                **{key: float(row[f"{key}_{year}"]) for key in
                   ("eligibility_frequency", "top10_frequency", "expected_p10", "expected_p90")},
            }
            rank = row[f"rank_{year}"]
            record[f"rank{year}"] = None if pd.isna(rank) else int(rank)
        records.append(record)
    return records


def shortlist_2026(summary, scores):
    """Attach declared sensitivity checks and source discrepancies, not business recommendations."""
    now = summary["now"]
    kept = set(now["kept_with_fast_food"])
    old_ranks = now["ranks_with_2019_footfall"]
    rows = []
    for cell_id, cell in scores[scores["rank_2026"].notna()].sort_values("rank_2026").iterrows():
        rank = int(cell["rank_2026"])
        ranks = [now["single_radius_ranks"][str(cell_id)].get(f"rank at {radius} m") for radius in RADII]
        before, after = int(cell["competitors_2019"]), int(cell["competitors_2026"])
        old_rank = old_ranks.get(str(cell_id))
        stable = all(r is not None and r <= 12 for r in ranks) and rank in kept
        stable = stable and old_rank is not None and old_rank <= 10
        stable = stable and cell["top10_frequency_2026"] >= 0.8
        rows.append(
            {
                "id": int(cell_id),
                "rank": rank,
                "cell": cell,
                "robust": stable,
                "check": before >= 2 * max(after, 1) and before - after >= 5,
            }
        )
    return rows


# ---------------------------------------------------------------- page parts


def osm_link(cell):
    lat, lon = cell["lat"], cell["lon"]
    href = f"https://www.openstreetmap.org/?mlat={lat}&amp;mlon={lon}#map=17/{lat}/{lon}"
    return f'<a class="osm" href="{href}" target="_blank" rel="noopener">OSM ↗</a>'


def station(cell, year):
    return f"{escape(cell[f'nearest_metro_{year}'])}, {num(cell[f'metro_m_{year}'])}&nbsp;м"


def usual(cell, year):
    """Expected counts are conditional means and may be fractional."""
    return num(cell[f"expected_{year}"], 1)


def change_pct(ratio):
    value = 100 * (ratio - 1)
    return "0%" if abs(value) < 0.5 else f"{num(value, sign=True)}%"


def shortlist_2026_table(rows):
    header = [
        ("№", True), ("Где", False), ("Ближайшее метро", False), ("OSM 2026", True),
        ("Прогноз", True), ("Прогноз: 10–90%", True), ("Допуск", True), ("В десятке", True), ("", False),
    ]
    caption = (
        "Счётчики и прогноз для радиуса 300&nbsp;м по прямой. «Допуск» и «В десятке» — частоты в 50 "
        "разбиениях; 10–90% — перцентили прогнозов между разбиениями, не доверительный интервал."
    )
    body = []
    for row in rows:
        cell = row["cell"]
        chips = []
        if row["robust"]:
            chips.append('<span class="chip">устойчиво в проверках</span>')
        if row["check"]:
            chips.append('<span class="chip warn">сверить источник</span>')
        body.append(
            f'<tr data-cell="{row["id"]}" data-year="2026" tabindex="0" '
            f'aria-label="Показать место № {row["rank"]} на карте">'
            + td(row["rank"], numeric=True)
            + td(escape(cell["address"]) + osm_link(cell), css_class="address")
            + td(station(cell, 2026))
            + td(int(cell["competitors_2026"]), numeric=True, css_class="key")
            + td(usual(cell, 2026), numeric=True)
            + td(f"{num(cell['expected_p10_2026'], 1)}–{num(cell['expected_p90_2026'], 1)}", numeric=True)
            + td(pct(cell["eligibility_frequency_2026"]), numeric=True)
            + td(pct(cell["top10_frequency_2026"]), numeric=True)
            + td(f'<span class="chips">{"".join(chips)}</span>')
            + "</tr>"
        )
    return table(header, body, "shortlist", caption)


def excluded_table(scores):
    excluded = scores[(~scores["eligible_2026"]) & (scores["score_2026"] < 0)]
    excluded = excluded.sort_values("score_2026", kind="stable").head(5)
    header = [("Участок", False), ("Метро", False), ("Отклонение", True), ("OSM 2026", True),
              ("Прогноз", True), ("Допуск", True)]
    body = [
        "<tr>" + td(escape(cell["address"])) + td(station(cell, 2026))
        + td(num(cell["score_2026"], 2), numeric=True)
        + td(int(cell["competitors_2026"]), numeric=True) + td(usual(cell, 2026), numeric=True)
        + td(pct(cell["eligibility_frequency_2026"]), numeric=True) + "</tr>"
        for _, cell in excluded.iterrows()
    ]
    return table(header, body)


def shortlist_2019_table(scores):
    header = [
        ("№", True), ("Где", False), ("Ближайшее метро", False), ("Реестр 2019", True),
        ("Прогноз 2019", True), ("OSM 2026", True), ("Разность источников", True),
    ]
    shortlist = scores[scores["rank_2019"].notna()].sort_values("rank_2019")
    caption = (
        "Ретроспективный отбор, рассчитанный сейчас по данным 2019 года. Это не прогноз, опубликованный "
        "в 2019 году. Разность двух источников не равна числу реально открывшихся или закрывшихся заведений."
    )
    body = []
    for cell_id, cell in shortlist.iterrows():
        rank = int(cell["rank_2019"])
        before, after = int(cell["competitors_2019"]), int(cell["competitors_2026"])
        change = "0" if after == before else num(after - before, sign=True)
        body.append(
            f'<tr data-cell="{cell_id}" data-year="2019" tabindex="0" '
            f'aria-label="Показать место № {rank} списка 2019 года на карте">'
            + td(rank, numeric=True)
            + td(escape(cell["address"]), css_class="address")
            + td(station(cell, 2019))
            + td(before, numeric=True)
            + td(usual(cell, 2019), numeric=True)
            + td(after, numeric=True)
            + td(change, numeric=True, css_class="key")
            + "</tr>"
        )
    return table(header, body, "shortlist history", caption)


def saturated_table(summary, scores):
    header = [("Где", False), ("Ближайшее метро", False), ("Реестр 2019", True), ("Прогноз", True),
              ("Факт / прогноз", True)]
    caption = (
        "Наибольшие положительные отклонения в данных 2019 года. Они не доказывают избыток предложения."
    )
    body = []
    for entry in summary["most_saturated"]:
        cell = scores.loc[entry["cell_id"]]
        ratio = cell["competitors_2019"] / cell["expected_2019"]
        body.append(
            "<tr>"
            + td(escape(cell["address"]))
            + td(escape(cell["nearest_metro_2019"]))
            + td(int(cell["competitors_2019"]), numeric=True, css_class="key")
            + td(usual(cell, 2019), numeric=True)
            + td(f"в&nbsp;{num(ratio, 1)} раза", numeric=True)
            + "</tr>"
        )
    return table(header, body, caption=caption)


def quintile_chart(look_forward):
    labels = ["Минимальные отклонения", "Вторая группа", "Третья группа", "Четвёртая группа",
              "Максимальные отклонения"]
    colors = ["var(--d0)", "var(--d1)", "var(--ring)", "var(--d5)", "var(--d6)"]
    top = max(1.1, 1.1 * max(row["change"] for row in look_forward["by_quintile"]))
    rows = []
    for label, color, quintile in zip(labels, colors, look_forward["by_quintile"], strict=True):
        counts = f"{num(quintile['venues_2019'])} → {num(quintile['venues_2026'])} кафе"
        rows.append(
            f'<div class="bar-row"><span class="bar-label">{label}<small>{counts}</small></span>'
            f'<span class="bar-track"><span class="bar" style="width:{100 * quintile["change"] / top:.1f}%;'
            f'background:{color}"></span><span class="ref" style="left:{100 / top:.1f}%"></span></span>'
            f'<span class="bar-value">{change_pct(quintile["change"])}</span></div>'
        )
    return (
        '<figure class="chart" id="quintiles"><figcaption><strong>Сопоставление сумм счётчиков двух источников'
        "</strong>Пять групп по отклонению в данных 2019 года: реестр 2019 → OSM 2026. "
        "Пунктир отмечает равенство счётчиков. Это не оценка роста рынка.</figcaption>"
        f'<div class="bars">{"".join(rows)}</div></figure>'
    )


def by_type_table(look_forward):
    header = [("Тип района", False), ("Участков", True), ("Реестр 2019", True), ("OSM 2026", True),
              ("Различие счётчиков", True)]
    caption = "Суммы счётчиков по участкам каждого типа; источники различаются по полноте и классификации."
    body = []
    for i, name in enumerate(TYPES_RU):
        row = look_forward["by_type"][name]
        body.append(
            "<tr>"
            + td(f"{swatch(f't{i}')}{TYPES_RU[name]}")
            + "".join(td(num(row[key]), numeric=True) for key in ["cells", "venues_2019", "venues_2026"])
            + td(change_pct(row["change"]), numeric=True, css_class="key")
            + "</tr>"
        )
    return table(header, body, caption=caption)


def effect_label(column, effect):
    label = EFFECTS_RU[column]
    if effect["before"] is not None:
        label += f": {num(effect['before'])} → {num(effect['after'])}"
    return label


def effects_chart(summary):
    rows = sorted(summary["effects"].items(), key=lambda item: item[1]["effect, %"], reverse=True)
    low = min(0, min(row["95% low"] for _, row in rows)) - 4
    high = max(0, max(row["95% high"] for _, row in rows)) + 4

    def position(value):
        return 100 * (min(max(value, low), high) - low) / (high - low)

    lines = []
    for column, effect in rows:
        value, lo, hi = effect["effect, %"], effect["95% low"], effect["95% high"]
        clear = lo > 0 or hi < 0
        kind = ("pos" if value > 0 else "neg") if clear else "flat"
        interval = f"условный bootstrap-интервал: {num(lo, 1, sign=True)}…{num(hi, 1, sign=True)}%"
        label = effect_label(column, effect)
        title = f"{label}: {num(value, 1, sign=True)}%, {interval}"
        lines.append(
            f'<div class="dot-row" title="{escape(title)}">'
            f'<span class="dot-label">{label}</span>'
            f'<span class="dot-track"><span class="ci {kind}" style="left:{position(lo):.2f}%;'
            f'width:{position(hi) - position(lo):.2f}%"></span>'
            f'<span class="pt {kind}" style="left:{position(value):.2f}%"></span></span>'
            f'<span class="dot-value">{num(value, 0, sign=True)}%</span></div>'
        )
    ticks = "".join(
        f'<span class="tick" style="left:{position(t):.2f}%">{num(t, sign=t != 0)}%</span>'
        for t in np.arange(np.ceil(low / 10) * 10, high, 10)
    )
    return (
        '<figure class="chart" id="effects">'
        "<figcaption><strong>Контрасты прогноза при фиксированных остальных признаках</strong>"
        "Учтены log1p и обученный порог ограничения счётчика. Отрезок — 95%-й блочный bootstrap-интервал "
        "при фиксированной регуляризации. Серый означает, что интервал содержит ноль; это не доказательство "
        "отсутствия связи. Контрасты не устанавливают причинность.</figcaption>"
        f'<div class="dots" style="--zero:{position(0):.2f}%">{"".join(lines)}'
        f'<div class="dot-row axis"><span></span><span class="dot-track">{ticks}</span><span></span></div>'
        "</div></figure>"
    )


def chains_chart(summary):
    chains = list(summary["top_chains"].items())[:12]
    top = chains[0][1]
    rows = "".join(
        f'<div class="bar-row"><span class="bar-label">{escape(name)}</span>'
        f'<span class="bar-track"><span class="bar" style="width:{100 * count / top:.1f}%"></span></span>'
        f'<span class="bar-value">{count}</span></div>'
        for name, count in chains
    )
    return (
        '<figure class="chart" id="chains"><figcaption><strong>Крупнейшие сети кафе и ресторанов в радиусе '
        "6&nbsp;км, 2019</strong>Число заведений с отметкой сети в городском реестре.</figcaption>"
        f'<div class="bars">{rows}</div></figure>'
    )


def model_table(summary):
    best = max(summary["model_d2"], key=summary["model_d2"].get)
    body = [
        f'<tr{" class=best" if name == best else ""}>{td(MODELS_RU[name])}{td(num(value, 2), numeric=True)}</tr>'
        for name, value in summary["model_d2"].items()
    ]
    return table([("Способ расчёта", False), ("D²", True)], body)


def typology_table(summary):
    header = [("Тип района", False), ("Участков", True), ("Кафе", True), ("Выходы метро", True),
              ("Магазины", True), ("Услуги", True), ("До метро", True), ("До центра", True)]
    body = []
    for i, name in enumerate(TYPES_RU):
        profile = summary["typology"][name]
        body.append(
            "<tr>"
            + td(f"{swatch(f't{i}')}{TYPES_RU[name]}")
            + "".join(td(num(profile[key]), numeric=True)
                      for key in ["cells", "competitors", "metro_exits", "shops", "services"])
            + td(f"{num(profile['metro_distance'])}&nbsp;м", numeric=True)
            + td(f"{num(profile['center_distance'] / 1000, 1)}&nbsp;км", numeric=True)
            + "</tr>"
        )
    caption = (
        "Типичный участок каждого типа (медиана): сколько в 300&nbsp;м кафе, выходов метро, магазинов "
        "и услуг и как далеко метро и Красная площадь. Данные 2019 года."
    )
    return table(header, body, caption=caption)


def data_table(osm_date):
    layers = [
        ("Участки", "сетка 2019 года", data.load_candidates),
        ("Кафе, рестораны и другой общепит", "реестр data.mos.ru, 2019", data.load_catering),
        ("Выходы метро", "data.mos.ru, 2019", data.load_metro_exits),
        ("Остановки наземного транспорта", "data.mos.ru, 2019", data.load_bus_stops),
        ("Платные парковки", "data.mos.ru, 2019", data.load_parking),
        ("Магазины", "реестр data.mos.ru, 2019", data.load_shops),
        ("Бытовые услуги", "data.mos.ru, 2019", data.load_services),
        ("Спортзалы", "data.mos.ru, 2019", data.load_fitness),
        ("Вузы и колледжи", f"OpenStreetMap, {osm_date}", data.load_education),
        ("Кафе, рестораны, фастфуд и бары", f"OpenStreetMap, {osm_date}", data.load_osm_catering),
    ]
    demand = data.load_osm_demand()
    for name, key in [("Входы метро, МЦК и МЦД", "metro"), ("Остановки", "bus"), ("Магазины", "shops"),
                      ("Бытовые услуги", "services"), ("Фитнес-клубы", "fitness")]:
        layers.append((name, f"OpenStreetMap, {osm_date}", lambda key=key: demand[key]))
    body = [f"<tr>{td(name)}{td(source)}{td(num(len(loader())), numeric=True)}</tr>" for name, source, loader in layers]
    return table([("Слой", False), ("Источник", False), ("Объектов", True)], body)


# ---------------------------------------------------------------- page


def fields(summary, scores, rows):
    """Values of the ${...} placeholders, derived from the current run."""
    look = summary["look_forward"]
    slope = [2 ** look[key] - 1 for key in ("slope", "slope_low", "slope_high")]
    adjusted = [2 ** look[key] - 1 for key in ("distance_slope", "distance_slope_low", "distance_slope_high")]
    catering = summary["catering_within_6km"]
    robust = [row for row in rows if row["robust"]]
    now = scores[scores["rank_2026"].notna()]
    year, month, day = (int(part) for part in summary["osm_date"].split("-"))
    osm_date = f"{day}&nbsp;{MONTHS_RU[month - 1]} {year}&nbsp;года"
    validation = summary["validation"]
    return {
        "robust_count": num(len(robust)),
        "robust_listing": listing(f"№ {row['rank']} ({escape(row['cell']['nearest_metro_2026'])})" for row in robust),
        "repeats": num(validation["repeats"]),
        "buffer_m": num(validation["buffer_m"]),
        "minimum_frequency": pct(validation["minimum_eligibility_frequency"]),
        "slope": num(100 * slope[0], 1, sign=True),
        "slope_low": num(100 * slope[1], 1, sign=True),
        "slope_high": num(100 * slope[2], 1, sign=True),
        "distance_slope": num(100 * adjusted[0], 1, sign=True),
        "distance_low": num(100 * adjusted[1], 1, sign=True),
        "distance_high": num(100 * adjusted[2], 1, sign=True),
        "venues_2019": num(look["venues_2019"]),
        "venues_2026": num(look["venues_2026"]),
        "osm_date": osm_date,
        "distance_range": (f"{num(now['center_km'].min(), 1)}–{num(now['center_km'].max(), 1)}"
                           if len(now) else "—"),
        "max_metro": num(now["metro_m_2026"].max()) if len(now) else "—",
        "theta": num(summary["theta"], 1) if summary["theta"] is not None else "∞",
        "silhouette": num(summary["silhouette_k4"], 2),
        "d2_glm": pct(validation["d2"], 1),
        "d2_2026": pct(summary["now"]["d2"], 1),
        "d2_2026_old": pct(summary["now"]["d2_2019_footfall"], 1),
        "catering_total": counted(sum(catering.values()), "заведение", "заведения", "заведений"),
        "cafes": f"{num(catering['кафе'])} кафе",
        "restaurants": counted(catering["ресторан"], "ресторан", "ресторана", "ресторанов"),
        "seats": counted(summary["competitor_seats"], "посадочное место", "посадочных места", "посадочных мест"),
        "chain_share": pct(summary["chain_share"]),
        "by_type_table": by_type_table(look),
        "shortlist_2026_table": shortlist_2026_table(rows),
        "shortlist_2019_table": shortlist_2019_table(scores),
        "excluded_table": excluded_table(scores),
        "saturated_table": saturated_table(summary, scores),
        "quintile_chart": quintile_chart(look),
        "effects_chart": effects_chart(summary),
        "chains_chart": chains_chart(summary),
        "model_table": model_table(summary),
        "typology_table": typology_table(summary),
        "data_table": data_table(osm_date),
    }


FONTS = (
    "https://fonts.googleapis.com/css2?family=Golos+Text:wght@400;500;600"
    "&family=JetBrains+Mono:wght@400;500&family=Unbounded:wght@500;600&display=swap"
)
HEAD = f"""<title>Кафе в центре Москвы: участки для проверки</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
"""


def build(fragment=False):
    summary, scores = load()
    rows = shortlist_2026(summary, scores)
    rivers, rings = basemap()
    payload = {
        "cells": cell_records(scores),
        "types": list(TYPES_RU.values()),
        "rivers": rivers,
        "rings": rings,
        "stations": {str(year): stations(year) for year in YEARS},
        "extent": EXTENT_KM,
        "start": rows[0]["id"] if rows else int(scores.index[0]),
    }
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    page = Template((PAGE / "template.html").read_text(encoding="utf-8")).substitute(fields(summary, scores, rows))
    style = (PAGE / "style.css").read_text(encoding="utf-8")
    script = (PAGE / "script.js").read_text(encoding="utf-8")
    head = f"{HEAD}<style>\n{style}</style>\n"
    content = f'{page}<script type="application/json" id="report-data">{blob}</script>\n<script>\n{script}</script>\n'
    if fragment:
        return head + content
    return (
        '<!doctype html>\n<html lang="ru">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        f"{head}</head>\n<body>\n{content}</body>\n</html>\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fragment", type=Path, help="write the page without <html>/<head>/<body> to this path")
    args = parser.parse_args()
    if args.fragment:
        args.fragment.write_text(build(fragment=True), encoding="utf-8")
        print(f"wrote {args.fragment}")
    else:
        target = REPORT / "report_ru.html"
        target.write_text(build(fragment=False), encoding="utf-8")
        print(f"wrote {target}")


if __name__ == "__main__":
    main()
