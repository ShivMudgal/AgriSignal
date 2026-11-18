"""Extract monthly air temperature (mean and hottest) for every district.

NDVI shows how green crops are, but heat can damage the grain while the
leaves stay green (as in the March 2022 heatwave), so temperature is a
separate signal. It comes from the ERA5-Land reanalysis rather than the
MODIS satellites, whose land temperature drifts cooler after 2020 as their
orbits change the time of day they pass over.
"""

import ee
import pandas as pd

import config
from earth_engine import call_with_retry, get_districts_in_states, init_earth_engine

ERA5_LAND_MONTHLY = "ECMWF/ERA5_LAND/MONTHLY_AGGR"
BANDS = {"temperature_2m": "tmean_c", "temperature_2m_max": "tmax_c"}

# The ERA5-Land grid is about 11 km. Sampling at 5 km makes sure even small
# districts get a value.
ERA5_SCALE_METERS = 5000

KELVIN_TO_CELSIUS = 273.15


def district_temperature_for_month(
    districts: ee.FeatureCollection, month_start: pd.Timestamp
) -> list[dict]:
    """Return each district's mean and maximum air temperature (deg C) for a month."""
    month_end = month_start + pd.DateOffset(months=1)
    image = (
        ee.ImageCollection(ERA5_LAND_MONTHLY)
        .filterDate(month_start.strftime("%Y-%m-%d"), month_end.strftime("%Y-%m-%d"))
        .first()
        .select(list(BANDS))
    )
    stats = image.reduceRegions(
        collection=districts, reducer=ee.Reducer.mean(), scale=ERA5_SCALE_METERS
    )
    stats = stats.select(["GAUL1_NAME", "GAUL2_NAME"] + list(BANDS), None, False)

    rows = []
    for feature in stats.getInfo()["features"]:
        props = feature["properties"]
        row = {
            "state": props["GAUL1_NAME"],
            "district": props["GAUL2_NAME"],
            "month": month_start.strftime("%Y-%m"),
        }
        for band, column in BANDS.items():
            value = props.get(band)
            row[column] = (
                round(value - KELVIN_TO_CELSIUS, 2) if value is not None else None
            )
        rows.append(row)
    return rows


def main() -> None:
    init_earth_engine(config.GEE_PROJECT)

    districts = get_districts_in_states(config.COUNTRY, config.STUDY_STATES)
    months = pd.date_range(
        config.START_DATE, config.END_DATE, freq="MS", inclusive="left"
    )
    print(
        f"Extracting temperature for {len(config.STUDY_STATES)} states, "
        f"{len(months)} months"
    )

    all_rows = []
    failed_months = []
    for month_start in months:
        rows = call_with_retry(district_temperature_for_month, districts, month_start)
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
