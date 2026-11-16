"""Check the Earth Engine setup by computing Punjab's mean NDVI for one month."""

import ee

import config
from earth_engine import (
    MODIS_NDVI_COLLECTION,
    NDVI_SCALE_FACTOR,
    get_state,
    init_earth_engine,
)


def mean_ndvi(region: ee.FeatureCollection, start_date: str, end_date: str) -> float:
    """Return the average MODIS NDVI over a region between two dates."""
    ndvi = (
        ee.ImageCollection(MODIS_NDVI_COLLECTION)
        .filterDate(start_date, end_date)
        .select("NDVI")
        .mean()
    )
    stats = ndvi.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=region.geometry(),
        scale=250,
        maxPixels=1e10,
    )
    return stats.get("NDVI").getInfo() * NDVI_SCALE_FACTOR


def main() -> None:
    init_earth_engine(config.GEE_PROJECT)
    print(f"Connected to Earth Engine (project: {config.GEE_PROJECT})")

    punjab = get_state(config.COUNTRY, config.STATE)
    value = mean_ndvi(punjab, "2024-03-01", "2024-04-01")
    print(f"Mean NDVI over {config.STATE}, March 2024: {value:.3f}")


if __name__ == "__main__":
    main()
