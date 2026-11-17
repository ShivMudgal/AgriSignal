# AgriSignal

This is a project I'm building to see if satellite data can predict crop prices in India.
The goal is to predict whether all-India wheat and paddy prices will go up or down over the next 1 to 3 months, using crop health and rainfall in the main growing states.

Still in progress.

## Data

| Data | Source | Coverage |
|---|---|---|
| Crop health (NDVI) | NASA MODIS Terra and Aqua (MOD13Q1, MYD13Q1) on Google Earth Engine, cropland only (ESA WorldCover), cloudy pixels removed | 332 districts in 10 states, monthly |
| Rainfall | CHIRPS v3 daily rainfall, summed per month | Same districts, monthly |
| Prices | Wholesale Price Index (WPI) for wheat and paddy, Office of the Economic Adviser | All-India, monthly |

All three cover January 2018 to September 2026. District boundaries come from FAO GAUL 2025.

WPI changed its base year from 2011-12 to 2022-23. The new series starts in April 2023, so I joined the two series at that month: the old series is rescaled so both agree in April 2023, which keeps every real monthly up and down move.

## Tools Used

- Python
- Google Earth Engine
- Pandas
- SQLite

## Setup

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
```

Copy `.env.example` to `.env` and add your Earth Engine project id, then run:

```
earthengine authenticate
python src/check_gee.py
```

`requirements.txt` has only what the app needs to run. `requirements-dev.txt` adds formatting, testing and notebook tools.

## Getting the data

```
python src/extract_ndvi.py
python src/extract_rainfall.py
python src/build_wpi.py
```

The NDVI script saves one file per state in `data/raw/ndvi/`, so if it stops halfway, running it again continues where it left off.

The WPI script downloads two Excel files from eaindustry.nic.in into `data/raw/wpi/`. That site sometimes sends an incomplete security certificate, which Python rejects. If the download fails, the script prints the link, and you can download the file in a browser and save it in that folder.

## Known limitations

- Fog (January 2024) and monsoon cloud (July 2024) can leave some district-months with very few clear pixels, even with both satellites.
- Some south-west Punjab districts grow cotton in the kharif season, so their July to September NDVI is not only rice.
- The old and new WPI series do not always agree on the direction of paddy prices in the months they overlap.
- The latest one or two months of WPI are provisional and can be revised.
