"""Extract monthly daytime land surface temperature over cropland for every district.

NDVI shows how green crops are, but heat can damage the grain while the
leaves stay green (as in the March 2022 heatwave), so temperature is
extracted as a separate signal.
"""

import ee
import pandas as pd

import config
from earth_engine import call_with_retry, get_districts_in_states, init_earth_engine
from extract_ndvi import cropland_mask

# MODIS 8-day land surface temperature from the Terra and Aqua satellites.
LST_COLLECTIONS = ["MODIS/061/MOD11A2", "MODIS/061/MYD11A2"]
LST_BAND = "LST_Day_1km"
LST_SCALE_METERS = 1000

# Stored in kelvin multiplied by 50.
LST_SCALE_FACTOR = 0.02
KELVIN_TO_CELSIUS = 273.15


def monthly_lst(month_start: pd.Timestamp, cropland: ee.Image) -> ee.Image:
    """Mean daytime surface temperature (scaled kelvin) over cropland for a month."""
    month_end = month_start + pd.DateOffset(months=1)
    collection = ee.ImageCollection(LST_COLLECTIONS[0])
    for name in LST_COLLECTIONS[1:]:
        collection = collection.merge(ee.ImageCollection(name))
    # Cloudy pixels have no value in this product, so they are already left out.
    return (
        collection.filterDate(
            month_start.strftime("%Y-%m-%d"), month_end.strftime("%Y-%m-%d")
        )
        .select(LST_BAND)
        .mean()
        .updateMask(cropland)
    )


def district_lst_for_month(
    districts: ee.FeatureCollection, cropland: ee.Image, month_start: pd.Timestamp
) -> list[dict]:
    """Return each district's mean daytime cropland temperature (deg C) for a month."""
    stats = monthly_lst(month_start, cropland).reduceRegions(
        collection=districts, reducer=ee.Reducer.mean(), scale=LST_SCALE_METERS
    )
    stats = stats.select(["GAUL1_NAME", "GAUL2_NAME", "mean"], None, False).getInfo()

    rows = []
    for feature in stats["features"]:
        props = feature["properties"]
        value = props.get("mean")
        rows.append(
            {
                "state": props["GAUL1_NAME"],
                "district": props["GAUL2_NAME"],
                "month": month_start.strftime("%Y-%m"),
                "lst_day_c": (
                    round(value * LST_SCALE_FACTOR - KELVIN_TO_CELSIUS, 2)
                    if value is not None
                    else None
                ),
            }
        )
    return rows


def main() -> None:
    init_earth_engine(config.GEE_PROJECT)

    districts = get_districts_in_states(config.COUNTRY, config.STUDY_STATES)
    cropland = cropland_mask()
    months = pd.date_range(
        config.START_DATE, config.END_DATE, freq="MS", inclusive="left"
    )
    print(
        f"Extracting land surface temperature for {len(config.STUDY_STATES)} "
        f"states, {len(months)} months"
    )

    all_rows = []
    failed_months = []
    for month_start in months:
        rows = call_with_retry(district_lst_for_month, districts, cropland, month_start)
        if rows is None:
            failed_months.append(f"{month_start:%Y-%m}")
        else:
            all_rows.extend(rows)

    # Don't overwrite a good file with an incomplete one.
    if failed_months:
        raise SystemExit(f"Not saved, failed months: {', '.join(failed_months)}")

    temperature = pd.DataFrame(all_rows).sort_values(["state", "district", "month"])
    temperature.to_csv(config.TEMPERATURE_CSV, index=False, lineterminator="\n")
    print(
        f"Saved {len(temperature)} rows to {config.TEMPERATURE_CSV} "
        f"({temperature['state'].nunique()} states, {len(months)} months)"
    )


if __name__ == "__main__":
    main()
