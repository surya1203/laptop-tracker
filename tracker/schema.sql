-- A hunt is a saved search: one column per filter, typed values only.
-- NULL (or an empty list) means "Any". List columns hold JSON arrays.
CREATE TABLE IF NOT EXISTS hunts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused')),
    brands            TEXT NOT NULL DEFAULT '[]',
    series            TEXT,
    cpu_brand         TEXT,
    cpu_family        TEXT,
    cpu_model         TEXT,
    gpu_brand         TEXT,
    gpu_models        TEXT NOT NULL DEFAULT '[]',
    vram_min_gb       INTEGER,
    ram_min_gb        INTEGER,
    ram_type          TEXT,
    storage_type      TEXT,
    storage_interface TEXT,
    storage_min_gb    INTEGER,
    screen_min_in     REAL,
    screen_max_in     REAL,
    resolution_min    TEXT,
    refresh_min_hz    INTEGER,
    panels            TEXT NOT NULL DEFAULT '[]',
    weight_max_kg     REAL,
    budget_max_inr    INTEGER,
    retailers         TEXT NOT NULL DEFAULT '[]',
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    deleted_at        TEXT  -- set while a delete can still be undone
);

-- One product page found at one retailer.
CREATE TABLE IF NOT EXISTS listings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    hunt_id       INTEGER NOT NULL REFERENCES hunts (id) ON DELETE CASCADE,
    retailer      TEXT NOT NULL,
    url           TEXT NOT NULL,
    title         TEXT NOT NULL,
    image_url     TEXT,
    model_number  TEXT,
    specs         TEXT NOT NULL DEFAULT '{}',  -- parsed, typed specs (JSON)
    raw_specs     TEXT NOT NULL DEFAULT '{}',  -- the store's spec table as found (JSON)
    state         TEXT NOT NULL DEFAULT 'new' CHECK (state IN ('new', 'tracked', 'ignored')),
    first_seen_at TEXT NOT NULL,
    last_seen_at  TEXT NOT NULL,
    UNIQUE (hunt_id, url)
);

-- One row per price check.
CREATE TABLE IF NOT EXISTS price_points (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER NOT NULL REFERENCES listings (id) ON DELETE CASCADE,
    price_inr  INTEGER,
    mrp_inr    INTEGER,
    in_stock   INTEGER NOT NULL DEFAULT 1,
    checked_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_price_points_listing ON price_points (listing_id, checked_at);

-- What was sent, so the same alert is not repeated.
CREATE TABLE IF NOT EXISTS alerts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    hunt_id    INTEGER REFERENCES hunts (id) ON DELETE CASCADE,
    listing_id INTEGER REFERENCES listings (id) ON DELETE CASCADE,
    rule       TEXT NOT NULL,
    channel    TEXT NOT NULL,
    price_inr  INTEGER,
    message    TEXT,
    sent_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alerts_listing ON alerts (listing_id, sent_at);

-- Key/value: notification channels, check frequency, quiet hours.
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
