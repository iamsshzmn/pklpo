\set ON_ERROR_STOP on

INSERT INTO ops.symbol_succession
    (old_symbol, new_symbol, inst_type, venue, event_type, ratio,
     old_stop_ts, new_start_ts,
     price_continuity_checked, contract_specs_checked,
     source_url, status, notes, effective_from, known_from, approved_at)
VALUES
    ('TON-USDT-SWAP', 'GRAM-USDT-SWAP', 'SWAP', 'OKX', 'token_migration', 1,
     '2026-06-16T08:00:00Z'::timestamptz,
     '2026-06-17T10:30:00Z'::timestamptz,
     true,
     true,
     'https://www.okx.com/help/okx-to-support-ton-crypto-migration',
     'approved',
     '{
        "migration": "TON->GRAM 1:1",
        "old_stop_utc": "2026-06-16T08:00:00Z",
        "new_start_utc": "2026-06-17T10:30:00Z",
        "price_continuity_checked": true,
        "contract_specs_checked": true,
        "price_continuity_basis": "last available TON raw close vs first real GRAM backfilled close; missing TON interval remains unknown_raw_gap",
        "gap_metadata": "ops.gap_classification carries unknown_raw_gap and migration_halt rows",
        "evidence_docs": [
          "Captains_Logbook/planning/data_layers/task3_1_gram_backfill_2026-07-03.md",
          "Captains_Logbook/planning/data_layers/task3_2_ton_archive_decision_2026-07-03.md",
          "Captains_Logbook/planning/data_layers/task3_3_gap_classification_ton_gram_2026-07-03.md"
        ]
      }'::jsonb,
     '2026-06-17T10:30:00Z'::timestamptz,
     '2026-07-03T00:00:00Z'::timestamptz,
     '2026-07-03T00:00:00Z'::timestamptz)
ON CONFLICT (venue, inst_type, old_symbol, new_symbol) DO UPDATE SET
    event_type = EXCLUDED.event_type,
    ratio = EXCLUDED.ratio,
    old_stop_ts = EXCLUDED.old_stop_ts,
    new_start_ts = EXCLUDED.new_start_ts,
    price_continuity_checked = EXCLUDED.price_continuity_checked,
    contract_specs_checked = EXCLUDED.contract_specs_checked,
    source_url = EXCLUDED.source_url,
    status = EXCLUDED.status,
    notes = EXCLUDED.notes,
    effective_from = EXCLUDED.effective_from,
    known_from = EXCLUDED.known_from,
    approved_at = EXCLUDED.approved_at,
    updated_at = now()
WHERE ops.symbol_succession.event_type IS DISTINCT FROM EXCLUDED.event_type
   OR ops.symbol_succession.ratio IS DISTINCT FROM EXCLUDED.ratio
   OR ops.symbol_succession.old_stop_ts IS DISTINCT FROM EXCLUDED.old_stop_ts
   OR ops.symbol_succession.new_start_ts IS DISTINCT FROM EXCLUDED.new_start_ts
   OR ops.symbol_succession.price_continuity_checked IS DISTINCT FROM EXCLUDED.price_continuity_checked
   OR ops.symbol_succession.contract_specs_checked IS DISTINCT FROM EXCLUDED.contract_specs_checked
   OR ops.symbol_succession.source_url IS DISTINCT FROM EXCLUDED.source_url
   OR ops.symbol_succession.status IS DISTINCT FROM EXCLUDED.status
   OR ops.symbol_succession.notes IS DISTINCT FROM EXCLUDED.notes
   OR ops.symbol_succession.effective_from IS DISTINCT FROM EXCLUDED.effective_from
   OR ops.symbol_succession.known_from IS DISTINCT FROM EXCLUDED.known_from
   OR ops.symbol_succession.approved_at IS DISTINCT FROM EXCLUDED.approved_at;
