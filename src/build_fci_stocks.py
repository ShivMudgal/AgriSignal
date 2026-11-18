"""Build monthly wheat and rice stocks in the central pool from 2005 onwards.

The numbers come from the monthly Foodgrains Bulletin of the Department of
Food and Public Distribution. Each bulletin has a table of stocks on the 1st
of every month for roughly the last three years, so a handful of bulletins
covers the whole period, with overlaps used as a check.

2005 to 2011 comes from data/raw/fci_stocks_transcribed.csv, typed in from the
November 2011 bulletin, which only survives as a scanned image (Internet
Archive copy of dfpd.nic.in/fcamin/sites/default/files/userfiles/FB_Nov2011.pdf).
The March 2009 bulletin, which has a text layer, is used to check it.
"""

import re

import pandas as pd
import requests
from pypdf import PdfReader

import config

BULLETIN_SITE = "https://dfpd.gov.in/WriteReadData/FoodBulletinUploadDocuments"

# Newest first: when bulletins disagree about a month, the newest one wins.
# "grid" tables have a block of rice, wheat, coarse grain and total rows per
# year. "dated" tables have one row per date: wheat, rice, total and nutri
# cereals, with the stocking norm after each value in some rows.
BULLETINS = [
    {
        "name": "October 2026",
        "file": "1b5db9b4-ca3d-4a80-b41c-74d4a8f93560_Food%20Bulletin%20For%20October,%202026.pdf",
        "page": 12,
        "layout": "dated",
    },
    {
        "name": "January 2024",
        "file": "394b8ba8-56e1-4c68-a8fc-cd360b3d2707_Foodgrain%20Bulletin%20for%20January,2024.pdf",
        "page": 9,
        "layout": "grid",
        "first_year": 2021,
    },
    {
        "name": "January 2022",
        "file": "22801696-1ca2-4192-8562-459e965fa90d_FoodgrainBulletinforJanuary2022Bilingual.pdf",
        "page": 9,
        "layout": "grid",
        "first_year": 2019,
    },
    {
        "name": "January 2019",
        "file": "0568bd74-d63e-4fdc-9724-fdc346de8e28_January2019.pdf",
        "page": 9,
        "layout": "grid",
        "first_year": 2016,
    },
    {
        "name": "January 2016",
        "file": "61076836-ebb0-4945-8768-39663e49734a_2016janEng.pdf",
        "page": 10,
        "layout": "grid",
        "first_year": 2013,
    },
    {
        "name": "January 2015",
        "file": "dae9f886-98e4-43cf-8b24-d6215b40ca19_jan_2015.pdf",
        "page": 10,
        "layout": "grid",
        "first_year": 2012,
    },
]

# Used only to check the transcribed 2005 to April 2009 values.
MARCH_2009 = {
    "file": "d540df2e-387b-4c70-a575-cf15efc0c13d_march_2009.pdf",
    "page": 47,
}

NUMBER = re.compile(r"\d+\.\d{2}")
DATE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun"]
MONTHS += ["jul", "aug", "sep", "oct", "nov", "dec"]

# Printed totals are rounded, so allow a little slack in the sum check.
SUM_TOLERANCE = 0.05


def bulletin_page_text(file: str, page: int) -> str:
    """Download a bulletin (unless already saved) and return one page's text."""
    path = config.FCI_DOWNLOAD_DIR / file.split("_", 1)[1].replace("%20", "_")
    if not path.exists():
        url = f"{BULLETIN_SITE}/{file}"
        try:
            response = requests.get(
                url, headers={"User-Agent": "Mozilla/5.0"}, timeout=180
            )
            response.raise_for_status()
        except requests.RequestException as error:
            raise SystemExit(
                f"Could not download {url} ({error}).\n"
                f"Download it in a browser and save it as {path}"
            )
        path.write_bytes(response.content)
    return PdfReader(path).pages[page - 1].extract_text()


def parse_grid(text: str, first_year: int) -> pd.DataFrame:
    """Read a year x month table: rice, wheat, coarse grain and total rows."""
    rows = []
    for line in text.splitlines():
        if DATE.match(line.strip()):
            continue  # quarterly table printed under the main one
        numbers = [float(n) for n in NUMBER.findall(line)]
        if numbers:
            rows.append((line.lower(), numbers))

    # Each year starts with a rice row. The next three rows with the same
    # number of values are wheat, coarse grains and total, whatever their
    # (sometimes garbled) labels say.
    records = []
    year = first_year
    i = 0
    while i < len(rows):
        label, rice = rows[i]
        if "rice" not in label:
            i += 1
            continue
        block = [rice]
        j = i + 1
        while len(block) < 4 and j < len(rows):
            if len(rows[j][1]) == len(rice):
                block.append(rows[j][1])
            j += 1
        if len(block) < 4:
            break
        for month, values in enumerate(zip(*block), start=1):
            records.append(
                {
                    "month": f"{year}-{month:02d}",
                    "rice": values[0],
                    "wheat": values[1],
                    "coarse_grains": values[2],
                    "printed_total": values[3],
                }
            )
        year += 1
        i = j
    return pd.DataFrame(records)


def parse_dated(text: str) -> pd.DataFrame:
    """Read a table with one row per date (wheat, rice, total, nutri cereals)."""
    tokens = [t.strip() for t in text.splitlines() if t.strip()]
    records = []
    for i, token in enumerate(tokens):
        date = DATE.fullmatch(token)
        if not date:
            continue
        values = []
        for nxt in tokens[i + 1 :]:
            if not NUMBER.fullmatch(nxt):
                break
            values.append(float(nxt))
        # Rows with stocking norms have 7 values: actual, norm, actual, ...
        if len(values) == 7:
            values = values[0::2]
        if len(values) != 4:
            continue
        day, month, year = date.groups()
        records.append(
            {
                "month": f"{year}-{month}",
                "wheat": values[0],
                "rice": values[1],
                "coarse_grains": values[3],
                # The printed total here is wheat plus rice only, so add the
                # cereals to make it comparable with the grid tables.
                "printed_total": values[2] + values[3],
            }
        )
    return pd.DataFrame(records)


def read_bulletins() -> pd.DataFrame:
    """Parse every bulletin into one long table, tagged with its source."""
    tables = []
    for priority, bulletin in enumerate(BULLETINS):
        text = bulletin_page_text(bulletin["file"], bulletin["page"])
        if bulletin["layout"] == "grid":
            table = parse_grid(text, bulletin["first_year"])
        else:
            table = parse_dated(text)
        print(
            f"  {bulletin['name']}: {len(table)} months "
            f"({table['month'].min()} to {table['month'].max()})"
        )
        tables.append(table.assign(source=bulletin["name"], priority=priority))
    return pd.concat(tables, ignore_index=True)


def read_transcribed() -> pd.DataFrame:
    """Reshape the hand-typed 2005 to 2011 table into one row per month."""
    wide = pd.read_csv(config.FCI_TRANSCRIBED_CSV)
    long = wide.melt(id_vars=["year", "item"], var_name="name", value_name="value")
    long["month"] = (
        long["year"].astype(str)
        + "-"
        + (long["name"].map(MONTHS.index) + 1).astype(str).str.zfill(2)
    )
    table = long.pivot(index="month", columns="item", values="value").reset_index()
    table = table.rename(columns={"total": "printed_total"})
    return table.assign(source="November 2011 (transcribed)", priority=len(BULLETINS))


def check_sums(stocks: pd.DataFrame) -> None:
    """Report months where the parts do not add up to the printed total."""
    parts = stocks["rice"] + stocks["wheat"] + stocks["coarse_grains"]
    off = stocks[(parts - stocks["printed_total"]).abs() > SUM_TOLERANCE]
    print(f"Sum check: {len(stocks) - len(off)} of {len(stocks)} rows add up")
    for row in off.itertuples():
        print(
            f"  {row.source} {row.month}: parts {parts[row.Index]:.2f}, "
            f"printed total {row.printed_total:.2f}"
        )


def check_transcription(transcribed: pd.DataFrame) -> None:
    """Every transcribed value up to April 2009 should be in the 2009 bulletin."""
    text = bulletin_page_text(MARCH_2009["file"], MARCH_2009["page"])
    printed = set(NUMBER.findall(text))
    early = transcribed[transcribed["month"] <= "2009-04"]
    missing = [
        (row.month, item, f"{getattr(row, item):.2f}")
        for row in early.itertuples()
        for item in ["rice", "wheat", "coarse_grains", "printed_total"]
        if f"{getattr(row, item):.2f}" not in printed
    ]
    print(
        f"Transcription check: {len(early) * 4 - len(missing)} of {len(early) * 4} "
        "values found in the March 2009 bulletin"
    )
    for month, item, value in missing:
        print(f"  not found: {month} {item} {value}")


def check_overlaps(stocks: pd.DataFrame) -> None:
    """Compare months reported by more than one bulletin."""
    repeated = stocks[stocks.duplicated("month", keep=False)]
    spread = repeated.groupby("month")[["wheat", "rice"]].agg(
        lambda s: s.max() - s.min()
    )
    changed = spread[(spread > 0.01).any(axis=1)]
    print(
        f"Overlap check: {len(spread)} months appear in more than one bulletin, "
        f"{len(changed)} were revised (largest change: wheat "
        f"{spread['wheat'].max():.2f}, rice {spread['rice'].max():.2f} lakh tonnes)"
    )


def main() -> None:
    config.FCI_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    print("Reading bulletins")
    bulletins = read_bulletins()
    transcribed = read_transcribed()
    stocks = pd.concat([bulletins, transcribed], ignore_index=True)

    check_sums(stocks)
    check_transcription(transcribed)
    check_overlaps(stocks)

    # Keep the newest bulletin's figure for each month.
    stocks = stocks.sort_values("priority").drop_duplicates("month")
    start = config.START_DATE[:7]
    end = config.END_DATE[:7]
    stocks = stocks[(stocks["month"] >= start) & (stocks["month"] < end)]
    stocks = stocks.sort_values("month")[["month", "wheat", "rice", "source"]]
    stocks = stocks.rename(columns={"wheat": "wheat_lakh_t", "rice": "rice_lakh_t"})

    expected = pd.period_range(start, end, freq="M")[:-1].astype(str)
    missing = sorted(set(expected) - set(stocks["month"]))
    if missing:
        raise SystemExit(f"Missing months: {', '.join(missing)}")

    stocks.to_csv(config.FCI_STOCKS_CSV, index=False, lineterminator="\n")
    print(f"Saved {len(stocks)} months to {config.FCI_STOCKS_CSV}")


if __name__ == "__main__":
    main()
