"""Build monthly all-India wholesale price indices (WPI) for wheat and paddy.

WPI is published as two series with different base years. The old series
(base 2011-12) runs to April 2026 and the new one (base 2022-23) starts in
April 2023. The office publishes linking factors only for major groups, so
each crop gets its own factor: the old/new ratio in April 2023, the first
month both series cover. This keeps every month-to-month change of the old
series before the switch and of the new series after it.
"""

import pandas as pd
import requests

import config

WPI_SITE = "https://eaindustry.nic.in"
OLD_SERIES_URL = f"{WPI_SITE}/indx_download_1112/monthly_index_202606.xls"
NEW_SERIES_URL = f"{WPI_SITE}/indx_download_2223/wpi_monthly_index_202611.xlsx"

# Item codes are the same in both series.
CROP_CODES = {"paddy": 1101010101, "wheat": 1101010102}

LINK_MONTH = "2023-04"


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


def crop_rows(
    sheet: pd.DataFrame, code_column: int, first_month_column: int, month_format: str
) -> pd.DataFrame:
    """Return a month x crop table of index values from one WPI sheet."""
    months = pd.to_datetime(
        sheet.iloc[0, first_month_column:].astype(str), format=month_format
    ).dt.to_period("M")
    codes = pd.to_numeric(sheet.iloc[:, code_column], errors="coerce")

    table = {}
    for crop, code in CROP_CODES.items():
        row = sheet[codes == code].iloc[0]
        table[crop] = row.iloc[first_month_column:].astype(float).to_numpy()
    return pd.DataFrame(table, index=months)


def linking_factors(old: pd.DataFrame, new: pd.DataFrame) -> pd.Series:
    """Return the old/new index ratio in the linking month, per crop."""
    month = pd.Period(LINK_MONTH, "M")
    return old.loc[month] / new.loc[month]


def splice(old: pd.DataFrame, new: pd.DataFrame, factors: pd.Series) -> pd.DataFrame:
    """Join the rescaled old series with the new one, in long format."""
    switch = pd.Period(LINK_MONTH, "M")
    old_part = (old[old.index < switch] / factors).assign(series="2011-12 linked")
    new_part = new[new.index >= switch].assign(series="2022-23")

    wide = pd.concat([old_part, new_part])
    wide.index.name = "month"
    long = wide.reset_index().melt(
        id_vars=["month", "series"], var_name="crop", value_name="wpi"
    )
    long["wpi"] = long["wpi"].round(2)

    start = pd.Period(config.START_DATE, "M")
    end = pd.Period(config.END_DATE, "M")
    long = long[(long["month"] >= start) & (long["month"] < end)]
    long["month"] = long["month"].astype(str)
    return long[["crop", "month", "wpi", "series"]].sort_values(["crop", "month"])


def main() -> None:
    config.WPI_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # Old file: name, code, weight, then INDX042012 ... columns.
    old = crop_rows(download(OLD_SERIES_URL), 1, 3, "INDX%m%Y")
    # New file: level, name, code, weight, then Apr-23 ... columns.
    new = crop_rows(download(NEW_SERIES_URL), 2, 4, "%b-%y")

    factors = linking_factors(old, new)
    for crop, factor in factors.items():
        print(f"Linking factor for {crop}: {factor:.4f}")

    wpi = splice(old, new, factors)
    wpi.to_csv(config.WPI_CSV, index=False)
    print(
        f"Saved {len(wpi)} rows to {config.WPI_CSV} "
        f"({wpi['month'].min()} to {wpi['month'].max()})"
    )


if __name__ == "__main__":
    main()
