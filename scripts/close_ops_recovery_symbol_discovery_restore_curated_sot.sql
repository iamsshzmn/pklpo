-- Restore curated instruments_list.json as the single source of truth.
-- Idempotent: repeated runs do nothing after active rows are closed.

UPDATE ops.recovery_symbol_discovery
SET status = 'closed',
    closed_reason = 'restore_curated_sot',
    closed_at = now(),
    updated_at = now()
WHERE status = 'active'
RETURNING symbol, closed_reason, closed_at;
