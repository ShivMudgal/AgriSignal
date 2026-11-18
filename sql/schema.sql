-- AgriSignal database (SQLite).
-- Months are stored as the first day of the month, e.g. 2024-03-01.

DROP VIEW IF EXISTS district_month;
DROP TABLE IF EXISTS ndvi;
DROP TABLE IF EXISTS rainfall;
DROP TABLE IF EXISTS temperature;
DROP TABLE IF EXISTS districts;
DROP TABLE IF EXISTS wpi;
DROP TABLE IF EXISTS fci_stocks;
DROP TABLE IF EXISTS msp;
DROP TABLE IF EXISTS policy_events;

CREATE TABLE districts (
    district_id     INTEGER PRIMARY KEY,
    state           TEXT NOT NULL,
    district        TEXT NOT NULL,
    in_wheat_states BOOLEAN NOT NULL,
    in_rice_states  BOOLEAN NOT NULL,
    UNIQUE (state, district)
);

CREATE TABLE ndvi (
    district_id INTEGER NOT NULL REFERENCES districts (district_id),
    month       DATE NOT NULL,
    ndvi        REAL NOT NULL CHECK (ndvi BETWEEN -1 AND 1),
    pixel_count INTEGER NOT NULL CHECK (pixel_count >= 0),
    is_filled   BOOLEAN NOT NULL,
    PRIMARY KEY (district_id, month)
);

CREATE TABLE rainfall (
    district_id INTEGER NOT NULL REFERENCES districts (district_id),
    month       DATE NOT NULL,
    rainfall_mm REAL NOT NULL CHECK (rainfall_mm >= 0),
    PRIMARY KEY (district_id, month)
);

-- Monthly mean and hottest air temperature (ERA5-Land), in degrees Celsius.
CREATE TABLE temperature (
    district_id INTEGER NOT NULL REFERENCES districts (district_id),
    month       DATE NOT NULL,
    tmean_c     REAL NOT NULL CHECK (tmean_c BETWEEN -40 AND 55),
    tmax_c      REAL NOT NULL CHECK (tmax_c BETWEEN -40 AND 60),
    is_filled   BOOLEAN NOT NULL,
    PRIMARY KEY (district_id, month)
);

CREATE TABLE wpi (
    item   TEXT NOT NULL CHECK (
        item IN ('wheat', 'paddy', 'all_commodities', 'food_articles', 'diesel')
    ),
    month  DATE NOT NULL,
    wpi    REAL NOT NULL CHECK (wpi > 0),
    series TEXT NOT NULL,
    PRIMARY KEY (item, month)
);

-- Government wheat and rice stocks on the 1st of each month, in lakh tonnes.
CREATE TABLE fci_stocks (
    month        DATE PRIMARY KEY,
    wheat_lakh_t REAL NOT NULL CHECK (wheat_lakh_t >= 0),
    rice_lakh_t  REAL NOT NULL CHECK (rice_lakh_t >= 0),
    source       TEXT NOT NULL
);

-- Minimum support price (plus any bonus) for each marketing season.
CREATE TABLE msp (
    crop            TEXT NOT NULL CHECK (crop IN ('wheat', 'paddy')),
    marketing_year  TEXT NOT NULL,
    season_start    DATE NOT NULL,
    msp_rs_per_qtl  REAL NOT NULL CHECK (msp_rs_per_qtl > 0),
    source          TEXT NOT NULL,
    PRIMARY KEY (crop, marketing_year)
);

-- Export bans and stock limits. An empty end date means still in force.
CREATE TABLE policy_events (
    event      TEXT NOT NULL,
    crop       TEXT NOT NULL CHECK (crop IN ('wheat', 'paddy')),
    start_date DATE NOT NULL,
    end_date   DATE,
    source     TEXT NOT NULL,
    PRIMARY KEY (event, crop, start_date)
);

-- One row per district and month with crop health, rainfall and temperature.
CREATE VIEW district_month AS
SELECT
    d.state,
    d.district,
    n.month,
    n.ndvi,
    n.pixel_count,
    n.is_filled,
    r.rainfall_mm,
    t.tmean_c,
    t.tmax_c
FROM ndvi AS n
JOIN rainfall AS r ON r.district_id = n.district_id AND r.month = n.month
JOIN temperature AS t ON t.district_id = n.district_id AND t.month = n.month
JOIN districts AS d ON d.district_id = n.district_id;
