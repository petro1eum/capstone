import numpy as np
import pandas as pd
import pytest
from scipy.spatial.distance import cdist

from moscow_cafes import model


def features(n=64):
    x = np.arange(n, dtype=float)
    frame = pd.DataFrame({c: (x % 7) + 1 for c in model.COUNT_DRIVERS})
    frame["shops"] = x + 1
    frame["metro_distance"] = 100 + x
    frame["center_distance"] = 1000 + x * 50
    frame["competitors"] = (x % 11).astype(int)
    return frame


def positions():
    x, y = np.meshgrid(np.arange(8) * 600, np.arange(8) * 600)
    return np.column_stack([x.ravel(), y.ravel()])


def test_caps_are_fitted_to_training_rows_only():
    train = features(20)
    design = model.CountDesign().fit(train)
    cap = train["shops"].quantile(.99)
    held_out = train.iloc[:1].assign(shops=1_000_000)
    assert design.transform(held_out).iloc[0]["shops"] == pytest.approx(np.log1p(cap))
    assert design.caps_["shops"] == cap


def test_doubling_matches_the_actual_capped_log1p_prediction():
    frame = features()
    fitted = model.glm().fit(frame, frame["shops"] / 3 + 1)
    for before, after in [(1, 2), (10, 20), (100, 200)]:
        pair = pd.concat([frame.iloc[:1].assign(shops=before), frame.iloc[:1].assign(shops=after)])
        prediction = fitted.predict(pair)
        expected = 100 * (prediction[1] / prediction[0] - 1)
        assert model.count_effect(fitted, "shops", before, after) == pytest.approx(expected, abs=1e-10)
    assert model.count_effect(fitted, "shops", 100, 200) == 0


def test_spatial_buffer_removes_neighbours_across_block_boundaries():
    xy = positions()
    splits = model.spatial_splits(xy)
    np.testing.assert_array_equal(np.sort(np.concatenate([test for _, test in splits])), np.arange(len(xy)))
    blocks = model.block_ids(xy)
    for train, test in splits:
        assert not set(blocks[train]) & set(blocks[test])
        assert cdist(xy[train], xy[test]).min() > model.BUFFER_M


def test_outer_test_targets_cannot_change_their_own_predictions(monkeypatch):
    # A real nested fit, using two candidate penalties to keep this regression test small.
    original = model.select_alpha

    def two_alphas(*args, **kwargs):
        return original(*args, **kwargs, alphas=(.1, 1.0))

    monkeypatch.setattr(model, "select_alpha", two_alphas)
    frame = features()
    xy = positions() * 2  # enough blocks remain for the inner six-fold validation
    _, test = model.spatial_splits(xy)[0]
    y = frame["competitors"].copy()
    before, _ = model.nested_predictions(frame, y, xy, include_education=False)
    y.iloc[test] += 1000
    after, _ = model.nested_predictions(frame, y, xy, include_education=False)
    np.testing.assert_allclose(before.iloc[test], after.iloc[test], rtol=0, atol=0)


def test_2019_model_does_not_use_2026_education():
    frame = features()
    design = model.CountDesign(include_education=False).fit(frame)
    altered = frame.assign(education=100_000)
    pd.testing.assert_frame_equal(design.transform(frame), design.transform(altered))
    assert "education" not in design.get_feature_names_out()


def test_poisson_limit_for_nonpositive_excess_dispersion():
    y = pd.Series([1, 1, 1])
    gap, theta = model.residual_gap(y, pd.Series([1., 1., 1.]))
    assert np.isinf(theta)
    np.testing.assert_array_equal(gap, [0, 0, 0])
    with pytest.raises(ValueError, match="positive"):
        model.residual_gap(y, pd.Series([0., 1., 1.]))


def test_ranking_uses_full_precision_and_excludes_positive_residuals():
    scores = pd.DataFrame({"score": [-1.146, -1.154, .2], "eligible": [True, True, True]}, index=[1, 2, 3])
    assert list(model.top_ten(scores).index) == [2, 1]


def test_a_single_lucky_split_cannot_admit_a_borderline_candidate(monkeypatch):
    frame = features(3).assign(shops=20, services=5, metro_distance=100, competitors=[0, 8, 20])

    def predictions(features, y, xy, *, seed, include_education):
        # The extreme first prediction raises the aggregate above the median, but the
        # candidate fails eligibility in four of five splits, like the audited failure.
        return pd.Series([100 if seed == 0 else 9, 10, 11], index=frame.index), []

    monkeypatch.setattr(model, "nested_predictions", predictions)
    result = model.repeated_screening({r: frame for r in model.RADII}, np.zeros((3, 2)), seeds=range(5))
    assert result["runs"][300].loc[0, "eligible"]
    assert result["stability"].loc[0, "eligibility_frequency"] == .2
    assert not result["eligible"].loc[0]
