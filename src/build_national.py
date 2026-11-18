"""Combine district data into one national monthly series per crop."""

import pandas as pd
from sqlalchemy import Engine

import config
from build_database import connect

DISTRICT_MONTH_QUERY = """
SELECT
    d.district_id,
    d.in_wheat_states,
    d.in_rice_states,
    n.month,
    n.ndvi,
    n.pixel_count,
    r.rainfall_mm
FROM ndvi AS n
JOIN rainfall AS r ON r.district_id = n.district_id AND r.month = n.month
JOIN districts AS d ON d.district_id = n.district_id
"""

# Which districts feed each crop's national series.
CROP_STATE_FLAGS = {"wheat": "in_wheat_states", "paddy": "in_rice_states"}


def load_district_months(engine: Engine) -> pd.DataFrame:
    """Read NDVI and rainfall for every district and month from the database."""
    return pd.read_sql(DISTRICT_MONTH_QUERY, engine)


def add_farmland_weight(data: pd.DataFrame) -> pd.DataFrame:
    """Weight each district by its median clear cropland pixels (its farm size)."""
    weights = data.groupby("district_id")["pixel_count"].median().rename("weight")
    return data.join(weights, on="district_id")


def weighted_monthly_mean(data: pd.DataFrame, column: str) -> pd.Series:
    """Return the weighted average of a column for each month."""
    weighted_sum = (data[column] * data["weight"]).groupby(data["month"]).sum()
    total_weight = data.groupby("month")["weight"].sum()
    return weighted_sum / total_weight


def national_series(data: pd.DataFrame, wpi: pd.DataFrame) -> pd.DataFrame:
    """Return one row per crop and month with national NDVI, rainfall and WPI."""
    tables = []
    for crop, flag in CROP_STATE_FLAGS.items():
        crop_data = data[data[flag].astype(bool)]
        table = pd.DataFrame(
            {
                "ndvi": weighted_monthly_mean(crop_data, "ndvi").round(4),
                "rainfall_mm": weighted_monthly_mean(crop_data, "rainfall_mm").round(1),
                "districts": crop_data.groupby("month")["district_id"].nunique(),
            }
        )
        table["crop"] = crop
        tables.append(table.reset_index())

    national = pd.concat(tables, ignore_index=True)
    national["month"] = national["month"].astype(str).str[:7]
    national = national.merge(wpi[["crop", "month", "wpi"]], on=["crop", "month"])
    return national[["crop", "month", "ndvi", "rainfall_mm", "wpi", "districts"]]


def main() -> None:
    engine = connect(config.DATABASE_URL)
    data = add_farmland_weight(load_district_months(engine))
    wpi = pd.read_csv(config.WPI_CSV)

    national = national_series(data, wpi)
    national.to_csv(config.NATIONAL_CSV, index=False, lineterminator="\n")
    print(f"Saved {len(national)} rows to {config.NATIONAL_CSV}")
    print(national.groupby("crop")[["ndvi", "rainfall_mm", "wpi"]].mean().round(3))


if __name__ == "__main__":
    main()
