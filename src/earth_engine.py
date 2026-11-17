"""Shared helpers for working with Google Earth Engine."""

import time
from collections.abc import Callable
from typing import Any

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
    return get_districts_in_states(country, [state])


def get_districts_in_states(country: str, states: list[str]) -> ee.FeatureCollection:
    """Return the district boundaries of several states from FAO GAUL 2025."""
    return ee.FeatureCollection(GAUL_DISTRICTS).filter(
        ee.Filter.And(
            ee.Filter.eq("GAUL0_NAME", country),
            ee.Filter.inList("GAUL1_NAME", states),
        )
    )


def call_with_retry(
    func: Callable[..., Any], *args: Any, attempts: int = 3, wait_seconds: int = 10
) -> Any | None:
    """Call func(*args), retrying on Earth Engine errors. Returns None if all fail."""
    for attempt in range(1, attempts + 1):
        try:
            return func(*args)
        except ee.EEException as error:
            print(f"    attempt {attempt} failed: {error}")
            if attempt < attempts:
                time.sleep(wait_seconds)
    return None
