-- Trade Engine: rollback initial schema

DROP INDEX IF EXISTS idx_trade_proposals_user_b;
DROP INDEX IF EXISTS idx_trade_proposals_user_a;
DROP INDEX IF EXISTS idx_trade_proposals_deleted_at;
DROP TABLE IF EXISTS trade_proposals;

DROP INDEX IF EXISTS idx_items_status;
DROP INDEX IF EXISTS idx_items_category;
DROP INDEX IF EXISTS idx_items_owner_id;
DROP TABLE IF EXISTS items;
