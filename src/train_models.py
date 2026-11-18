"""Train and test models that predict whether prices rise in the next 1-3 months.

Testing is walk-forward: for every month from EVAL_START the models are
retrained on all earlier months whose outcome was already known, and then
predict that month. This is how the models would have done if used live.
"""

import numpy as np
import pandas as pd
from scipy.stats import binomtest, wilcoxon
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

import config
from baselines import RULES, baseline_predictions, future_up

HORIZONS = [1, 2, 3]

BASE_FEATURES = ["month_sin", "month_cos", "price_change", "price_change_lag1"]
FEATURE_SETS = {
    "base": BASE_FEATURES,
    "base_ndvi": BASE_FEATURES + ["ndvi_anomaly", "ndvi_anomaly_lag1"],
}


def make_model(name: str):
    """Return a fresh, untrained model."""
    if name == "logistic":
        return make_pipeline(StandardScaler(), LogisticRegression(C=1.0))
    # Small, slow-learning trees, because there are only a few hundred months.
    return XGBClassifier(
        n_estimators=100,
        max_depth=2,
        learning_rate=0.05,
        subsample=0.8,
        min_child_weight=5,
        random_state=0,
        verbosity=0,
    )


def add_model_inputs(data: pd.DataFrame) -> pd.DataFrame:
    """Add the calendar as a circle (so December sits next to January) and lags."""
    data = data.copy()
    angle = 2 * np.pi * (data["calendar_month"] - 1) / 12
    data["month_sin"] = np.sin(angle)
    data["month_cos"] = np.cos(angle)
    data["price_change_lag1"] = data["price_change"].shift(1)
    data["ndvi_anomaly_lag1"] = data["ndvi_anomaly"].shift(1)
    return data


def walk_forward(data: pd.DataFrame, months_ahead: int) -> pd.DataFrame:
    """Predict every month from EVAL_START, retraining before each prediction."""
    outcome = future_up(data["wpi"], months_ahead)
    rows = []
    for position in np.flatnonzero(
        (data["month"] >= config.EVAL_START) & outcome.notna()
    ):
        # Only months whose outcome was settled by now can be used for training.
        train = data.iloc[: position - months_ahead + 1]
        train_outcome = outcome.iloc[: position - months_ahead + 1]
        row = {"month": data["month"].iloc[position], "outcome": outcome.iloc[position]}
        for set_name, columns in FEATURE_SETS.items():
            usable = train[columns].notna().all(axis=1)
            for model_name in ["logistic", "xgboost"]:
                model = make_model(model_name)
                model.fit(train.loc[usable, columns], train_outcome[usable])
                up_probability = model.predict_proba(data[columns].iloc[[position]])[
                    0, 1
                ]
                row[f"{model_name}_{set_name}"] = float(up_probability >= 0.5)
                row[f"{model_name}_{set_name}_prob"] = round(float(up_probability), 4)
        rows.append(row)
    return pd.DataFrame(rows)


def mcnemar_p(model_right: pd.Series, baseline_right: pd.Series) -> float:
    """Exact McNemar test: are the months where the two disagree a fair coin flip?"""
    model_only = int((model_right & ~baseline_right).sum())
    baseline_only = int((~model_right & baseline_right).sum())
    if model_only + baseline_only == 0:
        return 1.0
    return binomtest(model_only, model_only + baseline_only, 0.5).pvalue


def brier_score(probability: pd.Series, outcome: pd.Series) -> pd.Series:
    """Squared error of a probability forecast, per month (lower is better)."""
    return (probability - outcome) ** 2


def summarise(predictions: pd.DataFrame) -> pd.DataFrame:
    """Accuracy against the best rule, and probability quality against the calendar."""
    model_columns = [
        f"{model}_{feature_set}"
        for feature_set in FEATURE_SETS
        for model in ["logistic", "xgboost"]
    ]
    rows = []
    for (crop, months_ahead), data in predictions.groupby(["crop", "months_ahead"]):
        rule_accuracy = {rule: (data[rule] == data["outcome"]).mean() for rule in RULES}
        best_rule = max(rule_accuracy, key=rule_accuracy.get)
        baseline_right = data[best_rule] == data["outcome"]
        calendar_brier = brier_score(data["calendar_prob"], data["outcome"])
        for column in model_columns:
            model_right = data[column] == data["outcome"]
            model_brier = brier_score(data[f"{column}_prob"], data["outcome"])
            rows.append(
                {
                    "crop": crop,
                    "months_ahead": months_ahead,
                    "model": column,
                    "accuracy": model_right.mean(),
                    "best_rule": best_rule,
                    "rule_accuracy": rule_accuracy[best_rule],
                    "difference": model_right.mean() - rule_accuracy[best_rule],
                    "mcnemar_p": mcnemar_p(model_right, baseline_right),
                    "brier": model_brier.mean(),
                    "calendar_brier": calendar_brier.mean(),
                    "brier_p": wilcoxon(model_brier, calendar_brier).pvalue,
                    "months": len(data),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    features = pd.read_csv(config.FEATURES_CSV)
    tables = []
    for crop, data in features.groupby("crop"):
        data = add_model_inputs(data.sort_values("month").reset_index(drop=True))
        for months_ahead in HORIZONS:
            print(f"  {crop}, {months_ahead} month(s) ahead")
            models = walk_forward(data, months_ahead)
            rules = baseline_predictions(data, months_ahead)
            rules = rules[rules["crop"] == crop].drop(columns=["outcome"])
            tables.append(models.merge(rules, on="month"))

    predictions = pd.concat(tables, ignore_index=True)
    predictions.to_csv(config.PREDICTIONS_CSV, index=False, lineterminator="\n")

    summary = summarise(predictions)
    pd.set_option("display.width", 160)
    print(summary.round(3).to_string(index=False))
    print(f"Saved {len(predictions)} predictions to {config.PREDICTIONS_CSV}")


if __name__ == "__main__":
    main()
