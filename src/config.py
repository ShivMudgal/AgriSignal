"""Project-wide settings shared by all scripts."""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")

GEE_PROJECT = os.getenv("GEE_PROJECT")

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
DB_PATH = PROJECT_ROOT / "db" / "agrisignal.db"
FIGURES_DIR = PROJECT_ROOT / "reports" / "figures"
SCHEMA_SQL = PROJECT_ROOT / "sql" / "schema.sql"

# SQLite by default. Set DATABASE_URL in .env to use another database,
# e.g. postgresql+psycopg://user:password@localhost:5432/agrisignal
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH.as_posix()}")

COUNTRY = "India"

# The largest producing states for each crop (Bihar is left out for now).
WHEAT_STATES = ["Uttar Pradesh", "Madhya Pradesh", "Punjab", "Haryana", "Rajasthan"]
RICE_STATES = [
    "West Bengal",
    "Uttar Pradesh",
    "Punjab",
    "Telangana",
    "Odisha",
    "Chhattisgarh",
    "Andhra Pradesh",
]
STUDY_STATES = sorted(set(WHEAT_STATES + RICE_STATES))

# Monthly data window for every source. The end date is exclusive.
START_DATE = "2005-01-01"
END_DATE = "2026-10-01"

NDVI_STATE_DIR = RAW_DATA_DIR / "ndvi"
NDVI_CSV = RAW_DATA_DIR / "ndvi_monthly.csv"
RAINFALL_CSV = RAW_DATA_DIR / "rainfall_monthly.csv"
TEMPERATURE_CSV = RAW_DATA_DIR / "temperature_monthly.csv"
WPI_DOWNLOAD_DIR = RAW_DATA_DIR / "wpi"
WPI_CSV = RAW_DATA_DIR / "wpi_monthly.csv"
FCI_DOWNLOAD_DIR = RAW_DATA_DIR / "fci"
FCI_TRANSCRIBED_CSV = RAW_DATA_DIR / "fci_stocks_transcribed.csv"
FCI_STOCKS_CSV = RAW_DATA_DIR / "fci_stocks_monthly.csv"
MSP_CSV = RAW_DATA_DIR / "msp_yearly.csv"
POLICY_EVENTS_CSV = RAW_DATA_DIR / "policy_events.csv"

NDVI_CLEAN_CSV = PROCESSED_DATA_DIR / "ndvi_clean.csv"
RAINFALL_CLEAN_CSV = PROCESSED_DATA_DIR / "rainfall_clean.csv"
TEMPERATURE_CLEAN_CSV = PROCESSED_DATA_DIR / "temperature_clean.csv"
NATIONAL_CSV = PROCESSED_DATA_DIR / "national_monthly.csv"
FEATURES_CSV = PROCESSED_DATA_DIR / "features_monthly.csv"
PREDICTIONS_CSV = PROCESSED_DATA_DIR / "predictions.csv"
FORECAST_CSV = PROCESSED_DATA_DIR / "forecast.csv"
DISTRICTS_GEOJSON = PROCESSED_DATA_DIR / "districts.geojson"

# Districts that are almost all city or have no usable cropland.
EXCLUDED_DISTRICTS = ["Kolkata", "Hyderabad", "Disputed (Ratlam & Mandsaur)"]

# Below this many clear cropland pixels a monthly NDVI value is not reliable.
MIN_CLEAR_PIXELS = 100

# "Normal" for a month is the same calendar month in the previous few years.
ANOMALY_YEARS = 5
MIN_HISTORY_YEARS = 3

# Predictions are scored on months from here on; earlier months are only
# used for learning.
EVAL_START = "2012-01"
