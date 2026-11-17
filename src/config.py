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

COUNTRY = "India"

# Main producing states for each crop. Together they grow roughly 85% of
# India's wheat and about 70% of its rice.
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
NDVI_STATES = sorted(set(WHEAT_STATES + RICE_STATES))

# NDVI extraction window. The end date is exclusive.
NDVI_START_DATE = "2018-01-01"
NDVI_END_DATE = "2026-10-01"
NDVI_STATE_DIR = RAW_DATA_DIR / "ndvi"
NDVI_CSV = RAW_DATA_DIR / "ndvi_monthly.csv"
