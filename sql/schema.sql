-- AgriSignal database. Works on both SQLite and PostgreSQL.
-- Months are stored as the first day of the month, e.g. 2024-03-01.

DROP VIEW IF EXISTS district_month;
DROP TABLE IF EXISTS ndvi;
DROP TABLE IF EXISTS rainfall;
DROP TABLE IF EXISTS districts;
DROP TABLE IF EXISTS wpi;

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

CREATE TABLE wpi (
    crop   TEXT NOT NULL CHECK (crop IN ('wheat', 'paddy')),
    month  DATE NOT NULL,
    wpi    REAL NOT NULL CHECK (wpi > 0),
    series TEXT NOT NULL,
    PRIMARY KEY (crop, month)
);

-- One row per district and month with crop health and rainfall side by side.
CREATE VIEW district_month AS
SELECT
    d.state,
    d.district,
    n.month,
    n.ndvi,
    n.pixel_count,
    n.is_filled,
    r.rainfall_mm
FROM ndvi AS n
JOIN rainfall AS r ON r.district_id = n.district_id AND r.month = n.month
JOIN districts AS d ON d.district_id = n.district_id;
