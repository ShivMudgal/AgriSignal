"""Draw the figures used in the README and the report from the saved data."""

import json

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.collections import PolyCollection
from matplotlib.colors import TwoSlopeNorm

import config
from build_features import nearby_anomaly

MAP_MONTH = "2022-03"
RULES = ["always_up", "calendar", "momentum"]


def district_polygons(geojson: dict) -> dict[str, list]:
    """Outer rings of every district, keyed by 'state|district'."""
    polygons = {}
    for feature in geojson["features"]:
        props = feature["properties"]
        key = f"{props['state']}|{props['district']}"
        polygons[key] = [polygon[0] for polygon in feature["geometry"]["coordinates"]]
    return polygons


def crop_health_map(path) -> None:
    """Map of each district's NDVI compared with the same month in nearby years."""
    ndvi = pd.read_csv(config.NDVI_CLEAN_CSV)
    ndvi = ndvi.sort_values(["state", "district", "month"]).reset_index(drop=True)
    groups = [ndvi["state"], ndvi["district"], ndvi["month"].str[5:7]]
    ndvi["vs_normal"] = nearby_anomaly(ndvi["ndvi"], groups)
    month = ndvi[ndvi["month"] == MAP_MONTH]
    values = dict(zip(month["state"] + "|" + month["district"], month["vs_normal"]))

    polygons = district_polygons(json.loads(config.DISTRICTS_GEOJSON.read_text()))
    shapes, colors = [], []
    for key, rings in polygons.items():
        if key in values:
            shapes.extend(rings)
            colors.extend([values[key]] * len(rings))

    figure, ax = plt.subplots(figsize=(7, 6.5))
    collection = PolyCollection(
        shapes,
        array=pd.Series(colors),
        cmap="BrBG",
        norm=TwoSlopeNorm(vcenter=0, vmin=-0.1, vmax=0.1),
        edgecolors="white",
        linewidths=0.2,
    )
    ax.add_collection(collection)
    ax.autoscale_view()
    ax.set_aspect("equal")
    ax.axis("off")
    figure.colorbar(
        collection, ax=ax, shrink=0.6, label="NDVI vs March in nearby years"
    )
    ax.set_title("Crop health in March 2022, the heatwave month")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
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
    crop_health_map(config.FIGURES_DIR / "crop_health_march_2022.png")
    accuracy_chart(config.FIGURES_DIR / "accuracy.png")
    print(f"Saved figures to {config.FIGURES_DIR}")


if __name__ == "__main__":
    main()
