-- Raw tables for pickem. Idempotent: safe to re-run.
-- Order matters: parents before children (foreign keys).

-- Sequences ("take a number" counters)
CREATE SEQUENCE IF NOT EXISTS seq_players      START 1;
CREATE SEQUENCE IF NOT EXISTS seq_teams        START 1;
CREATE SEQUENCE IF NOT EXISTS seq_schedule     START 1;
CREATE SEQUENCE IF NOT EXISTS seq_weekly_games START 1;
CREATE SEQUENCE IF NOT EXISTS seq_picks        START 1;

CREATE TABLE IF NOT EXISTS players (
    player_id   INTEGER PRIMARY KEY DEFAULT nextval('seq_players'),
    player_name VARCHAR NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS teams (
    team_id           INTEGER PRIMARY KEY DEFAULT nextval('seq_teams'),
    team_name         VARCHAR NOT NULL,
    division          VARCHAR NOT NULL,
    is_listed         BOOLEAN NOT NULL DEFAULT FALSE,
    list_type         VARCHAR,
    nominating_player INTEGER REFERENCES players (player_id),
    espn_team_id      VARCHAR UNIQUE,
    odds_api_name     VARCHAR
);

CREATE TABLE IF NOT EXISTS weeks (
    week_id     INTEGER PRIMARY KEY,
    week_number INTEGER NOT NULL UNIQUE,
    CHECK (week_id = week_number)
);

CREATE TABLE IF NOT EXISTS rankings (
    week_id   INTEGER NOT NULL REFERENCES weeks (week_id),
    team_id   INTEGER NOT NULL REFERENCES teams (team_id),
    poll_type VARCHAR NOT NULL,
    rank      INTEGER NOT NULL CHECK (rank > 0),
    PRIMARY KEY (week_id, team_id, poll_type)
);

CREATE TABLE IF NOT EXISTS schedule (
    schedule_id   INTEGER PRIMARY KEY DEFAULT nextval('seq_schedule'),
    espn_event_id VARCHAR NOT NULL UNIQUE,
    week_id       INTEGER NOT NULL REFERENCES weeks (week_id),
    home_team_id  INTEGER NOT NULL REFERENCES teams (team_id),
    away_team_id  INTEGER NOT NULL REFERENCES teams (team_id),
    kickoff_at    TIMESTAMPTZ,
    CHECK (home_team_id <> away_team_id)
);

CREATE TABLE IF NOT EXISTS weekly_games (
    game_id          INTEGER PRIMARY KEY DEFAULT nextval('seq_weekly_games'),
    week_id          INTEGER NOT NULL REFERENCES weeks (week_id),
    schedule_id      INTEGER NOT NULL UNIQUE REFERENCES schedule (schedule_id),
    slot_number      INTEGER NOT NULL CHECK (slot_number BETWEEN 1 AND 12),
    selection_reason VARCHAR,
    score_type       VARCHAR NOT NULL CHECK (score_type IN ('standings', 'tiebreaker')),
    home_spread      DECIMAL(4,1),
    status           VARCHAR NOT NULL DEFAULT 'pending',
    UNIQUE (week_id, slot_number)
);

CREATE TABLE IF NOT EXISTS results (
    schedule_id INTEGER PRIMARY KEY REFERENCES schedule (schedule_id),
    home_score  INTEGER,
    away_score  INTEGER,
    game_status VARCHAR NOT NULL DEFAULT 'scheduled'
);

CREATE TABLE IF NOT EXISTS picks (
    pick_id        INTEGER PRIMARY KEY DEFAULT nextval('seq_picks'),
    player_id      INTEGER NOT NULL REFERENCES players (player_id),
    game_id        INTEGER NOT NULL REFERENCES weekly_games (game_id),
    picked_team_id INTEGER NOT NULL REFERENCES teams (team_id),
    submitted_at   TIMESTAMPTZ NOT NULL DEFAULT current_timestamp
);