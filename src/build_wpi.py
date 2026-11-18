"""Build monthly all-India wholesale price indices (WPI) from 2005 onwards.

WPI has been published with three base years: 2004-05 (2005 to March 2017),
2011-12 (April 2012 to April 2026) and 2022-23 (from April 2023). The office
publishes linking factors only for major groups, so each item is chain-linked
on its own: an older series is rescaled so it matches the newer one in the
newer series' first month. This keeps every month-to-month change of each
series, and all values end up on the 2022-23 base.

Before April 2012 there is no paddy index, so the rice index stands in for it.
"""

import pandas as pd
import requests

import config

WPI_SITE = "https://eaindustry.nic.in"

# Oldest first. Item codes for diesel changed between series.
SERIES = [
    {
        "label": "2004-05",
        "urls": [
            f"{WPI_SITE}/indx_download_0405/month2till2012.xls",
            f"{WPI_SITE}/indx_download_0405/month2.xls",
        ],
        "code_column": 1,
        "first_month_column": 3,
        "month_format": "INDX%m%Y",
        "codes": {
            "wheat": 1101010102,
            "paddy": 1101010101,  # listed as Rice in this series
            "all_commodities": 1000000000,
            "food_articles": 1101000000,
            "diesel": 1200020005,
        },
    },
    {
        "label": "2011-12",
        "urls": [f"{WPI_SITE}/indx_download_1112/monthly_index_202606.xls"],
        "code_column": 1,
        "first_month_column": 3,
        "month_format": "INDX%m%Y",
        "codes": {
            "wheat": 1101010102,
            "paddy": 1101010101,
            "all_commodities": 1000000000,
            "food_articles": 1101000000,
            "diesel": 1202000005,
        },
    },
    {
        "label": "2022-23",
        "urls": [f"{WPI_SITE}/indx_download_2223/wpi_monthly_index_202611.xlsx"],
        "code_column": 2,
        "first_month_column": 4,
        "month_format": "%b-%y",
        "codes": {
            "wheat": 1101010102,
            "paddy": 1101010101,
            "all_commodities": 1000000000,
            "food_articles": 1101000000,
            "diesel": 1202010005,
        },
    },
]


def download(url: str) -> pd.DataFrame:
    """Download one WPI file (unless already saved) and read it with no header."""
    path = config.WPI_DOWNLOAD_DIR / url.rsplit("/", 1)[-1]
    if not path.exists():
        try:
            response = requests.get(url, timeout=120)
            response.raise_for_status()
        except requests.RequestException as error:
            # The site sometimes sends an incomplete certificate chain, which
            # Python rejects even though browsers accept it.
            raise SystemExit(
                f"Could not download {url} ({error}).\n"
                f"Download it in a browser and save it as {path}"
            )
        path.write_bytes(response.content)
    # calamine reads both the old .xls and the new .xlsx format.
    return pd.read_excel(path, header=None, engine="calamine")


def item_rows(sheet: pd.DataFrame, series: dict) -> pd.DataFrame:
    """Return a month x item table of index values from one WPI sheet."""
    first = series["first_month_column"]
    months = pd.to_datetime(
        sheet.iloc[0, first:].astype(str), format=series["month_format"]
    ).dt.to_period("M")
    codes = pd.to_numeric(sheet.iloc[:, series["code_column"]], errors="coerce")

    table = {}
    for item, code in series["codes"].items():
        row = sheet[codes == code].iloc[0]
        table[item] = row.iloc[first:].astype(float).to_numpy()
    return pd.DataFrame(table, index=months)


def read_series(series: dict) -> pd.DataFrame:
    """Read every file of one series into a single month x item table."""
    tables = [item_rows(download(url), series) for url in series["urls"]]
    return pd.concat(tables).sort_index()


def chain_link(tables: list[tuple[str, pd.DataFrame]]) -> pd.DataFrame:
    """Rescale older series onto the newest one and join them (oldest first in)."""
    label, linked = tables[-1]
    linked = linked.assign(series=label)

    for label, older in reversed(tables[:-1]):
        link_month = linked.index.min()
        newer_values = linked.loc[link_month].drop("series").astype(float)
        factors = older.loc[link_month] / newer_values
        print(
            f"Linking {label} at {link_month}: "
            + ", ".join(f"{item} {factor:.4f}" for item, factor in factors.items())
        )
        older_part = (older[older.index < link_month] / factors).assign(
            series=f"{label} linked"
        )
        linked = pd.concat([older_part, linked])
    return linked


def to_long(wide: pd.DataFrame) -> pd.DataFrame:
    """Reshape to one row per item and month, inside the study window."""
    wide.index.name = "month"
    long = wide.reset_index().melt(
        id_vars=["month", "series"], var_name="item", value_name="wpi"
    )
    long["wpi"] = long["wpi"].astype(float).round(2)

    # Mark the months where the rice index stands in for paddy.
    rice = (long["item"] == "paddy") & (long["series"] == "2004-05 linked")
    long.loc[rice, "series"] = "2004-05 linked (rice)"

    start = pd.Period(config.START_DATE, "M")
    end = pd.Period(config.END_DATE, "M")
    long = long[(long["month"] >= start) & (long["month"] < end)]
    long["month"] = long["month"].astype(str)
    return long[["item", "month", "wpi", "series"]].sort_values(["item", "month"])


def main() -> None:
    config.WPI_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    tables = [(series["label"], read_series(series)) for series in SERIES]
    wpi = to_long(chain_link(tables))

    wpi.to_csv(config.WPI_CSV, index=False, lineterminator="\n")
    print(
        f"Saved {len(wpi)} rows to {config.WPI_CSV} "
        f"({wpi['item'].nunique()} items, {wpi['month'].min()} to {wpi['month'].max()})"
    )


if __name__ == "__main__":
    main()
