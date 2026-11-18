import pandas as pd

from baselines import calendar_rule, future_up, known_outcomes


def test_future_up_marks_rises_and_unknown_months():
    wpi = pd.Series([100.0, 101.0, 100.5, 102.0])
    result = future_up(wpi, months_ahead=1)
    assert result.tolist()[:3] == [1.0, 0.0, 1.0]
    assert pd.isna(result.iloc[3])


def test_known_outcomes_only_uses_settled_months():
    outcome = pd.Series(range(10), dtype=float)
    # At month 6, a 3-month outcome is only settled for months 0 to 3.
    assert known_outcomes(outcome, position=6, months_ahead=3).tolist() == [0, 1, 2, 3]


def test_calendar_rule_ignores_the_future():
    # Two years of a 12-month pattern: the second year flips direction.
    calendar_month = pd.Series(list(range(1, 13)) * 3)
    first_year = [1.0] * 12
    outcome = pd.Series(first_year + [0.0] * 24)
    predictions = calendar_rule(outcome, calendar_month, months_ahead=1)
    # In the second year it can only have seen the first year, so it says up.
    assert predictions.iloc[13:24].eq(1.0).all()
