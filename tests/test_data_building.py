import pandas as pd
import pytest

from build_features import past_anomaly
from build_fci_stocks import parse_grid
from build_wpi import chain_link
from clean_data import fill_gaps


def test_chain_link_keeps_every_monthly_change():
    months = pd.period_range("2020-01", "2020-06", freq="M")
    old = pd.DataFrame({"wheat": [50.0, 51.0, 52.0, 53.0, 54.0, 55.0]}, index=months)
    new = pd.DataFrame({"wheat": [100.0, 103.0, 104.0]}, index=months[3:])

    linked = chain_link([("old", old), ("new", new)])

    # From the link month on, the values are the new series.
    assert linked.loc[months[3] :, "wheat"].tolist() == [100.0, 103.0, 104.0]
    # Before it, the old series' monthly changes are kept exactly.
    expected = old["wheat"].pct_change().loc[months[1] : months[3]]
    actual = linked["wheat"].astype(float).pct_change().loc[months[1] : months[3]]
    assert actual.tolist() == pytest.approx(expected.tolist())


def test_fill_gaps_interpolates_and_flags():
    table = pd.DataFrame(
        {
            "state": ["A"] * 3,
            "district": ["x"] * 3,
            "month": ["2020-01", "2020-02", "2020-03"],
            "ndvi": [0.4, 0.1, 0.6],
        }
    )
    unreliable = pd.Series([False, True, False])
    filled = fill_gaps(table, "ndvi", unreliable, decimals=4)
    assert filled["ndvi"].tolist() == [0.4, 0.5, 0.6]
    assert filled["is_filled"].tolist() == [False, True, False]


def test_past_anomaly_uses_previous_years_only():
    calendar_month = pd.Series([3, 3, 3, 3, 3])
    values = pd.Series([1.0, 2.0, 3.0, 4.0, 100.0])
    anomaly = past_anomaly(values, calendar_month)
    # The first three years have no history (at least three earlier years needed).
    assert anomaly.iloc[:3].isna().all()
    # Year 4 is compared with the mean of years 1 to 3 only.
    assert anomaly.iloc[3] == pytest.approx(4.0 - 2.0)
    # Year 5's spike does not change year 4's anomaly, and uses years 1 to 4.
    assert anomaly.iloc[4] == pytest.approx(100.0 - 2.5)


def test_parse_grid_reads_rows_even_with_a_garbled_label():
    text = "\n".join(
        [
            "2015 (Rice) 10.00 20.00",
            "~~ (Whe@t garbled 30.00 40.00",
            "(Coarsegrains) 1.00 2.00",
            "(Total) 41.00 62.00",
            "01.01.2015 99.99 99.99 99.99",
        ]
    )
    stocks = parse_grid(text, first_year=2015)
    assert stocks["month"].tolist() == ["2015-01", "2015-02"]
    assert stocks["wheat"].tolist() == [30.0, 40.0]
    assert stocks["rice"].tolist() == [10.0, 20.0]
