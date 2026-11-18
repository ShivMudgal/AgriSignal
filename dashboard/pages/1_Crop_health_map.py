"""Map of crop health by district for any month."""

import plotly.express as px
import streamlit as st

from common import MONTH_NAMES, load_district_ndvi, load_districts_geojson

st.set_page_config(page_title="Crop health map", layout="wide")
st.title("Crop health map")
st.markdown(
    "NDVI measures how green the cropland is (higher is greener). The map shows each "
    "district compared with its own average for that calendar month over 2005-2026, so "
    "green means healthier crops than usual and brown means worse."
)

ndvi = load_district_ndvi()
geojson = load_districts_geojson()

years = sorted(ndvi["month"].str[:4].unique())
col1, col2, col3 = st.columns([2, 2, 2])
year = col1.select_slider("Year", options=years, value="2022")
month_name = col2.select_slider("Month", options=MONTH_NAMES, value="Mar")
measure = col3.radio("Show", ["Compared with normal", "NDVI value"], horizontal=True)

month = f"{year}-{MONTH_NAMES.index(month_name) + 1:02d}"
data = ndvi[ndvi["month"] == month]

if data.empty:
    st.warning("No data for this month.")
    st.stop()

if measure == "Compared with normal":
    column, colors, limits = "ndvi_vs_normal", "BrBG", (-0.1, 0.1)
else:
    column, colors, limits = "ndvi", "YlGn", (0.1, 0.8)

# Drawn from the district shapes alone, so the map needs no tile server.
figure = px.choropleth(
    data,
    geojson=geojson,
    locations="key",
    featureidkey="properties.key",
    color=column,
    color_continuous_scale=colors,
    range_color=limits,
    hover_name="district",
    hover_data={"state": True, "ndvi": ":.3f", "ndvi_vs_normal": ":+.3f", "key": False},
    labels={"ndvi_vs_normal": "vs normal", "ndvi": "NDVI", "state": "State"},
)
figure.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)")
figure.update_layout(paper_bgcolor="rgba(0,0,0,0)")
figure.update_traces(marker_line_width=0.3, marker_line_color="white")
figure.update_layout(height=620, margin={"l": 0, "r": 0, "t": 0, "b": 0})
st.plotly_chart(figure, use_container_width=True)

season = {12: "rabi (wheat)", 1: "rabi (wheat)", 2: "rabi (wheat)", 3: "rabi (wheat)"}
season.update(
    {7: "kharif (rice)", 8: "kharif (rice)", 9: "kharif (rice)", 10: "kharif (rice)"}
)
calendar_month = MONTH_NAMES.index(month_name) + 1
st.caption(
    f"{month_name} {year}: "
    + (
        f"{season[calendar_month]} season."
        if calendar_month in season
        else "between the main seasons."
    )
    + f" Average across districts: {data['ndvi_vs_normal'].mean():+.3f} vs normal."
    " Kolkata, Hyderabad and a disputed area are left out because they have almost no farmland."
)
