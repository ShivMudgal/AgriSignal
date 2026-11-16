import os
import ee
from dotenv import load_dotenv

# Load project id from .env
load_dotenv()

project = os.getenv("GEE_PROJECT")

# Connect to Earth Engine
ee.Initialize(project=project)

print(f"Connected to Earth Engine ({project})")

# State boundaries
states = ee.FeatureCollection("FAO/GAUL/2025/level1")

# Pakistan also has a Punjab so filter by country too
punjab = states.filter(
    ee.Filter.And(
        ee.Filter.eq("GAUL0_NAME", "India"),
        ee.Filter.eq("GAUL1_NAME", "Punjab")
    )
)

# MODIS NDVI for March 2024
ndvi = (
    ee.ImageCollection("MODIS/061/MOD13Q1")
    .filterDate("2024-03-01", "2024-04-01")
    .select("NDVI")
    .mean()
)

# Average NDVI over Punjab
result = ndvi.reduceRegion(
    reducer=ee.Reducer.mean(),
    geometry=punjab.geometry(),
    scale=250,
    maxPixels=1e10
)

# MODIS NDVI is scaled by 10000
ndvi_value = result.get("NDVI").getInfo() * 0.0001

print(f"Average NDVI over Punjab (March 2024): {ndvi_value:.3f}")
