-- Tesla headline salience study — analysis database
-- Separate from the coronial database. Nothing here touches the production DBs.
-- Default location: research/tesla-headline-salience/data/study.db (gitignored).

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Raw harvest. Brand-agnostic (Protocol 6.1). One row per URL per source.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS harvest (
    url_hash        TEXT PRIMARY KEY,          -- sha1(canonical_url)[:16]
    canonical_url   TEXT NOT NULL,
    source          TEXT NOT NULL,             -- gdelt | ccnews | sitemap | manual
    domain          TEXT NOT NULL,
    title_at_crawl  TEXT,                      -- headline as the index saw it
    seendate        TEXT,                      -- ISO8601 UTC
    query           TEXT,                      -- which frozen query surfaced it
    harvested_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (canonical_url, source)
);
CREATE INDEX IF NOT EXISTS ix_harvest_domain  ON harvest(domain);
CREATE INDEX IF NOT EXISTS ix_harvest_seendate ON harvest(seendate);

-- Harvest progress, so a long run can resume after an interruption. A five-year
-- harvest is ~7,300 API calls over several hours; without this, any interruption
-- means starting over, and a partial re-run would bias coverage toward whatever
-- date range happened to complete.
CREATE TABLE IF NOT EXISTS harvest_progress (
    query_hash   TEXT NOT NULL,
    window_start TEXT NOT NULL,
    window_end   TEXT NOT NULL,
    n_returned   INTEGER NOT NULL DEFAULT 0,
    capped       INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (query_hash, window_start, window_end)
);

-- ---------------------------------------------------------------------------
-- Incidents (Codebook 1). Manually verified clusters.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS incident (
    incident_id        TEXT PRIMARY KEY,       -- YYYYMMDD-STATE-nn
    incident_date      TEXT NOT NULL,
    state              TEXT NOT NULL CHECK (state IN ('NSW','VIC','QLD','WA','SA','TAS','NT','ACT')),
    locality           TEXT,
    remoteness         TEXT CHECK (remoteness IN ('metro','regional','remote') OR remoteness IS NULL),
    deaths             INTEGER NOT NULL DEFAULT 0,
    serious_injuries   INTEGER NOT NULL DEFAULT 0,
    victim_child       INTEGER NOT NULL DEFAULT 0,
    incident_type      TEXT CHECK (incident_type IN (
                          'pedestrian_cyclist_struck','single_vehicle_fire',
                          'occupant_fatal_collision','occupant_serious_collision','other')),
    multi_vehicle      INTEGER NOT NULL DEFAULT 0,
    fire_involved      INTEGER NOT NULL DEFAULT 0,
    index_make         TEXT,                   -- canonical (lexicon.canonical_make)
    index_model        TEXT,
    index_vehicle_year INTEGER,
    index_is_bev       INTEGER,
    second_make        TEXT,
    all_makes          TEXT,                   -- pipe-separated, >=3 vehicles
    make_tier          INTEGER CHECK (make_tier IN (1,2) OR make_tier IS NULL),
    make_source        TEXT,                   -- URL / police release id / coronial ref
    adas_alleged       INTEGER NOT NULL DEFAULT 0,
    driver_notable     INTEGER NOT NULL DEFAULT 0,
    vehicle_age_band   TEXT CHECK (vehicle_age_band IN ('<=2y','3-7y','>=8y','unknown')),
    is_seed_example    INTEGER NOT NULL DEFAULT 0,  -- excluded from analysis (Protocol 13)
    eligible           INTEGER NOT NULL DEFAULT 0,
    exclusion_reason   TEXT,
    coded_by           TEXT,
    coded_at           TEXT,
    notes              TEXT
);
CREATE INDEX IF NOT EXISTS ix_incident_make ON incident(index_make);

-- ---------------------------------------------------------------------------
-- Articles (Codebook 2). One row per article; body text lives on disk, not here.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS article (
    article_id            TEXT PRIMARY KEY,
    incident_id           TEXT REFERENCES incident(incident_id) ON DELETE CASCADE,
    url                   TEXT NOT NULL UNIQUE,
    outlet                TEXT NOT NULL,
    outlet_group          TEXT NOT NULL,
    outlet_register       TEXT NOT NULL CHECK (outlet_register IN
                             ('tabloid','broadsheet','broadcast','public','wire','aggregator')),
    publish_datetime      TEXT,
    headline              TEXT NOT NULL,
    headline_source       TEXT CHECK (headline_source IN ('wayback','gdelt','ccnews','live')),
    headline_captured_at  TEXT,
    standfirst            TEXT,
    is_wire               INTEGER NOT NULL DEFAULT 0,
    syndication_group_id  TEXT,
    article_wordcount     INTEGER,
    substantive           INTEGER NOT NULL DEFAULT 1,
    excluded              INTEGER NOT NULL DEFAULT 0,
    exclusion_reason      TEXT,

    -- outcomes (automated, from lexicon.py)
    headline_names_make        INTEGER,
    headline_names_make_strict INTEGER,
    headline_names_second_make INTEGER,
    body_names_make            INTEGER,
    first_mention_position     TEXT CHECK (first_mention_position IN
                                  ('headline','standfirst','first_paragraph','later_body','absent')
                                  OR first_mention_position IS NULL),
    coded_at              TEXT
);
CREATE INDEX IF NOT EXISTS ix_article_incident ON article(incident_id);
CREATE INDEX IF NOT EXISTS ix_article_outlet   ON article(outlet_group);
CREATE INDEX IF NOT EXISTS ix_article_synd     ON article(syndication_group_id);

-- ---------------------------------------------------------------------------
-- Dual-coding record (Codebook 4). Kept so reliability can be recomputed, and so
-- disagreements survive rather than being silently overwritten by the adjudicator.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dual_coding (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_type     TEXT NOT NULL CHECK (unit_type IN ('incident','article')),
    unit_id       TEXT NOT NULL,
    variable      TEXT NOT NULL,
    coder         TEXT NOT NULL,
    value         TEXT,
    coded_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (unit_type, unit_id, variable, coder)
);

-- ---------------------------------------------------------------------------
-- Provenance. Which frozen artefacts produced the current dataset.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS provenance (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    recorded_at TEXT NOT NULL DEFAULT (datetime('now'))
);
-- expected keys: protocol_sha, lexicon_sha, queries_sha, harvest_completed_at,
--                dataset_locked_at, osf_registration_doi

-- ---------------------------------------------------------------------------
-- Analysis view: eligible, substantive, non-seed articles only.
-- ---------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS v_analysis AS
SELECT
    a.article_id, a.incident_id, a.outlet, a.outlet_group, a.outlet_register,
    a.is_wire, a.syndication_group_id, a.headline,
    a.headline_names_make, a.headline_names_make_strict,
    a.headline_names_second_make, a.body_names_make, a.first_mention_position,
    i.incident_date, i.state, i.remoteness,
    CAST(strftime('%Y', i.incident_date) AS INTEGER) AS year,
    i.deaths, i.serious_injuries, i.victim_child, i.incident_type,
    i.multi_vehicle, i.fire_involved, i.adas_alleged, i.driver_notable,
    i.index_make, i.second_make, i.make_tier, i.vehicle_age_band,
    CASE WHEN i.index_make = 'Tesla' THEN 1 ELSE 0 END AS tesla
FROM article a
JOIN incident i ON i.incident_id = a.incident_id
WHERE i.eligible = 1
  AND i.is_seed_example = 0
  AND a.excluded = 0
  AND a.substantive = 1;
