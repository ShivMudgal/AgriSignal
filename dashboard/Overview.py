"""AgriSignal dashboard: overview page."""

import plotly.graph_objects as go
import streamlit as st

from common import accuracy_table, load_national, load_predictions, sidebar_about

st.set_page_config(page_title="AgriSignal", layout="wide")

st.title("AgriSignal")
st.markdown(
    "Can satellite data on crop health predict whether wheat and paddy prices in "
    "India will rise over the next 1 to 3 months?"
)

national = load_national()
predictions = load_predictions()
accuracy = accuracy_table(predictions)
wheat3 = accuracy[(accuracy["crop"] == "wheat") & (accuracy["months_ahead"] == 3)].iloc[
    0
]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Districts", "329", help="Main wheat and rice districts in 10 states")
col2.metric(
    "Months of data",
    f"{national['month'].nunique()}",
    help="January 2005 to September 2026",
)
col3.metric(
    "Wheat, 3 months ahead",
    f"{wheat3['xgboost_base_ndvi']:.1%}",
    f"{wheat3['xgboost_base_ndvi'] - wheat3['calendar']:+.1%} vs calendar rule",
    help="Share of months 2012-2026 where the model called the direction correctly",
)
col4.metric(
    "Same model without NDVI",
    f"{wheat3['xgboost_base']:.1%}",
    f"{wheat3['xgboost_base'] - wheat3['calendar']:+.1%} vs calendar rule",
)

st.subheader("What I found")
st.markdown("""
- **Crop health matters for wheat.** When the wheat states are greener than in recent
  years, wheat prices rise less over the following months. This passes a Granger
  causality test even after correcting for the number of tests.
- **It improves the 3-month wheat forecast.** Adding NDVI lifts accuracy from 73% to 80%,
  and only the models with NDVI give better probability forecasts than the calendar.
  The gain over the calendar rule in plain accuracy is not yet statistically conclusive.
- **Paddy is different.** Paddy prices rise steadily, and no model beats simply
  predicting "up". Crop conditions add nothing measurable; government buying at the
  minimum support price seems to matter more.
- **More history removed a false lead.** On 2018-2026 alone, rainfall looked useful for
  paddy. With 21 years of data the effect disappears.
""")

st.subheader("Accuracy on 2012-2026, month by month")
with st.sidebar:
    st.header("Chart settings")
    crop = st.radio(
        "Crop for the accuracy chart", ["wheat", "paddy"], format_func=str.title
    )
sidebar_about()
data = accuracy[accuracy["crop"] == crop].set_index("months_ahead")
best_rule = data[["always_up", "calendar", "momentum"]].max(axis=1)
best_model = data[["logistic_base_ndvi", "xgboost_base_ndvi"]].max(axis=1)
base_model = data[["logistic_base", "xgboost_base"]].max(axis=1)

figure = go.Figure()
labels = [
    f"{horizon} month{'s' if horizon > 1 else ''} ahead" for horizon in data.index
]
figure.add_bar(
    x=labels, y=best_rule * 100, name="Best simple rule", marker_color="#999999"
)
figure.add_bar(
    x=labels, y=base_model * 100, name="Best model without NDVI", marker_color="#fdbb84"
)
figure.add_bar(
    x=labels, y=best_model * 100, name="Best model with NDVI", marker_color="#e34a33"
)
figure.update_layout(
    barmode="group",
    yaxis_title="% of months called correctly",
    yaxis_range=[50, 85],
    height=380,
    margin={"t": 20},
)
st.plotly_chart(figure, use_container_width=True)
st.caption(
    "Models are retrained every month on earlier data only and then predict the next "
    "month, as they would have been used live. The simple rules are: always predict the "
    "more common direction, predict the usual direction for that calendar month, or "
    "repeat the recent direction."
)

with st.expander("Data sources"):
    st.markdown("""
| Data | Source |
|---|---|
| Crop health (NDVI) | NASA MODIS Terra and Aqua, cropland only, via Google Earth Engine |
| Rainfall | CHIRPS v3 |
| Temperature | ERA5-Land reanalysis |
| Prices | Wholesale Price Index, Office of the Economic Adviser (three base years linked) |
| Government stocks and MSP | Foodgrains Bulletins, Department of Food and Public Distribution |
| Export bans and stock limits | DGFT notifications, PIB releases, Lok Sabha answers |
""")
