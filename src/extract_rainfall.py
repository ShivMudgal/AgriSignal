"""Extract monthly total rainfall for every district in the study states."""

import ee
import pandas as pd

import config
from earth_engine import call_with_retry, get_districts_in_states, init_earth_engine

# CHIRPS v3 daily rainfall in mm/day, on a grid of about 5.5 km.
CHIRPS_DAILY_COLLECTION = "UCSB-CHC/CHIRPS/V3/DAILY_SAT"
CHIRPS_SCALE_METERS = 5566


def district_rainfall_for_month(
    districts: ee.FeatureCollection, month_start: pd.Timestamp
) -> list[dict]:
    """Return each district's average total rainfall (mm) for one month."""
    month_end = month_start + pd.DateOffset(months=1)

    monthly_total = (
        ee.ImageCollection(CHIRPS_DAILY_COLLECTION)
        .filterDate(month_start.strftime("%Y-%m-%d"), month_end.strftime("%Y-%m-%d"))
        .select("precipitation")
        .sum()
    )

    stats = monthly_total.reduceRegions(
        collection=districts,
        reducer=ee.Reducer.mean(),
        scale=CHIRPS_SCALE_METERS,
    )
    # Drop the district shapes before downloading; we only need the numbers.
    stats = stats.select(["GAUL1_NAME", "GAUL2_NAME", "mean"], None, False).getInfo()

    rows = []
    for feature in stats["features"]:
        props = feature["properties"]
        rainfall = props.get("mean")
        rows.append(
            {
                "state": props["GAUL1_NAME"],
                "district": props["GAUL2_NAME"],
                "month": month_start.strftime("%Y-%m"),
                "rainfall_mm": round(rainfall, 1) if rainfall is not None else None,
            }
        )
    return rows


def main() -> None:
    init_earth_engine(config.GEE_PROJECT)

    districts = get_districts_in_states(config.COUNTRY, config.STUDY_STATES)
    months = pd.date_range(
        config.START_DATE, config.END_DATE, freq="MS", inclusive="left"
    )
    print(
        f"Extracting rainfall for {len(config.STUDY_STATES)} states, "
        f"{len(months)} months"
    )

    all_rows = []
    failed_months = []
    for month_start in months:
        rows = call_with_retry(district_rainfall_for_month, districts, month_start)
        if rows is None:
            failed_months.append(f"{month_start:%Y-%m}")
        else:
            all_rows.extend(rows)

    # Don't overwrite a good file with an incomplete one.
    if failed_months:
        raise SystemExit(f"Not saved, failed months: {', '.join(failed_months)}")

    rainfall = pd.DataFrame(all_rows).sort_values(["state", "district", "month"])
    config.RAINFALL_CSV.parent.mkdir(parents=True, exist_ok=True)
    rainfall.to_csv(config.RAINFALL_CSV, index=False)
    print(
        f"Saved {len(rainfall)} rows to {config.RAINFALL_CSV} "
        f"({rainfall['state'].nunique()} states, {len(months)} months)"
    )


if __name__ == "__main__":
    main()
