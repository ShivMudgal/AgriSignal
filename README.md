# AgriSignal

This is a project I'm building to see if satellite data can predict crop prices in India.
The goal is to predict whether all-India wheat and paddy prices will go up or down over the next 1 to 3 months, using crop health, rainfall and heat in the main growing states, together with the government factors that move Indian grain prices (stocks, support prices and export bans).

Still in progress.

## Data

| Data | Source | Coverage |
|---|---|---|
| Crop health (NDVI) | NASA MODIS Terra and Aqua (MOD13Q1, MYD13Q1) on Google Earth Engine, cropland only (ESA WorldCover), cloudy pixels removed | 332 districts in 10 states, monthly |
| Rainfall | CHIRPS v3 daily rainfall, summed per month | Same districts, monthly |
| Temperature | ERA5-Land monthly mean and hottest 2 m air temperature | Same districts, monthly |
| Prices | Wholesale Price Index (WPI) for wheat, paddy, all commodities, food articles and diesel, Office of the Economic Adviser | All-India, monthly |
| Government grain stocks | Wheat and rice in the central pool on the 1st of each month, from the Foodgrains Bulletin of the Department of Food and Public Distribution | All-India, monthly |
| Minimum support price | MSP plus any bonus for each marketing season, from the Foodgrains Bulletins and the Department of Food and Public Distribution | All-India, yearly |
| Policy events | Export bans and stock limits on wheat and rice, from DGFT notifications, PIB releases and Lok Sabha answers (sources listed in the file) | Dated events |

Everything covers January 2005 to September 2026. District boundaries come from FAO GAUL 2025.

WPI has been published with three base years (2004-05, 2011-12 and 2022-23). I chain-linked them item by item: each older series is rescaled so it matches the newer one in the newer series' first month, which keeps every real monthly up and down move. Before April 2012 there is no paddy index, so the rice index stands in for it (marked in the data).

The grain stock figures come from six bulletins (2015 to 2026), each covering about three years, so most months are reported twice and the overlaps are checked against each other. 2005 to 2011 only exists as a scanned bulletin (November 2011, from the Internet Archive copy of the old dfpd.nic.in site), so I typed that table into `data/raw/fci_stocks_transcribed.csv`. Every month is checked: rice, wheat and coarse grains must add up to the printed total, and the 2005 to April 2009 values must also appear in the March 2009 bulletin.

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
python src/extract_temperature.py
python src/build_wpi.py
python src/build_fci_stocks.py
```

The NDVI script saves one file per state in `data/raw/ndvi/`, so if it stops halfway, running it again continues where it left off.

The WPI script downloads two Excel files from eaindustry.nic.in into `data/raw/wpi/`. That site sometimes sends an incomplete security certificate, which Python rejects. If the download fails, the script prints the link, and you can download the file in a browser and save it in that folder.

Temperature comes from the ERA5-Land reanalysis rather than the MODIS satellites. I tried MODIS land surface temperature first, but the orbits of both Terra and Aqua have been drifting since about 2020, so they pass over at a different time of day and their daytime readings over Punjab came out 2 to 3 degrees cooler in 2025 and 2026 than in 2024. ERA5-Land has no such drift and still picks out the real heatwaves (March 2010 and March 2022).

## Cleaning and the database

```
python src/clean_data.py
python src/build_database.py
```

Cleaning drops three districts with almost no farmland (Kolkata, Hyderabad and a disputed area), leaving 329 districts. NDVI values from fewer than 100 clear pixels are replaced by the value between the months before and after, and marked in an `is_filled` column. Only 14 of 85,869 values needed this.

The database has eight tables (`districts`, `ndvi`, `rainfall`, `temperature`, `wpi`, `fci_stocks`, `msp`, `policy_events`) and a view, `district_month`, that puts the district data side by side. The schema is in `sql/schema.sql`. It uses SQLite by default (`db/agrisignal.db`). To use PostgreSQL instead, install `psycopg` and set `DATABASE_URL` in `.env` (see `.env.example`).

## Exploring the data

```
python src/build_national.py
```

This combines the districts into one national monthly series per crop (wheat states and rice states), weighting each district by its farmland, and adds prices, government stocks, the MSP in force and export ban and stock limit flags. The analysis is in `notebooks/01_eda.ipynb`. Main findings so far (2005 to 2026):

- The calendar explains a lot: wheat prices usually fall from February to June after the harvest and rise for the rest of the year.
- Greener than normal crops go with smaller price rises over the next 1 to 3 months (correlation about -0.25 for wheat and -0.27 for paddy).
- Recent price rises tend to continue, and MSP increases go with higher paddy prices (about +0.30).
- Hotter than normal months go with bigger price rises (about +0.12), a small but consistent effect.
- Rainfall, stock changes and export bans show no clear link. On 2018 to 2026 data alone, paddy rainfall looked as strong as NDVI; with 21 years it disappears.
- Each signal on its own is weak, so the next step is to test whether together they beat the calendar on months a model has not seen.

## Testing the signals

```
python src/build_features.py
python src/baselines.py
```

`build_features.py` turns the national table into model features using only past information: each anomaly compares a month with the same calendar month in the previous five years. `baselines.py` scores three simple rules (always up, same direction as usual for the calendar month, same direction as recent momentum) on 2012 to 2026. The best of them already calls the price direction right 68% to 75% of the time, which is the bar a model has to beat.

`notebooks/02_signal_tests.ipynb` runs Granger causality tests: does a signal improve the forecast of next month's price change beyond past price changes and the calendar? With 48 tests, the p-values are adjusted for multiple testing (Benjamini-Hochberg). Results:

- Wheat NDVI passes at 1, 2 and 3 lags (adjusted p = 0.002 to 0.039). Greener than recent years means a smaller price rise; a typical anomaly moves next month's wheat price change by about 0.4 percentage points.
- Past price changes (momentum) pass for both crops.
- Paddy NDVI, heat, rainfall, stock changes, food inflation, MSP changes and export bans do not pass for either crop.

## Models

```
python src/train_models.py
```

Logistic regression and XGBoost predict whether the price will be higher 1, 2 or 3 months later. They are tested walk-forward: for every month from 2012 the models are retrained on all earlier months whose outcome was known, then make one prediction. Each model is trained twice, with and without the NDVI inputs, so the value of the satellite data shows up directly. The analysis is in `notebooks/03_models.ipynb`.

- Wheat, 3 months ahead: adding NDVI raises accuracy from 73.0% to 79.9% (XGBoost), against 75.3% for the best simple rule (calendar). Only the models with NDVI produce better probability forecasts than the calendar (Brier score 0.150 vs 0.173, p = 0.016).
- The accuracy gain over the calendar rule (+4.6 points over 174 months) is not statistically significant (McNemar p = 0.24), and the edge varies from year to year.
- Wheat 1 and 2 months ahead: NDVI adds nothing; momentum and the calendar do the work.
- Paddy: no model beats the simple rules. At 3 months, "always up" (75.3%) is significantly better than every model.

In short: satellite crop health measurably improves 3-month wheat forecasts, but the gain over a well-chosen calendar rule is modest, and paddy prices are driven by the government's support price rather than crop conditions.

## Known limitations

- Fog and monsoon cloud leave a few district-months with very few clear pixels, even with both satellites. These are filled from nearby months.
- Some south-west Punjab districts grow cotton in the kharif season, so their July to September NDVI is not only rice.
- The old and new WPI series do not always agree on the direction of paddy prices in the months they overlap.
- The latest one or two months of WPI are provisional and can be revised.
- Before April 2012 the paddy price is the rice index.
- NDVI drifts slightly upward over the years (about 0.004 a year), which accounts for part of the paddy signal.
- Government stocks, MSP and export bans partly react to prices, so their links with prices run both ways.
- The 2005 to 2011 stock figures were typed in from a scanned bulletin and checked against printed totals and a second bulletin.
