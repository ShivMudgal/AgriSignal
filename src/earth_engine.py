"""Shared helpers for working with Google Earth Engine."""

import ee

MODIS_NDVI_COLLECTION = "MODIS/061/MOD13Q1"
GAUL_STATES = "FAO/GAUL/2025/level1"
GAUL_DISTRICTS = "FAO/GAUL/2025/level2"

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
    # Filter on country as well, since Pakistan also has a state called Punjab.
    return ee.FeatureCollection(GAUL_STATES).filter(
        ee.Filter.And(
            ee.Filter.eq("GAUL0_NAME", country),
            ee.Filter.eq("GAUL1_NAME", state),
        )
    )


def get_districts(country: str, state: str) -> ee.FeatureCollection:
    """Return the district boundaries of one state from FAO GAUL 2025."""
    return ee.FeatureCollection(GAUL_DISTRICTS).filter(
        ee.Filter.And(
            ee.Filter.eq("GAUL0_NAME", country),
            ee.Filter.eq("GAUL1_NAME", state),
        )
    )
