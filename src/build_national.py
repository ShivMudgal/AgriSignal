"""Build one national monthly table per crop: crop conditions, prices and policy."""

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
    r.rainfall_mm,
    t.lst_day_c
FROM ndvi AS n
JOIN rainfall AS r ON r.district_id = n.district_id AND r.month = n.month
JOIN temperature AS t ON t.district_id = n.district_id AND t.month = n.month
JOIN districts AS d ON d.district_id = n.district_id
"""

# Which districts feed each crop's national series.
CROP_STATE_FLAGS = {"wheat": "in_wheat_states", "paddy": "in_rice_states"}

# Which central pool stock goes with each crop (paddy is stored as rice).
CROP_STOCK_COLUMNS = {"wheat": "wheat_lakh_t", "paddy": "rice_lakh_t"}

# Economy-wide price indices used alongside each crop's own price.
OTHER_PRICE_ITEMS = ["all_commodities", "food_articles", "diesel"]

# Policy flags: an event counts if its name contains the key.
POLICY_FLAGS = {"export_ban": "export_ban", "stock_limit": "stock_limit"}


def load_district_months(engine: Engine) -> pd.DataFrame:
    """Read NDVI, rainfall and temperature for every district and month."""
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


def crop_conditions(data: pd.DataFrame) -> pd.DataFrame:
    """National NDVI, rainfall and temperature per crop and month."""
    tables = []
    for crop, flag in CROP_STATE_FLAGS.items():
        crop_data = data[data[flag].astype(bool)]
        table = pd.DataFrame(
            {
                "ndvi": weighted_monthly_mean(crop_data, "ndvi").round(4),
                "rainfall_mm": weighted_monthly_mean(crop_data, "rainfall_mm").round(1),
                "lst_day_c": weighted_monthly_mean(crop_data, "lst_day_c").round(2),
                "districts": crop_data.groupby("month")["district_id"].nunique(),
            }
        )
        table["crop"] = crop
        tables.append(table.reset_index())

    conditions = pd.concat(tables, ignore_index=True)
    conditions["month"] = conditions["month"].astype(str).str[:7]
    return conditions


def add_prices(national: pd.DataFrame, wpi: pd.DataFrame) -> pd.DataFrame:
    """Add each crop's own WPI and the economy-wide indices."""
    wpi = wpi.assign(month=wpi["month"].astype(str).str[:7])
    crop_prices = wpi.rename(columns={"item": "crop", "series": "wpi_series"})
    national = national.merge(crop_prices, on=["crop", "month"])

    other_prices = wpi[wpi["item"].isin(OTHER_PRICE_ITEMS)].pivot(
        index="month", columns="item", values="wpi"
    )
    return national.join(other_prices, on="month")


def add_stocks(national: pd.DataFrame, stocks: pd.DataFrame) -> pd.DataFrame:
    """Add the central pool stock of each crop on the 1st of the month."""
    stocks = stocks.assign(month=stocks["month"].astype(str).str[:7])
    long = pd.concat(
        [
            stocks[["month", column]]
            .rename(columns={column: "stock_lakh_t"})
            .assign(crop=crop)
            for crop, column in CROP_STOCK_COLUMNS.items()
        ]
    )
    return national.merge(long, on=["crop", "month"], how="left")


def add_msp(national: pd.DataFrame, msp: pd.DataFrame) -> pd.DataFrame:
    """Add the MSP in force: the latest season that started on or before the month."""
    msp = msp.assign(season_start=pd.to_datetime(msp["season_start"]))
    national = national.assign(date=pd.to_datetime(national["month"]))
    parts = []
    for crop, part in national.groupby("crop"):
        crop_msp = msp[msp["crop"] == crop].sort_values("season_start")
        part = pd.merge_asof(
            part.sort_values("date"),
            crop_msp[["season_start", "msp_rs_per_qtl"]],
            left_on="date",
            right_on="season_start",
        )
        parts.append(part.drop(columns="season_start"))
    return pd.concat(parts, ignore_index=True).drop(columns="date")


def add_policy_flags(national: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Flag months in which an export ban or stock limit was in force for any day."""
    month_start = pd.to_datetime(national["month"])
    month_end = month_start + pd.offsets.MonthEnd(0)
    for flag, key in POLICY_FLAGS.items():
        active = pd.Series(False, index=national.index)
        for event in events[events["event"].str.contains(key)].itertuples():
            start = pd.Timestamp(event.start_date)
            end = pd.Timestamp(event.end_date) if pd.notna(event.end_date) else None
            in_force = (national["crop"] == event.crop) & (month_end >= start)
            if end is not None:
                in_force &= month_start <= end
            active |= in_force
        national[flag] = active.astype(int)
    return national


def main() -> None:
    engine = connect(config.DATABASE_URL)
    data = add_farmland_weight(load_district_months(engine))

    national = crop_conditions(data)
    national = add_prices(national, pd.read_sql("SELECT * FROM wpi", engine))
    national = add_stocks(national, pd.read_sql("SELECT * FROM fci_stocks", engine))
    national = add_msp(national, pd.read_sql("SELECT * FROM msp", engine))
    national = add_policy_flags(
        national, pd.read_sql("SELECT * FROM policy_events", engine)
    )

    columns = ["crop", "month", "ndvi", "rainfall_mm", "lst_day_c", "wpi"]
    columns += ["wpi_series"] + OTHER_PRICE_ITEMS
    columns += ["stock_lakh_t", "msp_rs_per_qtl"] + list(POLICY_FLAGS)
    columns += ["districts"]
    national = national[columns].sort_values(["crop", "month"])

    if national.drop(columns="wpi_series").isna().any().any():
        raise SystemExit("The national table has missing values.")
    national.to_csv(config.NATIONAL_CSV, index=False, lineterminator="\n")
    print(f"Saved {len(national)} rows to {config.NATIONAL_CSV}")
    print(
        national.groupby("crop")[["ndvi", "lst_day_c", "stock_lakh_t"]].mean().round(2)
    )


if __name__ == "__main__":
    main()
