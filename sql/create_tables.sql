CREATE SEQUENCE IF NOT EXISTS seq_players START 1;

CREATE TABLE IF NOT EXISTS players (
    player_id INTEGER PRIMARY KEY DEFAULT nextval('seq_players'),
    player_name VARCHAR NOT NULL UNIQUE
);