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
STATE = "Punjab"

# NDVI extraction window. The end date is exclusive.
NDVI_START_DATE = "2018-01-01"
NDVI_END_DATE = "2026-10-01"
NDVI_CSV = RAW_DATA_DIR / "ndvi_punjab_monthly.csv"
