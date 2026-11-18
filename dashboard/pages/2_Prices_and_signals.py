"""Prices next to the signals that might move them."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from common import CROP_COLORS, load_events, load_national, sidebar_about

st.set_page_config(page_title="Prices and signals", layout="wide")
st.title("Prices and signals")
st.markdown(
    "The wholesale price index (WPI) for each crop, with a second signal underneath. "
    "Shaded periods are export bans on that crop."
)

national = load_national()
events = load_events()

SIGNALS = {
    "Crop health vs normal (NDVI)": ("ndvi_vs_normal", "NDVI difference"),
    "Hottest temperature vs normal": ("tmax_c_vs_normal", "deg C"),
    "Rainfall vs normal": ("rainfall_mm_vs_normal", "mm"),
    "Government stock": ("stock_lakh_t", "lakh tonnes"),
    "Minimum support price": ("msp_rs_per_qtl", "Rs per quintal"),
}

NOTES = {
    "ndvi_vs_normal": "For wheat, greener than normal goes with smaller price rises over the next few months.",
    "tmax_c_vs_normal": "March 2010, 2017 and 2022 were the hottest Marches in the wheat states. Look at the wheat price after March 2022.",
    "rainfall_mm_vs_normal": "Rainfall showed no clear link with later prices: much of the wheat and rice is irrigated.",
    "stock_lakh_t": "Wheat stocks jump every May when the government buys the new harvest, then fall through the year.",
    "msp_rs_per_qtl": "The support price for each marketing season, including any bonus. For paddy, the market price climbs with it.",
}

with st.sidebar:
    st.header("Chart settings")
    crop = st.radio("Crop", ["wheat", "paddy"], format_func=str.title)
    signal_label = st.selectbox("Signal underneath", list(SIGNALS))
    column, unit = SIGNALS[signal_label]
    st.info(NOTES[column])
sidebar_about()

data = national[national["crop"] == crop]
figure = make_subplots(
    rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06, row_heights=[0.6, 0.4]
)
figure.add_scatter(
    x=data["date"],
    y=data["wpi"],
    name="WPI",
    line={"color": CROP_COLORS[crop]},
    row=1,
    col=1,
)

if column.endswith("_vs_normal"):
    colors = ["#2a7f62" if value >= 0 else "#b03a2e" for value in data[column]]
    if column == "tmax_c_vs_normal":
        colors = ["#b03a2e" if value >= 0 else "#2b8cbe" for value in data[column]]
    figure.add_bar(
        x=data["date"],
        y=data[column],
        name=signal_label,
        marker_color=colors,
        row=2,
        col=1,
    )
else:
    figure.add_scatter(
        x=data["date"],
        y=data[column],
        name=signal_label,
        line={"color": "#555555"},
        row=2,
        col=1,
    )

end_of_data = data["date"].max()
bans = events[(events["crop"] == crop) & events["event"].str.contains("export_ban")]
for ban in bans.itertuples():
    end = ban.end if pd.notna(ban.end) else end_of_data
    figure.add_vrect(
        x0=ban.start,
        x1=end,
        fillcolor="grey",
        opacity=0.15,
        line_width=0,
        row="all",
        col=1,
    )

figure.update_yaxes(title_text="WPI (2022-23 = 100)", row=1, col=1)
figure.update_yaxes(title_text=unit, row=2, col=1)
figure.update_layout(height=620, showlegend=False, margin={"t": 20})
st.plotly_chart(figure, use_container_width=True)

if crop == "paddy":
    st.caption("Before April 2012 the paddy price is the rice index.")
