"""Save simplified district boundaries as GeoJSON for the dashboard map."""

import json

import ee

import config
from earth_engine import get_districts_in_states, init_earth_engine

# Boundaries are simplified to within about 1 km, which is plenty for a map
# of the whole region and keeps the file small.
SIMPLIFY_METERS = 1000


def as_multipolygon(geometry: dict) -> dict:
    """Turn any geometry into a MultiPolygon, which every map library can draw.

    Simplifying sometimes leaves a GeometryCollection with stray lines or
    points; only the polygons are kept.
    """
    if geometry["type"] == "Polygon":
        return {"type": "MultiPolygon", "coordinates": [geometry["coordinates"]]}
    if geometry["type"] == "MultiPolygon":
        return geometry
    polygons = []
    for part in geometry.get("geometries", []):
        if part["type"] in ("Polygon", "MultiPolygon"):
            polygons.extend(as_multipolygon(part)["coordinates"])
    return {"type": "MultiPolygon", "coordinates": polygons}


def main() -> None:
    init_earth_engine(config.GEE_PROJECT)
    districts = get_districts_in_states(config.COUNTRY, config.STUDY_STATES)
    simplified = districts.map(
        lambda feature: ee.Feature(
            feature.geometry().simplify(SIMPLIFY_METERS),
            {"state": feature.get("GAUL1_NAME"), "district": feature.get("GAUL2_NAME")},
        )
    )
    geojson = simplified.getInfo()

    # Keep only what the map needs, and round coordinates to about 100 m.
    for feature in geojson["features"]:
        feature.pop("id", None)
        feature["geometry"] = json.loads(
            json.dumps(as_multipolygon(feature["geometry"])),
            parse_float=lambda value: round(float(value), 3),
        )

    config.DISTRICTS_GEOJSON.write_text(json.dumps(geojson, separators=(",", ":")))
    size_mb = config.DISTRICTS_GEOJSON.stat().st_size / 1e6
    print(
        f"Saved {len(geojson['features'])} districts to {config.DISTRICTS_GEOJSON} "
        f"({size_mb:.1f} MB)"
    )


if __name__ == "__main__":
    main()
