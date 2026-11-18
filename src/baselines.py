"""Simple rules a model has to beat at predicting whether prices go up.

Each rule is run month by month and only uses outcomes that were already
known at that point, the same way a model will be tested.
"""

import pandas as pd

import config


def future_up(wpi: pd.Series, months_ahead: int) -> pd.Series:
    """1 if the price is higher months_ahead later, 0 if not, NaN if unknown."""
    change = wpi.shift(-months_ahead) - wpi
    return (change > 0).astype(float).where(change.notna())


def known_outcomes(outcome: pd.Series, position: int, months_ahead: int) -> pd.Series:
    """Outcomes that were already settled at a given month."""
    return outcome.iloc[: max(position - months_ahead + 1, 0)].dropna()


def always_up_rule(outcome: pd.Series, months_ahead: int) -> pd.Series:
    """Predict whichever direction has been more common so far."""
    predictions = []
    for position in range(len(outcome)):
        past = known_outcomes(outcome, position, months_ahead)
        predictions.append(float(past.mean() >= 0.5) if len(past) else 1.0)
    return pd.Series(predictions, index=outcome.index)


def calendar_probability(
    outcome: pd.Series, calendar_month: pd.Series, months_ahead: int
) -> pd.Series:
    """Share of past years in which the price rose from this calendar month."""
    probabilities = []
    for position in range(len(outcome)):
        past = known_outcomes(outcome, position, months_ahead)
        same_month = past[
            calendar_month.loc[past.index] == calendar_month.iloc[position]
        ]
        source = same_month if len(same_month) else past
        probabilities.append(source.mean() if len(source) else 1.0)
    return pd.Series(probabilities, index=outcome.index)


def calendar_rule(
    outcome: pd.Series, calendar_month: pd.Series, months_ahead: int
) -> pd.Series:
    """Predict the direction most common for this calendar month so far."""
    probability = calendar_probability(outcome, calendar_month, months_ahead)
    return (probability >= 0.5).astype(float)


def momentum_rule(wpi: pd.Series, months_ahead: int) -> pd.Series:
    """Predict the same direction as the price moved over the last months_ahead."""
    return (wpi > wpi.shift(months_ahead)).astype(float)


RULES = ["always_up", "calendar", "momentum"]


def baseline_predictions(
    features: pd.DataFrame, months_ahead: int, start: str = config.EVAL_START
) -> pd.DataFrame:
    """Each rule's prediction and the actual outcome for every tested month."""
    tables = []
    for crop, data in features.groupby("crop"):
        data = data.sort_values("month").reset_index(drop=True)
        outcome = future_up(data["wpi"], months_ahead)
        table = pd.DataFrame(
            {
                "crop": crop,
                "months_ahead": months_ahead,
                "month": data["month"],
                "outcome": outcome,
                "always_up": always_up_rule(outcome, months_ahead),
                "calendar": calendar_rule(
                    outcome, data["calendar_month"], months_ahead
                ),
                "momentum": momentum_rule(data["wpi"], months_ahead),
                "calendar_prob": calendar_probability(
                    outcome, data["calendar_month"], months_ahead
                ),
            }
        )
        tables.append(table[(table["month"] >= start) & outcome.notna()])
    return pd.concat(tables, ignore_index=True)


def baseline_accuracy(
    features: pd.DataFrame, months_ahead: int, start: str = config.EVAL_START
) -> pd.DataFrame:
    """Accuracy of every rule for each crop on months from start onwards."""
    predictions = baseline_predictions(features, months_ahead, start)
    rows = []
    for crop, data in predictions.groupby("crop"):
        for rule in RULES:
            rows.append(
                {
                    "crop": crop,
                    "months_ahead": months_ahead,
                    "rule": rule,
                    "accuracy": (data[rule] == data["outcome"]).mean(),
                    "months_tested": len(data),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    features = pd.read_csv(config.FEATURES_CSV)
    results = pd.concat(
        [baseline_accuracy(features, months_ahead) for months_ahead in [1, 2, 3]]
    )
    table = results.pivot_table(
        index=["crop", "months_ahead"], columns="rule", values="accuracy"
    )
    table["best_rule"] = table.idxmax(axis=1)
    table["best_accuracy"] = table[RULES].max(axis=1)
    print(f"Directional accuracy on months from {config.EVAL_START}")
    print(table.round(3))
    print(
        f"Months tested per crop: {results['months_tested'].min()} to "
        f"{results['months_tested'].max()}"
    )


if __name__ == "__main__":
    main()
