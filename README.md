# AgriSignal

This is a project I'm building to see if satellite data can predict crop prices in India.
It uses NASA MODIS NDVI data (a measure of how green and healthy crops are) from Google Earth Engine and compares it with wheat and rice mandi prices.

Still in progress.

## Tools Used

- Python
- Google Earth Engine
- Pandas
- SQLite

## Setup

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your Earth Engine project id, then run:

```
earthengine authenticate
python src/check_gee.py
```
