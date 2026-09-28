"""Build the Russian report page from the outputs of notebook 03.

    python scripts/build_report_page.py                   # report/report_ru.html, a standalone page
    python scripts/build_report_page.py --fragment PATH   # the same page without <html>/<head>/<body>

Inputs: report/summary.json, report/cell_scores.csv and report/shortlist_{2019,2026}.csv (written
by the notebook), data/osm/osm_basemap.geojson and data/osm/osm_cell_addresses_ru.csv (written by
scripts/fetch_osm_data.py) and the data layers themselves, for the record counts. The text of the
page is report_page.html, its style and script are report_page.css and report_page.js.
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

HERE = Path(__file__).resolve().parent
REPORT = ROOT / "report"
OSM = ROOT / "data" / "osm"
EXTENT_KM = 6.6
YEARS = (2019, 2026)
RADII = (250, 300, 400)

TYPES_RU = {
    "Transit hubs": "Транспортные узлы",
    "Central neighbourhoods": "Центральные кварталы",
    "Residential belt": "Жилой пояс",
    "Parks, rail and industrial land": "Парки, железные дороги и промзоны",
}
EFFECTS_RU = {
    "center_distance_km": "На 1 км дальше от Красной площади",
    "metro_distance_km": "На 100 м дальше от выхода метро",
    "shops": "Вдвое больше магазинов",
    "services": "Вдвое больше бытовых услуг",
    "parking_spaces": "Вдвое больше парковочных мест",
    "metro_exits": "Вдвое больше выходов метро",
    "education": "Вдвое больше вузов и колледжей",
    "bus_stops": "Вдвое больше остановок",
    "fitness": "Вдвое больше спортзалов",
}
MODELS_RU = {
    "Poisson GLM, log distances": "Пуассоновская регрессия, логарифм расстояний",
    "Poisson GLM, linear distances": "Пуассоновская регрессия, линейные расстояния",
    "Gradient boosting, Poisson loss": "Градиентный бустинг с пуассоновской функцией потерь",
    "Average of the GLM and boosting": "Среднее регрессии и бустинга",
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

# The hand-written notes of report_page.html describe these cells. A rerun that changes them must
# update the notes too, so the build stops instead of publishing text that no longer fits.
NOTES = {
    "robust": [2, 3, 5],  # ranks on the 2026 shortlist
    "check": {5: (9, 1)},  # rank: (2019 register, OpenStreetMap 2026)
    "saturated": [254, 316, 78, 137, 96, 136],  # cell ids, most saturated in 2019 first
}

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
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " и " + items[-1]


def swatch(css_class):
    return f'<span class="swatch {css_class}" aria-hidden="true"></span>'


def score_class(score):
    edges = [-1.2, -0.7, -0.25, 0.25, 0.7, 1.2]  # the same bins as the map
    return f"d{sum(score > edge for edge in edges)}"


def table(header, rows, css_class="compact"):
    """A table from a header of (title, numeric) pairs and rows of ready <td> strings."""
    head = "".join(f'<th class="num">{title}</th>' if numeric else f"<th>{title}</th>" for title, numeric in header)
    return (
        f'<div class="table-wrap"><table class="{css_class}"><thead><tr>{head}</tr></thead>'
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


def stations():
    """Metro stations as the mean position of their exits."""
    exits = data.load_metro_exits()
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
            }
            rank = row[f"rank_{year}"]
            record[f"rank{year}"] = None if pd.isna(rank) else int(rank)
        records.append(record)
    return records


def shortlist_2026(summary, scores):
    """The 2026 shortlist with its checks: stable across catchments, competitor definitions and
    footfall layers, and under-served in the 2019 register as well (`robust`); far fewer venues in
    OpenStreetMap than in the register (`check`)."""
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
        rows.append(
            {
                "id": int(cell_id),
                "rank": rank,
                "cell": cell,
                "ranks": ranks,
                "robust": stable and cell["score_2019"] < 0,
                "check": before >= 2 * max(after, 1) and before - after >= 5,
            }
        )
    return rows


def check_notes(rows, summary):
    robust = [row["rank"] for row in rows if row["robust"]]
    checked = {
        row["rank"]: (int(row["cell"]["competitors_2019"]), int(row["cell"]["competitors_2026"]))
        for row in rows
        if row["check"]
    }
    saturated = [entry["cell_id"] for entry in summary["most_saturated"]]
    found = {"robust": robust, "check": checked, "saturated": saturated}
    if found != NOTES:
        raise SystemExit(f"The results changed: update the notes in report_page.html and NOTES.\n{found}")


# ---------------------------------------------------------------- page parts


def osm_link(cell):
    lat, lon = cell["lat"], cell["lon"]
    href = f"https://www.openstreetmap.org/?mlat={lat}&amp;mlon={lon}#map=17/{lat}/{lon}"
    return f'<a class="osm" href="{href}" target="_blank" rel="noopener">OSM ↗</a>'


def facts_vs_expected(cell, year):
    return f"{int(cell[f'competitors_{year}'])} / {num(cell[f'expected_{year}'], 1)}"


def score_td(score):
    return td(f"{swatch(score_class(score))}{num(score, 2)}", numeric=True)


def shortlist_2026_table(rows):
    header = [
        ("№", True), ("Метро", False), ("Адрес центра ячейки", False), ("До выхода метро", True),
        ("До Красной площади", True), ("Кафе и рестораны: факт / ожидание", True), ("Оценка", True),
        ("Реестр 2019", True), ("Место при 250 · 300 · 400&nbsp;м", True), ("", False),
    ]
    body = []
    for row in rows:
        cell = row["cell"]
        chips = []
        if row["robust"]:
            chips.append('<span class="chip">устойчиво</span>')
        if row["check"]:
            chips.append('<span class="chip warn">сверить данные</span>')
        ranks = " · ".join("—" if rank is None else num(rank) for rank in row["ranks"])
        body.append(
            f'<tr data-cell="{row["id"]}" tabindex="0" aria-label="Показать место № {row["rank"]} на карте">'
            + td(row["rank"], numeric=True)
            + td(escape(cell["nearest_metro_2026"]))
            + td(escape(cell["address"]) + osm_link(cell), css_class="address")
            + td(f"{num(cell['metro_m_2026'])}&nbsp;м", numeric=True)
            + td(f"{num(cell['center_km'], 1)}&nbsp;км", numeric=True)
            + td(facts_vs_expected(cell, 2026), numeric=True)
            + score_td(cell["score_2026"])
            + td(int(cell["competitors_2019"]), numeric=True)
            + td(ranks, numeric=True)
            + td(f'<span class="chips">{"".join(chips)}</span>')
            + "</tr>"
        )
    return table(header, body, "shortlist")


def shortlist_2019_table(scores):
    header = [
        ("№", True), ("Метро", False), ("Адрес центра ячейки", False), ("2019: факт / ожидание", True),
        ("Оценка 2019", True), ("2026, OpenStreetMap", True), ("", False),
    ]
    body = []
    for cell_id, cell in scores[scores["rank_2019"].notna()].sort_values("rank_2019").iterrows():
        rank = int(cell["rank_2019"])
        before, after = int(cell["competitors_2019"]), int(cell["competitors_2026"])
        change = "±0" if after == before else num(after - before, sign=True)
        stayed = "" if pd.isna(cell["rank_2026"]) else f'<span class="chip">№&nbsp;{cell["rank_2026"]} в 2026</span>'
        body.append(
            f'<tr data-cell="{cell_id}" tabindex="0" aria-label="Показать место № {rank} списка 2019 года на карте">'
            + td(rank, numeric=True)
            + td(escape(cell["nearest_metro_2019"]))
            + td(escape(cell["address"]), css_class="address")
            + td(facts_vs_expected(cell, 2019), numeric=True)
            + score_td(cell["score_2019"])
            + td(f'{after} <span class="delta">{change}</span>', numeric=True)
            + td(stayed)
            + "</tr>"
        )
    return table(header, body, "shortlist history")


def saturated_table(summary, scores):
    header = [("Адрес центра ячейки", False), ("Метро", False), ("2019: факт / ожидание", True), ("Оценка", True)]
    body = []
    for entry in summary["most_saturated"]:
        cell = scores.loc[entry["cell_id"]]
        body.append(
            "<tr>"
            + td(escape(cell["address"]))
            + td(escape(cell["nearest_metro_2019"]))
            + td(facts_vs_expected(cell, 2019), numeric=True)
            + score_td(cell["score_2019"])
            + "</tr>"
        )
    return table(header, body)


def quintile_chart(look_forward):
    labels = ["1: самые недообеспеченные", "2", "3", "4", "5: самые насыщенные"]
    colors = ["var(--d0)", "var(--d1)", "var(--ring)", "var(--d5)", "var(--d6)"]
    top = 1.8
    rows = []
    for label, color, quintile in zip(labels, colors, look_forward["by_quintile"], strict=True):
        counts = f"{num(quintile['venues_2019'])} → {num(quintile['venues_2026'])}"
        rows.append(
            f'<div class="bar-row"><span class="bar-label">{label}<small>{counts}</small></span>'
            f'<span class="bar-track"><span class="bar" style="width:{100 * quintile["change"] / top:.1f}%;'
            f'background:{color}"></span><span class="ref" style="left:{100 / top:.1f}%"></span></span>'
            f'<span class="bar-value">×{num(quintile["change"], 2)}</span></div>'
        )
    return (
        '<figure class="chart" id="quintiles"><figcaption><strong>Сколько заведений стало к 2026 году'
        "</strong>Ячейки разбиты на пять равных групп по оценке 2019 года. Отношение числа кафе и ресторанов "
        "в OpenStreetMap 2026 к реестру 2019; вертикальная линия отмечает ×1.</figcaption>"
        f'<div class="bars">{"".join(rows)}</div></figure>'
    )


def by_type_table(look_forward):
    header = [("Тип места", False), ("Ячеек", True), ("Заведений в 2019", True), ("В 2026", True),
              ("Изменение", True)]
    body = []
    for i, name in enumerate(TYPES_RU):
        row = look_forward["by_type"][name]
        body.append(
            "<tr>"
            + td(f"{swatch(f't{i}')}{TYPES_RU[name]}")
            + "".join(td(num(row[key]), numeric=True) for key in ["cells", "venues_2019", "venues_2026"])
            + td(f"×{num(row['change'], 2)}", numeric=True)
            + "</tr>"
        )
    return table(header, body)


def effects_chart(summary):
    rows = sorted(summary["effects"].items(), key=lambda item: item[1]["effect, %"], reverse=True)
    low, high = -32.0, 34.0

    def position(value):
        return 100 * (min(max(value, low), high) - low) / (high - low)

    lines = []
    for column, effect in rows:
        value, lo, hi = effect["effect, %"], effect["95% low"], effect["95% high"]
        clear = lo > 0 or hi < 0
        kind = ("pos" if value > 0 else "neg") if clear else "flat"
        interval = f"95%: {num(lo, 1, sign=True)}…{num(hi, 1, sign=True)}%"
        title = f"{EFFECTS_RU[column]}: {num(value, 1, sign=True)}% ({interval})"
        lines.append(
            f'<div class="dot-row" title="{escape(title)}">'
            f'<span class="dot-label">{EFFECTS_RU[column]}</span>'
            f'<span class="dot-track"><span class="ci {kind}" style="left:{position(lo):.2f}%;'
            f'width:{position(hi) - position(lo):.2f}%"></span>'
            f'<span class="pt {kind}" style="left:{position(value):.2f}%"></span></span>'
            f'<span class="dot-value">{num(value, 0, sign=True)}%</span></div>'
        )
    ticks = "".join(
        f'<span class="tick" style="left:{position(t):.2f}%">{num(t, sign=t != 0)}%</span>' for t in range(-30, 31, 10)
    )
    return (
        '<figure class="chart" id="effects">'
        "<figcaption><strong>Как меняется ожидаемое число кафе и ресторанов</strong>"
        "Точка: оценка регрессии, линия: 95% интервал блочного бутстрэпа. Серым отмечены эффекты, "
        "которые нельзя отличить от нуля.</figcaption>"
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
        '<figure class="chart" id="chains"><figcaption><strong>Крупнейшие сети в радиусе 6&nbsp;км, 2019'
        "</strong>Кафе и рестораны с отметкой сетевого заведения в реестре.</figcaption>"
        f'<div class="bars">{rows}</div></figure>'
    )


def model_table(summary):
    best = max(summary["model_d2"], key=summary["model_d2"].get)
    body = [
        f'<tr{" class=best" if name == best else ""}>{td(MODELS_RU[name])}{td(num(value, 2), numeric=True)}</tr>'
        for name, value in summary["model_d2"].items()
    ]
    return table([("Модель", False), ("D², пространственная кросс-валидация", True)], body)


def typology_table(summary):
    header = [("Тип", False), ("Ячеек", True), ("Кафе и рестораны", True), ("Выходы метро", True),
              ("Магазины", True), ("Услуги", True), ("До метро, м", True), ("До центра, км", True)]
    body = []
    for i, name in enumerate(TYPES_RU):
        profile = summary["typology"][name]
        body.append(
            "<tr>"
            + td(f"{swatch(f't{i}')}{TYPES_RU[name]}")
            + "".join(td(num(profile[key]), numeric=True)
                      for key in ["cells", "competitors", "metro_exits", "shops", "services", "metro_distance"])
            + td(num(profile["center_distance"] / 1000, 1), numeric=True)
            + "</tr>"
        )
    return table(header, body)


def data_table(osm_date):
    layers = [
        ("Ячейки-кандидаты", "сетка 2019 года", data.load_candidates),
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
    return table([("Слой", False), ("Источник", False), ("Записей", True)], body)


# ---------------------------------------------------------------- page


def fields(summary, scores, rows):
    """Values of the ${...} placeholders of report_page.html."""
    look = summary["look_forward"]
    q1, q5 = look["by_quintile"][0]["change"], look["by_quintile"][-1]["change"]
    slope = [2 ** look[key] - 1 for key in ("slope", "slope_low", "slope_high")]
    distance_slope = [2 ** look[key] - 1 for key in ("distance_slope", "distance_slope_low", "distance_slope_high")]
    effects = {key: value["effect, %"] for key, value in summary["effects"].items()}
    d2 = summary["model_d2"]
    catering = summary["catering_within_6km"]
    fast_food = catering["предприятие быстрого обслуживания"] + catering["закусочная"]
    other = catering["буфет"] + catering["кафетерий"] + catering["магазин (отдел кулинарии)"]
    past = scores[scores["rank_2019"].notna()]
    stayed = past[past["rank_2026"].notna()].sort_values("rank_2019")
    stayed = [
        f"№&nbsp;{rank} ({escape(metro)})" for rank, metro in stayed[["rank_2019", "nearest_metro_2019"]].to_numpy()
    ]
    robust = [row for row in rows if row["robust"]]
    now = pd.DataFrame([row["cell"] for row in rows])
    year, month, day = (int(part) for part in summary["osm_date"].split("-"))
    osm_date = f"{day}&nbsp;{MONTHS_RU[month - 1]} {year}&nbsp;г."
    return {
        "competitors_2019": counted(summary["competitors_within_6km"], "кафе и ресторан", "кафе и ресторана",
                                    "кафе и ресторанов"),
        "q1_times": f"в {num(q1, 1)} раза больше",
        "q1_change": f"×{num(q1, 2)}",
        "q5_change": f"×{num(q5, 2)}",
        "q5_drop": num(100 * (1 - q5)),
        "slope": num(100 * slope[0]),
        "slope_low": num(100 * slope[1], sign=True),
        "slope_high": num(100 * slope[2], sign=True),
        "outer_q1": f"×{num(look['outer_change'][0], 2)}",
        "outer_q5": f"×{num(look['outer_change'][-1], 2)}",
        "distance_slope": num(100 * distance_slope[0], sign=True),
        "distance_low": num(100 * distance_slope[1], sign=True),
        "distance_high": num(100 * distance_slope[2], sign=True),
        "hubs_drop": num(100 * (1 - look["by_type"]["Transit hubs"]["change"])),
        "belt_gain": num(100 * (look["by_type"]["Residential belt"]["change"] - 1)),
        "by_type_table": by_type_table(look),
        "venues_2019": counted(look["venues_2019"], "заведение", "заведения", "заведений"),
        "venues_2026": num(look["venues_2026"]),
        "short2019_before": num(past["competitors_2019"].sum()),
        "short2019_after": num(past["competitors_2026"].sum()),
        "gained": num((past["competitors_2026"] > past["competitors_2019"]).sum()),
        "stayed": f"В шорт-листе 2026 года остались {listing(stayed)}." if stayed
        else "В шорт-лист 2026 года не вошло ни одно из них.",
        "robust_count": num(len(robust)),
        "robust_label": plural(len(robust), "устойчивый кандидат", "устойчивых кандидата", "устойчивых кандидатов"),
        "robust_names": ", ".join(escape(row["cell"]["nearest_metro_2026"]) for row in robust),
        "robust_listing": listing(escape(row["cell"]["nearest_metro_2026"]) for row in robust),
        "robust_ranks": "№&nbsp;" + listing(str(row["rank"]) for row in robust),
        "osm_date": osm_date,
        "distance_range": f"{num(now['center_km'].min(), 1)}–{num(now['center_km'].max(), 1)}",
        "max_metro": num(now["metro_m_2026"].max()),
        "theta": num(summary["theta"], 1),
        "d2_glm": pct(d2["Poisson GLM, linear distances"]),
        "d2_boosting": pct(d2["Gradient boosting, Poisson loss"]),
        "d2_log": pct(d2["Poisson GLM, log distances"]),
        "d2_random": pct(summary["random_cv_d2"]),
        "d2_2026": pct(summary["now"]["d2"]),
        "d2_2026_old": pct(summary["now"]["d2_2019_footfall"]),
        "effect_center": num(-effects["center_distance_km"]),
        "effect_metro": num(-effects["metro_distance_km"], 1),
        "effect_shops": num(effects["shops"]),
        "effect_services": num(effects["services"]),
        "effect_exits": num(effects["metro_exits"]),
        "silhouette": num(summary["silhouette_k4"], 2),
        "catering_total": counted(sum(catering.values()), "заведение", "заведения", "заведений"),
        "cafes": f"{num(catering['кафе'])} кафе",
        "restaurants": counted(catering["ресторан"], "ресторан", "ресторана", "ресторанов"),
        "canteens": counted(catering["столовая"], "столовая", "столовые", "столовых"),
        "bars": counted(catering["бар"], "бар", "бара", "баров"),
        "fast_food": counted(fast_food, "точка", "точки", "точек"),
        "other": num(other),
        "seats": counted(summary["competitor_seats"], "посадочное место", "посадочных места", "посадочных мест"),
        "chain_share": pct(summary["chain_share"]),
        "shortlist_2026_table": shortlist_2026_table(rows),
        "shortlist_2019_table": shortlist_2019_table(scores),
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
HEAD = f"""<title>Где открыть кафе в центре Москвы</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
"""


def build(fragment):
    summary, scores = load()
    rows = shortlist_2026(summary, scores)
    check_notes(rows, summary)
    rivers, rings = basemap()
    payload = {
        "cells": cell_records(scores),
        "types": list(TYPES_RU.values()),
        "rivers": rivers,
        "rings": rings,
        "stations": stations(),
        "extent": EXTENT_KM,
        "start": rows[0]["id"],
    }
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    page = Template((HERE / "report_page.html").read_text(encoding="utf-8")).substitute(fields(summary, scores, rows))
    style = (HERE / "report_page.css").read_text(encoding="utf-8")
    script = (HERE / "report_page.js").read_text(encoding="utf-8")
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
