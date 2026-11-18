"""Data loading shared by every dashboard page."""

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT / "src"))
from build_features import nearby_anomaly  # noqa: E402

DATA_DIR = PROJECT_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
RAW_DIR = DATA_DIR / "raw"

CROP_COLORS = {"wheat": "#c28a00", "paddy": "#2a7f62"}

MODEL_LABELS = {
    "xgboost_base_ndvi": "XGBoost with NDVI",
    "logistic_base_ndvi": "Logistic regression with NDVI",
    "xgboost_base": "XGBoost without NDVI",
    "logistic_base": "Logistic regression without NDVI",
}
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
MONTH_NAMES += ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


@st.cache_data
def load_national() -> pd.DataFrame:
    """National monthly table, one row per crop and month."""
    national = pd.read_csv(PROCESSED_DIR / "national_monthly.csv")
    national = national.sort_values(["crop", "month"]).reset_index(drop=True)
    national["date"] = pd.to_datetime(national["month"])
    groups = [national["crop"], national["date"].dt.month]
    for column in ["ndvi", "tmax_c", "rainfall_mm"]:
        national[f"{column}_vs_normal"] = nearby_anomaly(national[column], groups)
    return national


@st.cache_data
def load_district_ndvi() -> pd.DataFrame:
    """District NDVI compared with the same month in the years either side."""
    ndvi = pd.read_csv(PROCESSED_DIR / "ndvi_clean.csv")
    ndvi = ndvi.sort_values(["state", "district", "month"]).reset_index(drop=True)
    groups = [ndvi["state"], ndvi["district"], ndvi["month"].str[5:7]]
    ndvi["ndvi_vs_normal"] = nearby_anomaly(ndvi["ndvi"], groups).round(3)
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


def sidebar_about() -> None:
    """Short description of the project at the bottom of the sidebar."""
    with st.sidebar:
        st.divider()
        st.markdown("**About AgriSignal**")
        st.caption(
            "Uses satellite crop health (NDVI), weather and government data to predict "
            "whether wheat and paddy prices in India rise over the next 1 to 3 months."
        )
        st.markdown(
            "**Data:** Jan 2005 to Sep 2026  \n"
            "**Coverage:** 329 districts in 10 states  \n"
            "**Main result:** adding NDVI lifts 3-month wheat forecasts from 73% to 80% "
            "correct"
        )
        st.caption(
            "Sources: NASA MODIS, CHIRPS, ERA5-Land, Office of the Economic Adviser "
            "(WPI), Department of Food and Public Distribution."
        )


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
