"""Integration checks for the committed numerical outputs and their interactive presentation."""

import json
from html.parser import HTMLParser
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from moscow_cafes import model

REPORT = Path(__file__).resolve().parents[1] / "report"


@pytest.mark.parametrize("year", [2019, 2026])
def test_saved_shortlists_metrics_and_stability_agree(year):
    scores = pd.read_csv(REPORT / "cell_scores.csv", index_col="cell_id")
    shortlist = pd.read_csv(REPORT / f"shortlist_{year}.csv", index_col="cell_id")
    stability = pd.read_csv(REPORT / f"screening_stability_{year}.csv", index_col="cell_id")
    summary = json.loads((REPORT / "summary.json").read_text())
    expected_ids = model.top_ten(pd.DataFrame({
        "score": scores[f"score_{year}"], "eligible": scores[f"eligible_{year}"],
    })).index
    assert shortlist.index.equals(expected_ids)
    actual_d2 = model.d2(scores[f"competitors_{year}"], scores[f"expected_{year}"])
    metrics = summary["validation"] if year == 2019 else summary["now"]
    assert metrics["d2"] == pytest.approx(actual_d2, abs=1e-12)
    assert (shortlist["eligibility_frequency"] >= model.MIN_ELIGIBILITY_FREQUENCY).all()
    for column in stability:
        np.testing.assert_allclose(scores[f"{column}_{year}"], stability[column], atol=1e-12)
    for column in ["eligibility_frequency", "top10_frequency"]:
        assert stability[column].between(0, 1).all()
        # Each frequency represents an actual count of the declared 50 trials.
        counts = stability[column] * summary["validation"]["repeats"]
        np.testing.assert_allclose(counts, np.round(counts), atol=1e-12)
    assert (stability["expected_p10"] <= stability["expected_p90"]).all()
    folds = pd.read_csv(REPORT / f"cv_folds_{year}.csv")
    assert set(folds["alpha"]).issubset(model.ALPHAS)
    assert len(folds) == model.REPEATS * len(model.RADII) * 6
    assert not folds.duplicated(["seed", "radius", "fold"]).any()
    assert (folds.groupby(["seed", "radius"])["test_rows"].sum() == len(scores)).all()


class PayloadParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.collect = False
        self.payload = ""

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("id") == "report-data":
            self.collect = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.collect = False

    def handle_data(self, data):
        if self.collect:
            self.payload += data


def test_interactive_map_uses_current_counts_predictions_and_ranks():
    parser = PayloadParser()
    parser.feed((REPORT / "report_ru.html").read_text())
    payload = json.loads(parser.payload)
    scores = pd.read_csv(REPORT / "cell_scores.csv", index_col="cell_id")
    assert {cell["id"] for cell in payload["cells"]} == set(scores.index)
    for year in (2019, 2026):
        shortlist = pd.read_csv(REPORT / f"shortlist_{year}.csv", index_col="cell_id")
        for cell in payload["cells"]:
            source = scores.loc[cell["id"]]
            displayed = cell[f"y{year}"]
            for field in ("competitors", "expected", "score", "eligibility_frequency", "top10_frequency",
                          "expected_p10", "expected_p90"):
                assert displayed[field] == pytest.approx(source[f"{field}_{year}"], abs=1e-12)
            rank = shortlist.loc[cell["id"], "rank"] if cell["id"] in shortlist.index else None
            assert cell[f"rank{year}"] == rank
