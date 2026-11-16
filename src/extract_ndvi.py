"""Extract monthly mean cropland NDVI for every district in the state."""

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


def main() -> None:
    init_earth_engine(config.GEE_PROJECT)

    districts = get_districts(config.COUNTRY, config.STATE)
    cropland = cropland_mask()
    months = pd.date_range(
        config.NDVI_START_DATE, config.NDVI_END_DATE, freq="MS", inclusive="left"
    )
    print(f"Extracting NDVI for {len(months)} months...")

    all_rows = []
    failed_months = []
    for month_start in months:
        try:
            all_rows.extend(district_ndvi_for_month(districts, cropland, month_start))
            print(f"  {month_start:%Y-%m} done")
        except ee.EEException as error:
            # Skip a failed month instead of losing the whole run.
            print(f"  {month_start:%Y-%m} FAILED: {error}")
            failed_months.append(f"{month_start:%Y-%m}")

    ndvi = pd.DataFrame(all_rows).sort_values(["district", "month"])
    config.NDVI_CSV.parent.mkdir(parents=True, exist_ok=True)
    ndvi.to_csv(config.NDVI_CSV, index=False)

    print(f"\nSaved {len(ndvi)} rows to {config.NDVI_CSV}")
    print(f"Districts: {ndvi['district'].nunique()}, months: {ndvi['month'].nunique()}")
    if failed_months:
        print(f"Failed months (re-run to retry): {', '.join(failed_months)}")


if __name__ == "__main__":
    main()
