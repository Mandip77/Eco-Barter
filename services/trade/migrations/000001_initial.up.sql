-- Trade Engine: initial schema
-- Run with: migrate -path ./migrations -database "$POSTGRES_DSN" up

CREATE TABLE IF NOT EXISTS items (
    id          TEXT PRIMARY KEY,
    owner_id    TEXT NOT NULL,
    category    TEXT NOT NULL,
    title       TEXT NOT NULL,
    wants       JSONB NOT NULL DEFAULT '{}',
    status      TEXT NOT NULL DEFAULT 'available',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_items_owner_id  ON items (owner_id);
CREATE INDEX IF NOT EXISTS idx_items_category  ON items (category);
CREATE INDEX IF NOT EXISTS idx_items_status    ON items (status);

CREATE TABLE IF NOT EXISTS trade_proposals (
    id          BIGSERIAL PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ,

    k           INTEGER NOT NULL DEFAULT 3,
    status      TEXT NOT NULL DEFAULT 'pending',

    user_a      TEXT NOT NULL DEFAULT '',
    item_a      TEXT NOT NULL DEFAULT '',
    verified_a  BOOLEAN NOT NULL DEFAULT FALSE,

    user_b      TEXT NOT NULL DEFAULT '',
    item_b      TEXT NOT NULL DEFAULT '',
    verified_b  BOOLEAN NOT NULL DEFAULT FALSE,

    user_c      TEXT NOT NULL DEFAULT '',
    item_c      TEXT NOT NULL DEFAULT '',
    verified_c  BOOLEAN NOT NULL DEFAULT FALSE,

    user_d      TEXT NOT NULL DEFAULT '',
    item_d      TEXT NOT NULL DEFAULT '',
    verified_d  BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_trade_proposals_deleted_at ON trade_proposals (deleted_at);
CREATE INDEX IF NOT EXISTS idx_trade_proposals_user_a     ON trade_proposals (user_a);
CREATE INDEX IF NOT EXISTS idx_trade_proposals_user_b     ON trade_proposals (user_b);
