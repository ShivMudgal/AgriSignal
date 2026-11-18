# AgriSignal: can crop health from space predict Indian grain prices?

## Summary

I measured crop health from satellites in 329 districts across India's main wheat and rice states from 2005 to 2026, and tested whether it helps predict if all-India wheat and paddy wholesale prices rise over the next 1 to 3 months.

For wheat it does. Crop health that is better than in recent years is followed by smaller price rises, a relationship that passes a Granger causality test after correcting for multiple testing. In a walk-forward test on 2012 to 2026, adding crop health to a model raises its 3-month accuracy from 73.0% to 79.9%, and only the models with crop health give better probability forecasts than a simple calendar rule. The gain over that rule in plain accuracy (75.3% to 79.9%) is not yet statistically conclusive.

For paddy it does not. Paddy prices rise almost every year, and no model beats simply predicting "up". The likely reason is that the government buys a large share of the crop at a guaranteed support price, which smooths out the effect of a good or bad harvest.

## The question

Wheat and rice prices matter for inflation, farm incomes and government food policy. Harvest problems usually show up in prices only when the crop reaches the market, a few months after the damage is visible in the fields. Satellites see the fields every few days, so the question is whether they can give an early signal of where prices are heading.

I chose to predict the direction of the price (up or not) rather than its level, because prices trend upward with inflation and a forecast of the level would mostly be a forecast of inflation.

## Data

| What | Source | Notes |
|---|---|---|
| Crop health (NDVI) | NASA MODIS Terra and Aqua via Google Earth Engine | Monthly, cropland pixels only, cloudy pixels removed |
| Rainfall | CHIRPS v3 | Monthly totals per district |
| Temperature | ERA5-Land | Monthly mean and hottest air temperature |
| Prices | Wholesale Price Index, Office of the Economic Adviser | Wheat, paddy, all commodities, food articles, diesel |
| Grain stocks and support prices | Foodgrains Bulletins, Department of Food and Public Distribution | Built from the bulletins (see below) |
| Export bans and stock limits | DGFT notifications, PIB releases, Lok Sabha answers | 8 dated events |

Three parts of the data took more than downloading:

- **Joining the price series.** The WPI changed its base year twice (2011-12 and 2022-23). I chain-linked the three series item by item at the first month of each newer series, which keeps every monthly move. My factor for all commodities (1.526) matches the official linking factor (1.53).
- **Building the grain stock series.** The only ready-made monthly series is behind a paywall, so I built it from the government's monthly bulletins: six text bulletins for 2012 to 2026, whose 57 overlapping months agree exactly, and one scanned bulletin for 2005 to 2011, which I typed in. Every typed month adds up to the printed total, and the 2005 to 2009 values also appear in a second bulletin. The checks caught one printing error in an official bulletin.
- **Replacing a drifting satellite measure.** My first temperature data, MODIS land surface temperature, showed a steady cooling after 2020 that does not exist. Both satellites' orbits have drifted, so they pass over at a different time of day. I switched to ERA5-Land, which has no such drift and still shows the real heatwaves.

## Method

1. **National series.** For each crop, the district values were averaged over the states that grow it, weighting each district by its farmland.
2. **Anomalies without hindsight.** Crop health, rain and temperature were turned into anomalies: each month minus the same calendar month in the previous five years. Using only past years keeps future information out of the features and absorbs a slow greening trend in the satellite data.
3. **Baselines.** Three simple rules set the bar: predict the more common direction so far, predict the usual direction for that calendar month, and repeat the recent direction. On 2012 to 2026 the best of them is right 68% to 75% of the time.
4. **Granger tests.** For each signal, crop and lag, I tested whether adding the signal's past values improves a forecast of next month's price change that already uses past price changes and the calendar month. With 48 tests, p-values were adjusted with the Benjamini-Hochberg method.
5. **Models.** Logistic regression and XGBoost (small trees, slow learning), each with and without crop health. They were tested walk-forward: for every month from 2012, retrained on all earlier months whose outcome was known, then asked for one prediction. Accuracy was compared with the best rule using McNemar's test, and probability forecasts with the calendar rule's using the Brier score and a Wilcoxon test.

## Results

**Granger tests.** Wheat crop health passed at all three lags (adjusted p = 0.002, 0.012, 0.039). A typical anomaly shifts next month's wheat price change by about 0.4 percentage points, about a fifth of a typical monthly move. Past price changes passed for both crops. Everything else failed: paddy crop health, heat, rainfall, stock changes, food inflation, support price changes and export bans.

**Models, wheat 3 months ahead:**

| | Accuracy | Brier score (lower is better) |
|---|---|---|
| Calendar rule | 75.3% | 0.173 |
| XGBoost without crop health | 73.0% | 0.168 (p = 0.63 vs calendar) |
| XGBoost with crop health | 79.9% | 0.150 (p = 0.016 vs calendar) |
| Logistic regression with crop health | 77.6% | 0.157 (p = 0.044 vs calendar) |

At 1 and 2 months ahead crop health added nothing, which fits how harvests work: the condition of the crop reaches prices when the harvest is sold. The edge also varies by year. The crop health model held up in 2020 to 2022, when the calendar rule fell to about 45% (the pandemic, then the 2022 heatwave and export ban), but it did poorly in 2025.

**Models, paddy.** No model beat the simple rules. At 3 months, predicting "up" every time (75.3%) was significantly better than every model.

## What did not work

- **Rainfall.** On 2018 to 2026 data alone, paddy rainfall looked as strong a signal as crop health. With data back to 2005 it disappeared. Much of India's wheat and rice is irrigated; in August 2012, Punjab had 25% less rain than normal and its crops were greener than usual.
- **Paddy crop health.** Its correlation with prices mostly came from a slow upward trend in the satellite data, and it vanished once the anomalies used only past years.
- **Heat.** Hot months did go with larger price rises, but that information was already in past prices.
- **Satellite temperature.** Replaced because of orbit drift, as described above.

## Limitations

- About 225 months of usable data is a small sample, so even real effects are hard to prove; with this many comparisons the 3-month wheat result is best read as strong evidence rather than proof.
- NDVI does not separate crops. In the monsoon season it includes cotton and soybean as well as rice.
- Before April 2012 the paddy price is the rice index.
- Stocks, support prices and export bans partly react to prices, so their relationships run both ways.
- The forecasts are an illustration of the method, not trading advice.

## Next steps

- Use crop health only from the weeks that matter most for each crop (grain filling for wheat, heading for rice) instead of whole months.
- Look at state-level prices, where local crop failures may matter more than in the national average.
- Re-run the tests as new months arrive, to see whether the wheat result holds up out of sample.
