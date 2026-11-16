"""Check the Earth Engine setup by computing Punjab's mean NDVI for one month."""

import ee

import config

# MODIS stores NDVI as integers multiplied by 10,000.
NDVI_SCALE_FACTOR = 0.0001


def init_earth_engine(project: str | None) -> None:
    """Connect to Earth Engine using the Cloud project from .env."""
    if not project:
        raise SystemExit(
            "GEE_PROJECT is not set. Copy .env.example to .env and fill it in."
        )
    ee.Initialize(project=project)


def get_state(country: str, state: str) -> ee.FeatureCollection:
    """Return one state's boundary from FAO GAUL 2025."""
    states = ee.FeatureCollection("FAO/GAUL/2025/level1")
    # Filter on country as well, since Pakistan also has a state called Punjab.
    return states.filter(
        ee.Filter.And(
            ee.Filter.eq("GAUL0_NAME", country),
            ee.Filter.eq("GAUL1_NAME", state),
        )
    )


def mean_ndvi(region: ee.FeatureCollection, start_date: str, end_date: str) -> float:
    """Return the average MODIS NDVI over a region between two dates."""
    ndvi = (
        ee.ImageCollection("MODIS/061/MOD13Q1")
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

    punjab = get_state("India", "Punjab")
    value = mean_ndvi(punjab, "2024-03-01", "2024-04-01")
    print(f"Mean NDVI over Punjab, March 2024: {value:.3f}")


if __name__ == "__main__":
    main()
