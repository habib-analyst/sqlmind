"""DDL for sqlmind: SQL-native agent memory with differential consolidation."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id          INTEGER PRIMARY KEY,
    kind        TEXT NOT NULL CHECK (kind IN ('episode', 'fact')),
    step        INTEGER NOT NULL,          -- agent step when recorded
    agent_id    TEXT NOT NULL DEFAULT 'agent',
    text        TEXT NOT NULL,
    confidence  REAL NOT NULL DEFAULT 1.0,
    valid_from  INTEGER NOT NULL,          -- temporal versioning: live from this step
    valid_to    INTEGER,                   -- NULL = currently live
    tier        TEXT NOT NULL DEFAULT 'hot' CHECK (tier IN ('hot', 'core', 'merged')),
    superseded_by INTEGER REFERENCES memories(id),
    novelty     REAL,                      -- last pure-SQL novelty score
    n_tri       INTEGER NOT NULL DEFAULT 0 -- trigram count (avoids recounts)
);
CREATE INDEX IF NOT EXISTS idx_mem_live  ON memories (valid_to, tier);
CREATE INDEX IF NOT EXISTS idx_mem_step  ON memories (step);
CREATE INDEX IF NOT EXISTS idx_mem_kind  ON memories (kind, valid_to);

CREATE TABLE IF NOT EXISTS memory_trigrams (
    memory_id INTEGER NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    trigram   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tri_mid ON memory_trigrams (memory_id);
CREATE INDEX IF NOT EXISTS idx_tri_tg  ON memory_trigrams (trigram);

CREATE TABLE IF NOT EXISTS digests (
    id          INTEGER PRIMARY KEY,
    from_step   INTEGER NOT NULL,
    to_step     INTEGER NOT NULL,
    summary     TEXT NOT NULL,             -- extractive, no LLM
    n_merged    INTEGER NOT NULL,
    created_step INTEGER NOT NULL,
    valid_to    INTEGER                    -- NULL = live; set when merged away
);
CREATE INDEX IF NOT EXISTS idx_dig_live ON digests (valid_to);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""
