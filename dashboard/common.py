"""Data loading shared by every dashboard page."""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PROCESSED_DIR = DATA_DIR / "processed"
RAW_DIR = DATA_DIR / "raw"

CROP_COLORS = {"wheat": "#c28a00", "paddy": "#2a7f62"}
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
MONTH_NAMES += ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


@st.cache_data
def load_national() -> pd.DataFrame:
    """National monthly table, one row per crop and month."""
    national = pd.read_csv(PROCESSED_DIR / "national_monthly.csv")
    national["date"] = pd.to_datetime(national["month"])
    calendar_month = national["date"].dt.month
    for column in ["ndvi", "tmax_c", "rainfall_mm"]:
        normal = national.groupby(["crop", calendar_month])[column].transform("mean")
        national[f"{column}_vs_normal"] = national[column] - normal
    return national


@st.cache_data
def load_district_ndvi() -> pd.DataFrame:
    """District NDVI with the difference from the average for that calendar month."""
    ndvi = pd.read_csv(PROCESSED_DIR / "ndvi_clean.csv")
    calendar_month = ndvi["month"].str[5:7]
    normal = ndvi.groupby(["state", "district", calendar_month])["ndvi"].transform(
        "mean"
    )
    ndvi["ndvi_vs_normal"] = (ndvi["ndvi"] - normal).round(3)
    ndvi["key"] = ndvi["state"] + "|" + ndvi["district"]
    return ndvi


def signed_area(ring: list) -> float:
    """Positive when the ring runs anticlockwise."""
    return sum(
        x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1])
    )


def clockwise_outlines(polygon: list) -> list:
    """Outer ring clockwise and holes anticlockwise, as Plotly's maps expect.

    Standard GeoJSON uses the opposite order, which Plotly would read as
    'the whole world except this district'.
    """
    rings = []
    for index, ring in enumerate(polygon):
        anticlockwise = signed_area(ring) > 0
        is_outer = index == 0
        rings.append(ring[::-1] if anticlockwise == is_outer else ring)
    return rings


@st.cache_data
def load_districts_geojson() -> dict:
    """District boundaries, each tagged with a 'state|district' key."""
    geojson = json.loads((PROCESSED_DIR / "districts.geojson").read_text())
    for feature in geojson["features"]:
        props = feature["properties"]
        props["key"] = f"{props['state']}|{props['district']}"
        geometry = feature["geometry"]
        geometry["coordinates"] = [
            clockwise_outlines(polygon) for polygon in geometry["coordinates"]
        ]
    return geojson


@st.cache_data
def load_predictions() -> pd.DataFrame:
    """Walk-forward predictions of the models and the simple rules."""
    predictions = pd.read_csv(PROCESSED_DIR / "predictions.csv")
    predictions["date"] = pd.to_datetime(predictions["month"])
    return predictions


@st.cache_data
def load_forecast() -> pd.DataFrame:
    """Forecast from the last month of data."""
    return pd.read_csv(PROCESSED_DIR / "forecast.csv")


@st.cache_data
def load_events() -> pd.DataFrame:
    """Export bans and stock limits."""
    return pd.read_csv(RAW_DIR / "policy_events.csv", parse_dates=["start", "end"])


def accuracy_table(predictions: pd.DataFrame) -> pd.DataFrame:
    """Share of months each model and rule called correctly, per crop and horizon."""
    columns = ["always_up", "calendar", "momentum"]
    columns += [
        c for c in predictions.columns if c.startswith(("logistic_", "xgboost_"))
    ]
    columns = [c for c in columns if not c.endswith("_prob")]
    rows = []
    for (crop, months_ahead), data in predictions.groupby(["crop", "months_ahead"]):
        row = {"crop": crop, "months_ahead": months_ahead}
        row.update({c: (data[c] == data["outcome"]).mean() for c in columns})
        rows.append(row)
    return pd.DataFrame(rows)
