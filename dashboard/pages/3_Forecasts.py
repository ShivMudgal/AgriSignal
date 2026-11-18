"""The models' forecast from the latest data, and their track record."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from common import (
    MODEL_LABELS,
    accuracy_table,
    load_forecast,
    load_predictions,
    sidebar_about,
)

st.set_page_config(page_title="Forecasts", layout="wide")
st.title("Forecasts")

forecast = load_forecast()
predictions = load_predictions()
from_month = pd.Period(forecast["from_month"].iloc[0], "M")

st.markdown(
    f"Chance that the price is **higher** than in {from_month.strftime('%B %Y')}, from the "
    "model that did best for each crop and horizon on 2012-2026."
)
st.info(
    "These are probabilities, not certainties. On past data the models called the "
    "direction right 68% to 80% of the time, about as often as simple rules like "
    '"prices usually rise". Treat this as an illustration of the method, not trading advice.'
)

for crop in ["wheat", "paddy"]:
    st.subheader(crop.title())
    columns = st.columns(3)
    for column, row in zip(columns, forecast[forecast["crop"] == crop].itertuples()):
        to_month = pd.Period(row.to_month, "M").strftime("%b %Y")
        column.metric(
            f"By {to_month}",
            f"{row.probability_up:.0%} chance up",
            f"past accuracy {row.past_accuracy:.0%} (rule {row.rule_accuracy:.0%})",
            delta_color="off",
            help=f"Model: {MODEL_LABELS[row.model]}. Best simple rule on the same months: {row.best_rule}.",
        )

with st.sidebar:
    st.header("Track record settings")
    crop = st.radio("Crop", ["wheat", "paddy"], format_func=str.title)
    months_ahead = st.radio(
        "Months ahead",
        [1, 2, 3],
        index=2,
        format_func=lambda months: f"{months} month{'s' if months > 1 else ''}",
    )
    model = st.selectbox("Model", list(MODEL_LABELS), format_func=MODEL_LABELS.get)
    st.caption(
        "The forecasts at the top use the best model for each crop and horizon. "
        "These settings only change the track record chart and table."
    )
sidebar_about()

st.subheader(f"Track record: {crop}, {months_ahead} month(s) ahead")
st.markdown(f"**{MODEL_LABELS[model]}**, month by month from 2012")

data = predictions[
    (predictions["crop"] == crop) & (predictions["months_ahead"] == months_ahead)
]
correct = data[model] == data["outcome"]

figure = go.Figure()
figure.add_scatter(
    x=data["date"],
    y=data[f"{model}_prob"],
    name="Predicted chance of a rise",
    line={"color": "#555555"},
)
figure.add_scatter(
    x=data["date"],
    y=data["outcome"],
    mode="markers",
    name="What happened (1 = rose)",
    marker={"color": ["#2a7f62" if hit else "#b03a2e" for hit in correct], "size": 6},
)
figure.add_hline(y=0.5, line_dash="dot", line_color="grey")
figure.update_layout(
    height=380,
    yaxis_title="Probability / outcome",
    margin={"t": 20},
    legend={"orientation": "h"},
)
st.plotly_chart(figure, use_container_width=True)
st.caption(
    "Green dots: the model's call (above or below 50%) was right. Red: it was wrong."
)

accuracy = accuracy_table(predictions)
table = (
    accuracy[accuracy["crop"] == crop].set_index("months_ahead").drop(columns="crop")
)
table = (table * 100).round(1)
table.columns = [
    MODEL_LABELS.get(name, name.replace("_", " ")) for name in table.columns
]
st.markdown("**% of months called correctly, 2012-2026**")
st.dataframe(table, use_container_width=True)
