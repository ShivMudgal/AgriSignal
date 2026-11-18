"""Draw the figures used in the README and the report from the saved data."""

import json

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.collections import PolyCollection
from matplotlib.colors import TwoSlopeNorm
from shapely.geometry import shape
from shapely.ops import unary_union

import config
from build_features import nearby_anomaly

MAP_MONTH = "2022-03"
RULES = ["always_up", "calendar", "momentum"]


# Short labels for the state names drawn on the map.
STATE_LABELS = {
    "Punjab": "Punjab",
    "Haryana": "Haryana",
    "Rajasthan": "Rajasthan",
    "Uttar Pradesh": "Uttar Pradesh",
    "Madhya Pradesh": "Madhya Pradesh",
    "Chhattisgarh": "Chhattisgarh",
    "Odisha": "Odisha",
    "West Bengal": "W. Bengal",
    "Telangana": "Telangana",
    "Andhra Pradesh": "Andhra P.",
}


def load_districts() -> list[dict]:
    """District shapes with their state, district and shapely geometry."""
    geojson = json.loads(config.DISTRICTS_GEOJSON.read_text())
    districts = []
    for feature in geojson["features"]:
        props = feature["properties"]
        districts.append(
            {
                "key": f"{props['state']}|{props['district']}",
                "state": props["state"],
                "rings": [polygon[0] for polygon in feature["geometry"]["coordinates"]],
                "geometry": shape(feature["geometry"]),
            }
        )
    return districts


def anomaly_for_month(path, column: str) -> dict[str, float]:
    """Each district's value compared with the same month in nearby years."""
    data = pd.read_csv(path)
    data = data.sort_values(["state", "district", "month"]).reset_index(drop=True)
    groups = [data["state"], data["district"], data["month"].str[5:7]]
    data["vs_normal"] = nearby_anomaly(data[column], groups)
    month = data[data["month"] == MAP_MONTH]
    return dict(zip(month["state"] + "|" + month["district"], month["vs_normal"]))


def draw_map(ax, districts, values, cmap, limit, label) -> None:
    """Colour districts by value, with state borders and names on top."""
    shapes, colors = [], []
    for district in districts:
        if district["key"] in values:
            shapes.extend(district["rings"])
            colors.extend([values[district["key"]]] * len(district["rings"]))

    collection = PolyCollection(
        shapes,
        array=pd.Series(colors),
        cmap=cmap,
        norm=TwoSlopeNorm(vcenter=0, vmin=-limit, vmax=limit),
        edgecolors="white",
        linewidths=0.15,
    )
    ax.add_collection(collection)

    for state in STATE_LABELS:
        outline = unary_union(
            [d["geometry"].buffer(0.01) for d in districts if d["state"] == state]
        )
        parts = getattr(outline, "geoms", [outline])
        for part in parts:
            x, y = part.exterior.xy
            ax.plot(x, y, color="#333333", linewidth=0.8)
        point = outline.representative_point()
        ax.annotate(
            STATE_LABELS[state],
            (point.x, point.y),
            ha="center",
            va="center",
            fontsize=7.5,
            color="#222222",
            bbox={
                "boxstyle": "round,pad=0.15",
                "fc": "white",
                "ec": "none",
                "alpha": 0.7,
            },
        )

    ax.autoscale_view()
    ax.set_aspect("equal")
    ax.axis("off")
    colorbar = plt.colorbar(collection, ax=ax, shrink=0.55, pad=0.01)
    colorbar.set_label(label, fontsize=9)


def heatwave_map(path) -> None:
    """Heat and crop health side by side for the March 2022 heatwave."""
    districts = load_districts()
    heat = anomaly_for_month(config.TEMPERATURE_CLEAN_CSV, "tmax_c")
    health = anomaly_for_month(config.NDVI_CLEAN_CSV, "ndvi")

    figure, axes = plt.subplots(1, 2, figsize=(13, 6.2))
    draw_map(axes[0], districts, heat, "RdBu_r", 3.0, "deg C vs March in nearby years")
    axes[0].set_title("Hottest temperature", fontsize=12)
    draw_map(axes[1], districts, health, "BrBG", 0.05, "NDVI vs March in nearby years")
    axes[1].set_title("Crop health (NDVI)", fontsize=12)
    figure.suptitle(
        "March 2022: an early heatwave just before the wheat harvest", fontsize=14
    )
    figure.tight_layout()
    figure.savefig(path, dpi=150, facecolor="white")
    plt.close(figure)


def accuracy_chart(path) -> None:
    """Best simple rule against the best models with and without NDVI."""
    predictions = pd.read_csv(config.PREDICTIONS_CSV)
    figure, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
    bars = {
        "Best simple rule": (RULES, "#999999"),
        "Model without NDVI": (["logistic_base", "xgboost_base"], "#fdbb84"),
        "Model with NDVI": (["logistic_base_ndvi", "xgboost_base_ndvi"], "#e34a33"),
    }
    width = 0.26
    for ax, crop in zip(axes, ["wheat", "paddy"]):
        data = predictions[predictions["crop"] == crop]
        for offset, (label, (columns, color)) in zip([-1, 0, 1], bars.items()):
            accuracy = [
                max(
                    (group[column] == group["outcome"]).mean() * 100
                    for column in columns
                )
                for _, group in data.groupby("months_ahead")
            ]
            ax.bar(
                [h + offset * width for h in [1, 2, 3]],
                accuracy,
                width,
                color=color,
                label=label,
            )
        ax.set_xticks([1, 2, 3], ["1 month", "2 months", "3 months"])
        ax.set_ylim(50, 85)
        ax.set_title(crop.title())
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("% of months called correctly")
    axes[1].legend(fontsize=8, loc="lower right")
    figure.suptitle("Direction of price, walk-forward test 2012-2026")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def main() -> None:
    config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    heatwave_map(config.FIGURES_DIR / "heatwave_march_2022.png")
    accuracy_chart(config.FIGURES_DIR / "accuracy.png")
    print(f"Saved figures to {config.FIGURES_DIR}")


if __name__ == "__main__":
    main()
