"""Clean the raw district tables (NDVI, rainfall, temperature) for data/processed."""

import pandas as pd

import config


def drop_excluded_districts(table: pd.DataFrame) -> pd.DataFrame:
    """Remove districts with no usable cropland."""
    return table[~table["district"].isin(config.EXCLUDED_DISTRICTS)]


def fill_gaps(
    table: pd.DataFrame, column: str, unreliable: pd.Series, decimals: int
) -> pd.DataFrame:
    """Replace unreliable or missing values with the value between their neighbours."""
    table = table.copy()
    table.loc[unreliable, column] = None

    # Linear interpolation within each district, using the months on either side.
    table[column] = (
        table.groupby(["state", "district"])[column]
        .transform(lambda series: series.interpolate(limit_area="inside"))
        .round(decimals)
    )
    table["is_filled"] = unreliable

    if table[column].isna().any():
        raise SystemExit(
            f"Some {column} gaps could not be filled (first or last month)."
        )
    return table


def clean_ndvi(ndvi: pd.DataFrame) -> pd.DataFrame:
    """Fill NDVI that is missing or based on too few clear pixels."""
    ndvi = ndvi.sort_values(["state", "district", "month"])
    unreliable = ndvi["ndvi"].isna() | (ndvi["pixel_count"] < config.MIN_CLEAR_PIXELS)
    return fill_gaps(ndvi, "ndvi", unreliable, decimals=4)


def clean_temperature(temperature: pd.DataFrame) -> pd.DataFrame:
    """Fill months where clouds hid the ground for the whole month."""
    temperature = temperature.sort_values(["state", "district", "month"])
    return fill_gaps(
        temperature, "lst_day_c", temperature["lst_day_c"].isna(), decimals=2
    )


def save(table: pd.DataFrame, path, name: str) -> None:
    """Write a cleaned table and report how many values were filled."""
    table.to_csv(path, index=False, lineterminator="\n")
    filled = f", {table['is_filled'].sum()} filled" if "is_filled" in table else ""
    print(f"{name}: {len(table)} rows{filled}")


def main() -> None:
    ndvi = clean_ndvi(drop_excluded_districts(pd.read_csv(config.NDVI_CSV)))
    rainfall = drop_excluded_districts(pd.read_csv(config.RAINFALL_CSV))
    temperature = clean_temperature(
        drop_excluded_districts(pd.read_csv(config.TEMPERATURE_CSV))
    )

    config.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    save(ndvi, config.NDVI_CLEAN_CSV, "NDVI")
    save(rainfall, config.RAINFALL_CLEAN_CSV, "Rainfall")
    save(temperature, config.TEMPERATURE_CLEAN_CSV, "Temperature")
    print(
        f"Districts: {ndvi.groupby(['state', 'district']).ngroups} "
        f"(dropped {', '.join(config.EXCLUDED_DISTRICTS)})"
    )


if __name__ == "__main__":
    main()
