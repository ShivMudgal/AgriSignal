"""Load the cleaned data into the AgriSignal database (SQLite by default)."""

import pandas as pd
from sqlalchemy import Engine, create_engine, event, text

import config


def connect(url: str) -> Engine:
    """Create a database engine. SQLite needs foreign key checks switched on."""
    engine = create_engine(url)
    if engine.dialect.name == "sqlite":
        config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _record) -> None:
            connection.execute("PRAGMA foreign_keys = ON")

    return engine


def create_tables(engine: Engine) -> None:
    """Drop and recreate every table from sql/schema.sql."""
    statements = config.SCHEMA_SQL.read_text().split(";")
    with engine.begin() as connection:
        for statement in statements:
            if statement.strip():
                connection.execute(text(statement))


def first_of_month(months: pd.Series) -> pd.Series:
    """Turn '2024-03' into '2024-03-01' so it fits a DATE column."""
    return months + "-01"


def build_districts(ndvi: pd.DataFrame) -> pd.DataFrame:
    """Return one row per district with a numeric id and crop flags."""
    districts = (
        ndvi[["state", "district"]]
        .drop_duplicates()
        .sort_values(["state", "district"])
        .reset_index(drop=True)
    )
    districts.insert(0, "district_id", districts.index + 1)
    districts["in_wheat_states"] = districts["state"].isin(config.WHEAT_STATES)
    districts["in_rice_states"] = districts["state"].isin(config.RICE_STATES)
    return districts


def with_district_id(table: pd.DataFrame, districts: pd.DataFrame) -> pd.DataFrame:
    """Swap the state and district names for the district_id key."""
    table = table.merge(districts[["district_id", "state", "district"]], how="left")
    if table["district_id"].isna().any():
        raise SystemExit("Some rows did not match a district.")
    table["month"] = first_of_month(table["month"])
    return table.drop(columns=["state", "district"])


def load(engine: Engine, name: str, table: pd.DataFrame) -> None:
    """Append a table's rows to the database table of the same name."""
    table.to_sql(name, engine, if_exists="append", index=False)
    print(f"  {name}: {len(table)} rows")


def main() -> None:
    ndvi = pd.read_csv(config.NDVI_CLEAN_CSV)
    rainfall = pd.read_csv(config.RAINFALL_CLEAN_CSV)
    wpi = pd.read_csv(config.WPI_CSV)
    wpi["month"] = first_of_month(wpi["month"])

    districts = build_districts(ndvi)

    engine = connect(config.DATABASE_URL)
    create_tables(engine)
    print(f"Loading into {engine.url.render_as_string(hide_password=True)}")
    load(engine, "districts", districts)
    load(engine, "ndvi", with_district_id(ndvi, districts))
    load(engine, "rainfall", with_district_id(rainfall, districts))
    load(engine, "wpi", wpi)


if __name__ == "__main__":
    main()
