"""Count predictions and screening diagnostics, not estimates of unmet consumer demand.

All learned preprocessing lives inside the model pipeline. Spatial validation keeps an
800 m buffer (twice the largest 400 m catchment) around test centres, including during
inner tuning. Repeated splits expose sensitivity of the screening rule to training data.
"""

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import PoissonRegressor
from sklearn.metrics import d2_tweedie_score, mean_poisson_deviance
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.validation import check_is_fitted

COUNT_DRIVERS = ("metro_exits", "bus_stops", "parking_spaces", "shops", "services", "fitness", "education")
DISTANCES = ("metro_distance", "center_distance")
RADII = (250, 300, 400)
BLOCK_M = 2000
BUFFER_M = 2 * max(RADII)
ALPHAS = (0.1, 0.3, 1.0, 3.0, 10.0)
REPEATS = 50
SEEDS = tuple(range(REPEATS))
# A declared screening policy, not a probability of commercial success or a significance level.
MIN_ELIGIBILITY_FREQUENCY = 0.8


class CountDesign(TransformerMixin, BaseEstimator):
    """Fit count caps on training rows; never use target columns or a future education layer."""

    def __init__(self, *, include_education=True, distances="linear", quantile=0.99):
        self.include_education = include_education
        self.distances = distances
        self.quantile = quantile

    def fit(self, X, y=None):
        if self.distances not in ("linear", "log1p"):
            raise ValueError("distances must be 'linear' or 'log1p'")
        self.count_columns_ = [c for c in COUNT_DRIVERS if c != "education" or self.include_education]
        self.caps_ = X[self.count_columns_].quantile(self.quantile).astype(float)
        self.feature_names_ = self.count_columns_ + [f"{c}_km" for c in DISTANCES]
        return self

    def transform(self, X):
        check_is_fitted(self, "caps_")
        if (X[self.count_columns_ + list(DISTANCES)] < 0).any().any():
            raise ValueError("Counts and distances must be nonnegative")
        result = pd.DataFrame(index=X.index)
        for column in self.count_columns_:
            result[column] = np.log1p(X[column].astype(float).clip(upper=self.caps_[column]))
        for column in DISTANCES:
            km = X[column].astype(float) / 1000
            result[f"{column}_km"] = np.log1p(km) if self.distances == "log1p" else km
        if not np.isfinite(result.to_numpy()).all():
            raise ValueError("Model features must be finite and count features must be nonnegative")
        return result

    def get_feature_names_out(self, input_features=None):
        check_is_fitted(self, "feature_names_")
        return np.asarray(self.feature_names_, dtype=object)


def glm(alpha=1.0, *, include_education=True, distances="linear"):
    return Pipeline([
        ("design", CountDesign(include_education=include_education, distances=distances)),
        ("scale", StandardScaler()),
        ("regressor", PoissonRegressor(alpha=alpha, max_iter=2000)),
    ])


def boosting(*, include_education=True):
    return Pipeline([
        ("design", CountDesign(include_education=include_education)),
        ("regressor", HistGradientBoostingRegressor(
            loss="poisson", learning_rate=0.03, max_iter=300, max_depth=3,
            min_samples_leaf=20, random_state=0,
        )),
    ])


def d2(y, prediction):
    """Fraction of Poisson deviance explained; not ordinary R² or a success probability."""
    return d2_tweedie_score(y, prediction, power=1)


def block_ids(xy):
    return np.unique(np.floor(np.asarray(xy) / BLOCK_M).astype(int), axis=0, return_inverse=True)[1].ravel()


def spatial_splits(xy, *, seed=0, n_splits=6, buffer_m=BUFFER_M):
    """Hold out complete blocks and remove train centres <= buffer_m from any test centre.

    Returned positions are local to xy, so the same function can split an outer training
    subset for inner tuning. Every row is a test row exactly once.
    """
    xy = np.asarray(xy, dtype=float)
    blocks = block_ids(xy)
    n_blocks = int(blocks.max()) + 1
    if n_splits < 2 or n_blocks < n_splits:
        raise ValueError("Spatial validation needs at least n_splits distinct blocks")
    folds = (np.random.RandomState(seed).permutation(n_blocks) % n_splits)[blocks]
    splits = []
    for fold in range(n_splits):
        test = np.flatnonzero(folds == fold)
        train = np.flatnonzero(folds != fold)
        distance, _ = cKDTree(xy[test]).query(xy[train])
        train = train[distance > buffer_m]
        if not len(train):
            raise ValueError("The spatial buffer leaves no training rows")
        splits.append((train, test))
    return splits


def select_alpha(features, y, xy, *, seed=0, include_education=True, distances="linear", alphas=ALPHAS):
    """Tune on these rows only, with fold-local caps and a spatial buffer."""
    splits = spatial_splits(xy, seed=seed)
    predictions = {alpha: np.empty(len(features)) for alpha in alphas}
    for train, test in splits:
        # Preprocessing does not depend on alpha. Fit it once per inner training fold,
        # then reuse only those fitted transformations across the candidate penalties.
        preprocessing = Pipeline(glm(include_education=include_education, distances=distances).steps[:-1])
        train_X = preprocessing.fit_transform(features.iloc[train])
        test_X = preprocessing.transform(features.iloc[test])
        for alpha in alphas:
            fit = PoissonRegressor(alpha=alpha, max_iter=2000).fit(train_X, y.iloc[train])
            predictions[alpha][test] = fit.predict(test_X)
    losses = {alpha: mean_poisson_deviance(y, predicted) for alpha, predicted in predictions.items()}
    return min(losses, key=losses.get)


def nested_predictions(features, y, xy, *, seed=0, include_education=True, distances="linear"):
    """Outer predictions with alpha chosen using only the corresponding outer train rows."""
    predicted = np.empty(len(features))
    selected = []
    xy = np.asarray(xy)
    for fold, (train, test) in enumerate(spatial_splits(xy, seed=seed)):
        alpha = select_alpha(features.iloc[train], y.iloc[train], xy[train], seed=seed,
                             include_education=include_education, distances=distances)
        fit = glm(alpha, include_education=include_education, distances=distances)
        fit.fit(features.iloc[train], y.iloc[train])
        predicted[test] = fit.predict(features.iloc[test])
        selected.append({"fold": fold, "alpha": alpha, "train_rows": len(train), "test_rows": len(test)})
    return pd.Series(predicted, index=features.index, name="expected"), selected


def residual_gap(y, expected):
    """NB2 moment scaling of prediction errors, with the Poisson limit if not overdispersed.

    This descriptive score is not a normal z statistic. Out-of-fold prediction errors
    include uncertainty and misspecification of the mean as well as count variation.
    """
    expected = pd.Series(expected, index=y.index, dtype=float)
    if (expected <= 0).any() or not np.isfinite(expected).all():
        raise ValueError("Expected counts must be positive and finite")
    residual = y - expected
    excess = float((residual**2 - expected).sum())
    theta = float((expected**2).sum() / excess) if excess > 0 else np.inf
    gap = residual / np.sqrt(expected + expected**2 / theta)
    return gap, theta


def screening_mask(features, expected):
    return ((features["metro_distance"] <= 500)
            & (features["shops"] + features["services"] >= 10)
            & (expected >= expected.median()))


def top_ten(scores):
    """Rank unrounded scores; use cell id only to break exact ties."""
    shortlist = scores.loc[scores["eligible"] & (scores["score"] < 0)].sort_index()
    shortlist = shortlist.sort_values("score", kind="stable").head(10).copy()
    shortlist.insert(0, "rank", range(1, len(shortlist) + 1))
    return shortlist


def repeated_screening(features_by_radius, xy, *, include_education=True,
                       competitor_columns=("competitors",), seeds=SEEDS, progress=None):
    """Average nested out-of-fold predictions; retain eligibility in >=80% of repeats.

    Each repeat tunes its own models. Frequencies and 10–90% ranges describe sensitivity
    to splitting, not confidence/credible intervals or business success probabilities.
    """
    seeds = tuple(seeds)
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("Provide at least one distinct seed, without duplicates")
    reference = features_by_radius[300].index
    predictions = {radius: [] for radius in RADII}
    split_scores, split_eligible, split_top10, selected_alphas, repeat_d2 = [], [], [], [], []
    for number, seed in enumerate(seeds, start=1):
        gaps, eligible = [], []
        for radius in RADII:
            features = features_by_radius[radius]
            if not features.index.equals(reference):
                raise ValueError("All radii must have the same ordered cell index")
            y = features[list(competitor_columns)].sum(axis=1)
            expected, selected = nested_predictions(features, y, xy, seed=seed,
                                                    include_education=include_education)
            predictions[radius].append(expected)
            gaps.append(residual_gap(y, expected)[0])
            eligible.append(screening_mask(features, expected))
            selected_alphas.extend({"seed": seed, "radius": radius, **row} for row in selected)
            if radius == 300:
                repeat_d2.append(d2(y, expected))
        score = pd.concat(gaps, axis=1).mean(axis=1)
        mask = pd.concat(eligible, axis=1).sum(axis=1) >= 2
        trial = pd.DataFrame({"score": score, "eligible": mask})
        top = top_ten(trial).index
        split_scores.append(score)
        split_eligible.append(mask)
        split_top10.append(pd.Series(reference.isin(top), index=reference))
        if progress is not None:
            progress(number, len(seeds))

    runs, thetas = {}, {}
    for radius in RADII:
        features = features_by_radius[radius]
        y = features[list(competitor_columns)].sum(axis=1)
        expected = pd.concat(predictions[radius], axis=1).mean(axis=1)
        gap, theta = residual_gap(y, expected)
        runs[radius] = pd.DataFrame({"expected": expected, "gap": gap,
                                    "eligible": screening_mask(features, expected)})
        thetas[radius] = theta
    score = pd.concat({r: runs[r]["gap"] for r in RADII}, axis=1).mean(axis=1)
    aggregate_eligible = pd.concat({r: runs[r]["eligible"] for r in RADII}, axis=1).sum(axis=1) >= 2
    eligibility_frequency = pd.concat(split_eligible, axis=1).mean(axis=1)
    top10_frequency = pd.concat(split_top10, axis=1).mean(axis=1)
    eligible = aggregate_eligible & (eligibility_frequency >= MIN_ELIGIBILITY_FREQUENCY)
    expected_repeats = pd.concat(predictions[300], axis=1)
    score_repeats = pd.concat(split_scores, axis=1)
    stability = pd.DataFrame({
        "eligibility_frequency": eligibility_frequency, "top10_frequency": top10_frequency,
        "expected_p10": expected_repeats.quantile(.1, axis=1),
        "expected_p90": expected_repeats.quantile(.9, axis=1),
        "score_p10": score_repeats.quantile(.1, axis=1), "score_p90": score_repeats.quantile(.9, axis=1),
    })
    target = features_by_radius[300][list(competitor_columns)].sum(axis=1)
    return {
        "score": score, "eligible": eligible, "runs": runs, "theta": thetas,
        "stability": stability, "selected_alphas": selected_alphas,
        "d2": d2(target, runs[300]["expected"]), "repeat_d2": repeat_d2,
        "seeds": list(seeds), "buffer_m": BUFFER_M,
    }


def count_effect(fitted, column, before, after):
    """Exact percent contrast for the fitted capped log1p count feature."""
    design = fitted.named_steps["design"]
    position = design.feature_names_.index(column)
    beta = fitted.named_steps["regressor"].coef_[position] / fitted.named_steps["scale"].scale_[position]
    cap = design.caps_[column]
    delta = np.log1p(min(after, cap)) - np.log1p(min(before, cap))
    return 100 * np.expm1(beta * delta)


def distance_effect(fitted, column, delta_km):
    """Percent contrast for a linear distance term, holding other features constant."""
    design = fitted.named_steps["design"]
    if design.distances != "linear":
        raise ValueError("A fixed distance contrast requires a linear distance term")
    position = design.feature_names_.index(column)
    beta = fitted.named_steps["regressor"].coef_[position] / fitted.named_steps["scale"].scale_[position]
    return 100 * np.expm1(beta * delta_km)
