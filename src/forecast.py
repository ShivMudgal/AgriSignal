"""Forecast whether prices rise in the 1-3 months after the data ends.

For each crop and horizon this picks the model with the best walk-forward
Brier score, retrains it on every month with a known outcome, and predicts
from the last month. The track record is saved next to the forecast so the
dashboard can show both.
"""

import pandas as pd

import config
from baselines import future_up
from train_models import FEATURE_SETS, HORIZONS, add_model_inputs, make_model, summarise


def best_models(predictions: pd.DataFrame) -> pd.DataFrame:
    """The model with the lowest walk-forward Brier score per crop and horizon."""
    summary = summarise(predictions)
    best = summary.loc[summary.groupby(["crop", "months_ahead"])["brier"].idxmin()]
    return best.set_index(["crop", "months_ahead"])


def forecast_one(data: pd.DataFrame, months_ahead: int, model_column: str) -> float:
    """Train on all settled months and return the chance of a rise from the last month."""
    model_name, feature_set = model_column.split("_", 1)
    columns = FEATURE_SETS[feature_set]
    outcome = future_up(data["wpi"], months_ahead)
    usable = outcome.notna() & data[columns].notna().all(axis=1)

    model = make_model(model_name)
    model.fit(data.loc[usable, columns], outcome[usable])
    return float(model.predict_proba(data[columns].iloc[[-1]])[0, 1])


def main() -> None:
    features = pd.read_csv(config.FEATURES_CSV)
    best = best_models(pd.read_csv(config.PREDICTIONS_CSV))

    rows = []
    for crop, data in features.groupby("crop"):
        data = add_model_inputs(data.sort_values("month").reset_index(drop=True))
        last_month = pd.Period(data["month"].iloc[-1], "M")
        for months_ahead in HORIZONS:
            record = best.loc[(crop, months_ahead)]
            rows.append(
                {
                    "crop": crop,
                    "months_ahead": months_ahead,
                    "from_month": str(last_month),
                    "to_month": str(last_month + months_ahead),
                    "model": record["model"],
                    "probability_up": round(
                        forecast_one(data, months_ahead, record["model"]), 3
                    ),
                    "past_accuracy": round(record["accuracy"], 3),
                    "best_rule": record["best_rule"],
                    "rule_accuracy": round(record["rule_accuracy"], 3),
                }
            )

    forecast = pd.DataFrame(rows)
    forecast.to_csv(config.FORECAST_CSV, index=False, lineterminator="\n")
    print(forecast.to_string(index=False))


if __name__ == "__main__":
    main()
