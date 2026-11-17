"""Extract monthly mean cropland NDVI for every district in the main crop states."""

import time
from pathlib import Path

import ee
import pandas as pd

import config
from earth_engine import (
    MODIS_NDVI_COLLECTION,
    NDVI_SCALE_FACTOR,
    get_districts,
    init_earth_engine,
)

WORLDCOVER = "ESA/WorldCover/v200"
WORLDCOVER_CROPLAND = 40

# MODIS SummaryQA: 0 = good, 1 = marginal, 2 = snow/ice, 3 = cloudy.
MAX_SUMMARY_QA = 1

MODIS_SCALE_METERS = 250

MAX_ATTEMPTS = 3
RETRY_WAIT_SECONDS = 10


def cropland_mask() -> ee.Image:
    """Return an image that is 1 on cropland pixels and 0 elsewhere."""
    worldcover = ee.ImageCollection(WORLDCOVER).first()
    return worldcover.eq(WORLDCOVER_CROPLAND)


def clean_ndvi(image: ee.Image, cropland: ee.Image) -> ee.Image:
    """Keep NDVI only for clear (good or marginal quality) cropland pixels."""
    clear = image.select("SummaryQA").lte(MAX_SUMMARY_QA)
    return image.select("NDVI").updateMask(clear).updateMask(cropland)


def district_ndvi_for_month(
    districts: ee.FeatureCollection, cropland: ee.Image, month_start: pd.Timestamp
) -> list[dict]:
    """Return mean NDVI and clear pixel count for each district in one month."""
    month_end = month_start + pd.DateOffset(months=1)

    monthly_ndvi = (
        ee.ImageCollection(MODIS_NDVI_COLLECTION)
        .filterDate(month_start.strftime("%Y-%m-%d"), month_end.strftime("%Y-%m-%d"))
        .map(lambda image: clean_ndvi(image, cropland))
        .mean()
    )

    # One server-side call computes the stats for every district at once.
    stats = monthly_ndvi.reduceRegions(
        collection=districts,
        reducer=ee.Reducer.mean().combine(ee.Reducer.count(), sharedInputs=True),
        scale=MODIS_SCALE_METERS,
    ).getInfo()

    rows = []
    for feature in stats["features"]:
        props = feature["properties"]
        mean_value = props.get("mean")
        rows.append(
            {
                "state": props["GAUL1_NAME"],
                "district": props["GAUL2_NAME"],
                "month": month_start.strftime("%Y-%m"),
                "ndvi": (
                    round(mean_value * NDVI_SCALE_FACTOR, 4)
                    if mean_value is not None
                    else None
                ),
                "pixel_count": props.get("count", 0),
            }
        )
    return rows


def fetch_with_retry(
    districts: ee.FeatureCollection, cropland: ee.Image, month_start: pd.Timestamp
) -> list[dict] | None:
    """Fetch one month, retrying on Earth Engine errors. Returns None if all tries fail."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return district_ndvi_for_month(districts, cropland, month_start)
        except ee.EEException as error:
            print(f"    {month_start:%Y-%m} attempt {attempt} failed: {error}")
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_WAIT_SECONDS)
    return None


def state_csv_path(state: str) -> Path:
    """Return the output file for one state, e.g. data/raw/ndvi/uttar_pradesh.csv."""
    return config.NDVI_STATE_DIR / f"{state.lower().replace(' ', '_')}.csv"


def extract_state(state: str, cropland: ee.Image, months: pd.DatetimeIndex) -> bool:
    """Extract all months for one state and save them. Returns True on success."""
    districts = get_districts(config.COUNTRY, state)
    start = time.time()

    all_rows = []
    failed_months = []
    for month_start in months:
        rows = fetch_with_retry(districts, cropland, month_start)
        if rows is None:
            failed_months.append(f"{month_start:%Y-%m}")
        else:
            all_rows.extend(rows)

    # Only save complete states, so a re-run will retry the incomplete ones.
    if failed_months:
        print(f"  {state}: NOT saved, failed months: {', '.join(failed_months)}")
        return False

    ndvi = pd.DataFrame(all_rows).sort_values(["district", "month"])
    ndvi.to_csv(state_csv_path(state), index=False)
    minutes = (time.time() - start) / 60
    print(
        f"  {state}: {ndvi['district'].nunique()} districts, "
        f"{len(ndvi)} rows ({minutes:.1f} min)"
    )
    return True


def combine_states() -> pd.DataFrame:
    """Combine every saved state file into one table."""
    files = sorted(config.NDVI_STATE_DIR.glob("*.csv"))
    return pd.concat([pd.read_csv(file) for file in files], ignore_index=True)


def main() -> None:
    init_earth_engine(config.GEE_PROJECT)
    config.NDVI_STATE_DIR.mkdir(parents=True, exist_ok=True)

    cropland = cropland_mask()
    months = pd.date_range(
        config.NDVI_START_DATE, config.NDVI_END_DATE, freq="MS", inclusive="left"
    )
    print(f"Extracting NDVI for {len(config.NDVI_STATES)} states, {len(months)} months")

    incomplete = []
    for state in config.NDVI_STATES:
        if state_csv_path(state).exists():
            print(f"  {state}: already done, skipping")
            continue
        if not extract_state(state, cropland, months):
            incomplete.append(state)

    ndvi = combine_states()
    ndvi.to_csv(config.NDVI_CSV, index=False)
    print(
        f"\nSaved {len(ndvi)} rows to {config.NDVI_CSV} "
        f"({ndvi['state'].nunique()} states, {ndvi['district'].nunique()} districts)"
    )
    if incomplete:
        print(f"Incomplete states (re-run to retry): {', '.join(incomplete)}")


if __name__ == "__main__":
    main()
