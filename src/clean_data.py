"""Clean the raw NDVI and rainfall tables and save them to data/processed."""

import pandas as pd

import config


def drop_excluded_districts(table: pd.DataFrame) -> pd.DataFrame:
    """Remove districts with no usable cropland."""
    return table[~table["district"].isin(config.EXCLUDED_DISTRICTS)]


def fill_unreliable_ndvi(ndvi: pd.DataFrame) -> pd.DataFrame:
    """Replace NDVI from too few clear pixels with the value between its neighbours."""
    ndvi = ndvi.sort_values(["state", "district", "month"]).copy()
    unreliable = ndvi["ndvi"].isna() | (ndvi["pixel_count"] < config.MIN_CLEAR_PIXELS)
    ndvi.loc[unreliable, "ndvi"] = None

    # Linear interpolation within each district, using the months on either side.
    ndvi["ndvi"] = (
        ndvi.groupby(["state", "district"])["ndvi"]
        .transform(lambda series: series.interpolate(limit_area="inside"))
        .round(4)
    )
    ndvi["is_filled"] = unreliable

    if ndvi["ndvi"].isna().any():
        raise SystemExit("Some NDVI gaps could not be filled (first or last month).")
    return ndvi


def main() -> None:
    ndvi = drop_excluded_districts(pd.read_csv(config.NDVI_CSV))
    rainfall = drop_excluded_districts(pd.read_csv(config.RAINFALL_CSV))

    ndvi = fill_unreliable_ndvi(ndvi)

    config.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    ndvi.to_csv(config.NDVI_CLEAN_CSV, index=False, lineterminator="\n")
    rainfall.to_csv(config.RAINFALL_CLEAN_CSV, index=False, lineterminator="\n")

    print(
        f"NDVI: {len(ndvi)} rows, {ndvi['is_filled'].sum()} filled from nearby months"
    )
    print(f"Rainfall: {len(rainfall)} rows")
    print(
        f"Districts: {ndvi.groupby(['state', 'district']).ngroups} "
        f"(dropped {', '.join(config.EXCLUDED_DISTRICTS)})"
    )


if __name__ == "__main__":
    main()
