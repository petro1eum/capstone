(() => {
  "use strict";

  const DATA = JSON.parse(document.getElementById("report-data").textContent);
  const SVG_NS = "http://www.w3.org/2000/svg";
  const smooth = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";

  // ---------- helpers ----------
  const format = (value, digits = 0) =>
    new Intl.NumberFormat("ru-RU", { minimumFractionDigits: digits, maximumFractionDigits: digits })
      .format(value)
      .replace("-", "−");
  const signed = (value, digits = 2) => (value > 0 ? "+" : "") + format(value, digits);
  const plural = (n, one, few, many) => {
    const tens = Math.abs(n) % 100;
    const units = tens % 10;
    if (tens > 10 && tens < 20) return many;
    if (units === 1) return one;
    return units >= 2 && units <= 4 ? few : many;
  };
  const venues = (n) => `${format(n)} ${plural(n, "заведение", "заведения", "заведений")}`;

  function svg(tag, attrs, parent) {
    const node = document.createElementNS(SVG_NS, tag);
    for (const [key, value] of Object.entries(attrs || {})) node.setAttribute(key, value);
    if (parent) parent.appendChild(node);
    return node;
  }

  function html(tag, className, text, parent) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    if (parent) parent.appendChild(node);
    return node;
  }

  function starPath(r) {
    const points = [];
    for (let i = 0; i < 10; i += 1) {
      const angle = (Math.PI / 5) * i - Math.PI / 2;
      const radius = i % 2 === 0 ? r : r * 0.45;
      points.push(`${(radius * Math.cos(angle)).toFixed(4)},${(radius * Math.sin(angle)).toFixed(4)}`);
    }
    return `M${points.join("L")}Z`;
  }

  function placeTip(tip, frame, clientX, clientY) {
    const box = frame.getBoundingClientRect();
    tip.hidden = false;
    const width = tip.offsetWidth;
    const height = tip.offsetHeight;
    let left = clientX - box.left + 14;
    let top = clientY - box.top + 14;
    if (left + width > box.width - 8) left = clientX - box.left - width - 14;
    if (top + height > box.height - 8) top = clientY - box.top - height - 14;
    tip.style.left = `${Math.max(8, left)}px`;
    tip.style.top = `${Math.max(8, top)}px`;
  }

  function fillTip(tip, title, lines) {
    tip.replaceChildren();
    html("b", null, title, tip);
    lines.forEach((line) => html("span", null, line, tip));
  }

  // ---------- map ----------
  const cells = DATA.cells;
  const byId = new Map(cells.map((cell) => [cell.id, cell]));
  const extent = DATA.extent;
  const map = document.getElementById("map-svg");
  const frame = map.parentElement;
  const tip = document.getElementById("map-tip");
  map.setAttribute("viewBox", `${-extent} ${-extent} ${2 * extent} ${2 * extent}`);
  const point = ([x, y]) => `${x},${-y}`;

  const hexLayer = svg("g", { class: "hexes" }, map);
  const context = svg("g", { class: "context" }, map);
  const stationLayer = svg("g", { class: "stations" }, map);
  const outline = svg("g", { class: "outline" }, map);
  const landmarks = svg("g", { class: "landmarks", "aria-hidden": "true" }, map);

  DATA.rivers.forEach((line) => svg("polyline", { class: "river", points: line.map(point).join(" ") }, context));
  Object.values(DATA.rings).forEach((lines) =>
    lines.forEach((line) => svg("polyline", { class: "ring", points: line.map(point).join(" ") }, context)),
  );
  const stationDots = DATA.stations.map((station) =>
    svg("circle", { class: "station", cx: station.x, cy: -station.y, r: 0.05 }, stationLayer),
  );
  const hexes = cells.map((cell, index) =>
    svg("polygon", { class: "hex", points: cell.hex.map(point).join(" "), "data-index": index }, hexLayer),
  );
  const hoverOutline = svg("polygon", { class: "hover", points: "" }, outline);
  const selectedOutline = svg("polygon", { class: "selected", points: "" }, outline);
  const star = svg("path", { class: "landmark", d: starPath(0.16) }, landmarks);
  const starLabel = svg("text", { class: "landmark-label", x: 0.24, y: 0.1 }, landmarks);
  starLabel.textContent = "Красная площадь";

  // Numbered markers of both shortlists; the layer's year decides which set is shown.
  const markerGroups = {};
  const markers = [];
  for (const year of ["2026", "2019"]) {
    markerGroups[year] = svg("g", { class: `markers markers-${year}` }, map);
    const shortlisted = cells.filter((cell) => cell[`rank${year}`]).sort((a, b) => a[`rank${year}`] - b[`rank${year}`]);
    shortlisted.forEach((cell) => {
      const rank = cell[`rank${year}`];
      const group = svg(
        "g",
        { class: "marker", tabindex: "0", role: "button", "aria-label": `№ ${rank} шорт-листа ${year}: ${cell.address}` },
        markerGroups[year],
      );
      const circle = svg("circle", { cx: cell.x, cy: -cell.y, r: 0.2 }, group);
      const label = svg("text", { x: cell.x, y: -cell.y }, group);
      label.textContent = String(rank);
      group.addEventListener("click", () => select(cell.id));
      group.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          select(cell.id);
        }
      });
      group.addEventListener("pointerenter", (event) => showCellTip(event, cell));
      group.addEventListener("pointerleave", hideTip);
      markers.push({ cell, group, circle, label });
    });
  }

  // Keep markers and labels a readable size in screen pixels at any map width.
  function rescale() {
    const width = map.getBoundingClientRect().width || 600;
    const perKm = width / (2 * extent);
    const radius = Math.max(0.2, 11 / perKm);
    markers.forEach(({ circle, label }) => {
      circle.setAttribute("r", radius);
      label.setAttribute("font-size", (radius * 1.05).toFixed(3));
    });
    stationDots.forEach((dot) => dot.setAttribute("r", Math.max(0.045, 2.2 / perKm)));
    star.setAttribute("d", starPath(Math.max(0.16, 8 / perKm)));
    starLabel.setAttribute("font-size", Math.max(0.24, 11.5 / perKm).toFixed(3));
    starLabel.setAttribute("stroke-width", (3 / perKm).toFixed(4)); // a 3 px halo; the map units are km
    starLabel.setAttribute("x", Math.max(0.24, 11 / perKm).toFixed(3));
    starLabel.setAttribute("y", Math.max(0.1, 4 / perKm).toFixed(3));
  }
  if ("ResizeObserver" in window) new ResizeObserver(rescale).observe(map);
  rescale();

  // ---------- layers and legend ----------
  const SCORE_EDGES = [-1.2, -0.7, -0.25, 0.25, 0.7, 1.2];
  const COUNT_EDGES = [1, 3, 6, 11, 21, 41];
  const COUNT_LABELS = ["0", "1–2", "3–5", "6–10", "11–20", "21–40", "41+"];
  const scoreClass = (score) => `d${SCORE_EDGES.filter((edge) => score > edge).length}`;
  const countClass = (count) => `q${COUNT_EDGES.filter((edge) => count >= edge).length}`;
  const LAYERS = {
    score2026: { year: "2026", fill: (cell) => scoreClass(cell.y2026.score) },
    score2019: { year: "2019", fill: (cell) => scoreClass(cell.y2019.score) },
    type: { year: "2026", fill: (cell) => `t${cell.type}` },
    competitors: { year: "2026", fill: (cell) => countClass(cell.y2026.competitors) },
  };
  let layer = "score2026";
  const legend = document.getElementById("legend");

  function ramp(prefix, labels) {
    const box = html("div", "ramp-box");
    const row = html("div", "ramp", null, box);
    for (let i = 0; i < 7; i += 1) html("span", `${prefix}${i}`, null, row);
    const captions = html("div", labels.length === 7 ? "ramp-labels seven" : "ramp-labels", null, box);
    labels.forEach((text) => html("span", null, text, captions));
    return box;
  }

  function renderLegend() {
    legend.replaceChildren();
    if (layer === "score2026" || layer === "score2019") {
      html("div", "legend-title", `Кафе и рестораны относительно ожидания, ${LAYERS[layer].year}`, legend);
      legend.appendChild(ramp("d", ["меньше", "как обычно", "больше"]));
    } else if (layer === "type") {
      html("div", "legend-title", "Тип места", legend);
      const list = html("ul", "legend-list", null, legend);
      DATA.types.forEach((name, index) => {
        const item = html("li", null, null, list);
        html("span", `swatch t${index}`, null, item);
        html("span", null, `${name} (${format(cells.filter((cell) => cell.type === index).length)})`, item);
      });
    } else {
      html("div", "legend-title", "Кафе и рестораны в 300 м, 2026", legend);
      legend.appendChild(ramp("q", COUNT_LABELS));
    }
    const keys = html("ul", "legend-list keys", null, legend);
    const markerKey = html("li", null, null, keys);
    const year = LAYERS[layer].year;
    html("span", year === "2019" ? "key-marker past" : "key-marker", "1", markerKey);
    html("span", null, `шорт-лист ${year}`, markerKey);
    const riverKey = html("li", null, null, keys);
    html("span", "key-line", null, riverKey);
    html("span", null, "Москва-река и Яуза", riverKey);
    const ringKey = html("li", null, null, keys);
    html("span", "key-line ring-key", null, ringKey);
    html("span", null, "Бульварное, Садовое кольца и ТТК", ringKey);
    const stationKey = html("li", null, null, keys);
    html("span", "key-dot", null, stationKey);
    html("span", null, "станция метро", stationKey);
  }

  function setLayer(name) {
    layer = name;
    hexes.forEach((hex, index) => hex.setAttribute("class", `hex ${LAYERS[name].fill(cells[index])}`));
    Object.entries(markerGroups).forEach(([year, group]) => group.toggleAttribute("hidden", year !== LAYERS[name].year));
    document.querySelectorAll(".tab").forEach((tab) => {
      const active = tab.dataset.layer === name;
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
    });
    renderLegend();
  }

  const tabs = Array.from(document.querySelectorAll(".tab"));
  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => setLayer(tab.dataset.layer));
    tab.addEventListener("keydown", (event) => {
      const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
      if (!step) return;
      const next = tabs[(index + step + tabs.length) % tabs.length];
      next.focus();
      setLayer(next.dataset.layer);
    });
  });

  // ---------- tooltip and cell card ----------
  function yearLines(cell, year) {
    const numbers = cell[`y${year}`];
    return `${year}: ${venues(numbers.competitors)} при ожидаемых ${format(numbers.expected, 1)}, оценка ${signed(numbers.score)}`;
  }

  function showCellTip(event, cell) {
    const year = LAYERS[layer].year;
    const lines = [yearLines(cell, year)];
    if (cell[`rank${year}`]) lines.push(`№ ${cell[`rank${year}`]} шорт-листа ${year}`);
    fillTip(tip, cell.address, lines);
    placeTip(tip, frame, event.clientX, event.clientY);
  }

  function hideTip() {
    tip.hidden = true;
    hoverOutline.setAttribute("points", "");
  }

  hexLayer.addEventListener("pointermove", (event) => {
    const index = event.target.dataset && event.target.dataset.index;
    if (index === undefined) return;
    const cell = cells[Number(index)];
    hoverOutline.setAttribute("points", cell.hex.map(point).join(" "));
    showCellTip(event, cell);
  });
  hexLayer.addEventListener("pointerleave", hideTip);
  hexLayer.addEventListener("click", (event) => {
    const index = event.target.dataset && event.target.dataset.index;
    if (index !== undefined) select(cells[Number(index)].id);
  });

  const card = document.getElementById("cell-card");

  function renderCard(cell) {
    card.replaceChildren();
    html("h3", null, cell.address, card);
    const where = [DATA.types[cell.type], `${cell.metro}, ${format(cell.metro_m)} м`, `${format(cell.center_km, 1)} км от центра`];
    html("p", "where", where.join(" · "), card);
    if (cell.rank2026 || cell.rank2019) {
      const badges = html("div", "badges", null, card);
      if (cell.rank2026) html("span", "badge badge-strong", `№ ${cell.rank2026} шорт-листа 2026`, badges);
      if (cell.rank2019) html("span", "badge", `№ ${cell.rank2019} шорт-листа 2019`, badges);
    }
    const list = html("dl", null, null, card);
    const row = (term, value) => {
      html("dt", null, term, list);
      html("dd", null, value, list);
    };
    for (const year of ["2026", "2019"]) {
      const numbers = cell[`y${year}`];
      row(`Кафе и рестораны, ${year}`, `${format(numbers.competitors)} / ${format(numbers.expected, 1)}`);
      row(`Оценка ${year}`, `${signed(numbers.score)}${numbers.eligible ? "" : " · вне фильтров"}`);
    }
    row("Магазины / услуги", `${format(cell.shops)} / ${format(cell.services)}`);
    html("p", "card-note", "Кафе и рестораны: факт в радиусе 300 м / ожидание модели.", card);
  }

  function select(id, { scroll = false } = {}) {
    const cell = byId.get(id);
    if (!cell) return;
    selectedOutline.setAttribute("points", cell.hex.map(point).join(" "));
    markers.forEach(({ cell: markerCell, group }) => group.classList.toggle("is-selected", markerCell.id === id));
    document.querySelectorAll("tr[data-cell]").forEach((tr) => tr.classList.toggle("is-selected", Number(tr.dataset.cell) === id));
    renderCard(cell);
    if (scroll) document.getElementById("map").scrollIntoView({ behavior: smooth, block: "start" });
  }

  document.querySelectorAll("tr[data-cell]").forEach((tr) => {
    const id = Number(tr.dataset.cell);
    tr.addEventListener("click", (event) => {
      if (event.target.closest("a")) return;
      select(id, { scroll: true });
    });
    tr.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        select(id, { scroll: true });
      }
    });
  });

  setLayer(layer);
  select(DATA.start);

  // ---------- scatter: actual vs expected, 2019 ----------
  const scatter = document.getElementById("scatter-svg");
  const scatterTip = document.getElementById("scatter-tip");
  const scatterBox = scatter.parentElement;
  const TICKS = [0, 1, 5, 10, 20, 40, 80];
  let scatterPoints = [];
  let focusRing = null;

  function drawScatter() {
    const width = Math.max(280, scatterBox.getBoundingClientRect().width);
    const height = Math.round(Math.min(460, width * 0.82));
    const margin = { top: 12, right: 16, bottom: 46, left: 44 };
    scatter.setAttribute("viewBox", `0 0 ${width} ${height}`);
    scatter.setAttribute("width", width);
    scatter.setAttribute("height", height);
    scatter.replaceChildren();
    const maxValue = Math.max(...cells.map((cell) => Math.max(cell.y2019.expected, cell.y2019.competitors)));
    const domain = Math.sqrt(maxValue) + 0.4;
    const sx = (value) => margin.left + (Math.sqrt(value) / domain) * (width - margin.left - margin.right);
    const sy = (value) => height - margin.bottom - (Math.sqrt(value) / domain) * (height - margin.top - margin.bottom);
    TICKS.filter((tick) => Math.sqrt(tick) <= domain).forEach((tick) => {
      svg("line", { class: "grid-line", x1: sx(tick), x2: sx(tick), y1: margin.top, y2: height - margin.bottom }, scatter);
      svg("line", { class: "grid-line", x1: margin.left, x2: width - margin.right, y1: sy(tick), y2: sy(tick) }, scatter);
      const xLabel = svg("text", { class: "axis-text", x: sx(tick), y: height - margin.bottom + 16, "text-anchor": "middle" }, scatter);
      xLabel.textContent = tick;
      const yLabel = svg("text", { class: "axis-text", x: margin.left - 8, y: sy(tick) + 4, "text-anchor": "end" }, scatter);
      yLabel.textContent = tick;
    });
    const top = Math.min(maxValue, domain * domain);
    svg("line", { class: "diagonal", x1: sx(0), y1: sy(0), x2: sx(top), y2: sy(top) }, scatter);
    const xTitle = svg("text", { class: "axis-title", x: (margin.left + width - margin.right) / 2, y: height - 8, "text-anchor": "middle" }, scatter);
    xTitle.textContent = "Ожидание модели (вне выборки)";
    const yTitle = svg("text", { class: "axis-title", x: 12, y: margin.top + 4, "text-anchor": "start" }, scatter);
    yTitle.textContent = "Факт";
    const ordered = [...cells].sort((a, b) => Boolean(a.rank2019) - Boolean(b.rank2019));
    scatterPoints = ordered.map((cell) => {
      const x = sx(cell.y2019.expected);
      const y = sy(cell.y2019.competitors);
      svg("circle", { class: cell.rank2019 ? "pt-short" : "pt-cell", cx: x, cy: y, r: cell.rank2019 ? 5 : 3.5 }, scatter);
      return { x, y, cell };
    });
    focusRing = svg("circle", { class: "pt-focus", cx: -20, cy: -20, r: 8 }, scatter);
  }

  scatter.addEventListener("pointermove", (event) => {
    const box = scatter.getBoundingClientRect();
    const x = event.clientX - box.left;
    const y = event.clientY - box.top;
    let best = null;
    let bestDistance = 18 * 18;
    for (const candidate of scatterPoints) {
      const distance = (candidate.x - x) ** 2 + (candidate.y - y) ** 2;
      if (distance < bestDistance) {
        best = candidate;
        bestDistance = distance;
      }
    }
    if (!best) {
      scatterTip.hidden = true;
      focusRing.setAttribute("cx", -20);
      return;
    }
    focusRing.setAttribute("cx", best.x);
    focusRing.setAttribute("cy", best.y);
    const numbers = best.cell.y2019;
    const lines = [`2019: ${venues(numbers.competitors)} при ожидаемых ${format(numbers.expected, 1)}`];
    if (best.cell.rank2019) lines.push(`№ ${best.cell.rank2019} шорт-листа 2019`);
    fillTip(scatterTip, best.cell.address, lines);
    placeTip(scatterTip, scatterBox, event.clientX, event.clientY);
  });
  scatter.addEventListener("pointerleave", () => {
    scatterTip.hidden = true;
    if (focusRing) focusRing.setAttribute("cx", -20);
  });

  drawScatter();
  if ("ResizeObserver" in window) {
    let lastWidth = 0;
    new ResizeObserver((entries) => {
      const width = Math.round(entries[0].contentRect.width);
      if (width !== lastWidth) {
        lastWidth = width;
        drawScatter();
      }
    }).observe(scatterBox);
  }
})();
