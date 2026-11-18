"""Build model features from the national table using only past information.

Every value for a month uses data up to that month only. Anomalies compare a
month with the same calendar month in the previous few years, so no future
year leaks into "normal", and slow drifts (like NDVI greening over the
years) are absorbed by the rolling window.
"""

import pandas as pd

import config

ANOMALY_COLUMNS = ["ndvi", "rainfall_mm", "tmax_c"]


def past_anomaly(series: pd.Series, calendar_month: pd.Series) -> pd.Series:
    """Value minus the mean of the same calendar month in the previous years."""
    previous = series.groupby(calendar_month).transform(
        lambda same_month: same_month.shift(1)
        .rolling(config.ANOMALY_YEARS, min_periods=config.MIN_HISTORY_YEARS)
        .mean()
    )
    return series - previous


def nearby_anomaly(series: pd.Series, groups: list[pd.Series]) -> pd.Series:
    """Value minus the mean of the same month in the years either side of it.

    For charts only: it looks at later years too, so a model must not use it.
    Comparing with nearby years stops a slow trend from making every early
    year look bad and every recent year look good. Rows must be in time order
    within each group, which should include the calendar month.
    """

    def compare(values: pd.Series) -> pd.Series:
        window = values.rolling(2 * config.NEARBY_YEARS + 1, center=True, min_periods=1)
        others_total = window.sum() - values
        others_count = window.count() - 1
        return values - others_total / others_count

    return series.groupby(groups).transform(compare)


def crop_features(data: pd.DataFrame) -> pd.DataFrame:
    """Build the features for one crop (rows must be in month order)."""
    features = pd.DataFrame(
        {
            "crop": data["crop"],
            "month": data["month"],
            "calendar_month": data["calendar_month"],
            "wpi": data["wpi"],
        }
    )
    for column in ANOMALY_COLUMNS:
        features[f"{column}_anomaly"] = past_anomaly(
            data[column], data["calendar_month"]
        )

    features["price_change"] = data["wpi"].pct_change() * 100
    features["food_inflation"] = data["food_articles"].pct_change() * 100
    features["stock_change"] = data["stock_lakh_t"].pct_change(12) * 100
    features["msp_change"] = data["msp_rs_per_qtl"].pct_change(12) * 100
    features["export_ban"] = data["export_ban"]
    features["stock_limit"] = data["stock_limit"]
    features["rice_index"] = (data["wpi_series"] == "2004-05 linked (rice)").astype(int)
    return features


def main() -> None:
    national = pd.read_csv(config.NATIONAL_CSV)
    national["calendar_month"] = pd.to_datetime(national["month"]).dt.month
    national = national.sort_values(["crop", "month"])

    features = pd.concat(
        [crop_features(data) for _, data in national.groupby("crop")],
        ignore_index=True,
    )
    # Drop the first years, which have no past to compare with.
    features = features.dropna().reset_index(drop=True)

    features.to_csv(config.FEATURES_CSV, index=False, lineterminator="\n")
    print(
        f"Saved {len(features)} rows to {config.FEATURES_CSV} "
        f"({features['month'].min()} to {features['month'].max()})"
    )


if __name__ == "__main__":
    main()
