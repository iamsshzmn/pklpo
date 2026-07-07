-- Seed approved TON->GRAM gap classifications for the continuous identity plan.
-- Idempotent by semantic key; does not rewrite existing raw OHLCV.

WITH rows(
    series_id,
    timeframe,
    range_start_ts,
    range_end_ts,
    gap_type,
    recoverability,
    evidence,
    asserted_by,
    status,
    known_from,
    approved_at
) AS (
    VALUES
        -- Missing TON raw before OKX delisting. No trusted archive with provenance exists.
        ('TON-USDT-SWAP','1m',  1781068200000::bigint, 1781596800000::bigint, 'unknown_raw_gap', 'unrecoverable_without_archive',
         '{"decision":"no_trusted_ton_archive_found","evidence_docs":["Captains_Logbook/planning/data_layers/task3_2_ton_archive_decision_2026-07-03.md"],"last_ton_utc":"2026-06-10T05:09:00Z","gap_start_utc":"2026-06-10T05:10:00Z","gap_end_utc":"2026-06-16T08:00:00Z","missing_bars":8810}'::jsonb,
         'data_layers_identity_plan_task_3_3', 'approved', '2026-07-03T00:00:00Z'::timestamptz, '2026-07-03T00:00:00Z'::timestamptz),
        ('TON-USDT-SWAP','5m',  1781068200000::bigint, 1781596800000::bigint, 'unknown_raw_gap', 'unrecoverable_without_archive',
         '{"decision":"no_trusted_ton_archive_found","evidence_docs":["Captains_Logbook/planning/data_layers/task3_2_ton_archive_decision_2026-07-03.md"],"last_ton_utc":"2026-06-10T05:05:00Z","gap_start_utc":"2026-06-10T05:10:00Z","gap_end_utc":"2026-06-16T08:00:00Z","missing_bars":1762}'::jsonb,
         'data_layers_identity_plan_task_3_3', 'approved', '2026-07-03T00:00:00Z'::timestamptz, '2026-07-03T00:00:00Z'::timestamptz),
        ('TON-USDT-SWAP','15m', 1781067600000::bigint, 1781596800000::bigint, 'unknown_raw_gap', 'unrecoverable_without_archive',
         '{"decision":"no_trusted_ton_archive_found","evidence_docs":["Captains_Logbook/planning/data_layers/task3_2_ton_archive_decision_2026-07-03.md"],"last_ton_utc":"2026-06-10T04:45:00Z","gap_start_utc":"2026-06-10T05:00:00Z","gap_end_utc":"2026-06-16T08:00:00Z","missing_bars":588}'::jsonb,
         'data_layers_identity_plan_task_3_3', 'approved', '2026-07-03T00:00:00Z'::timestamptz, '2026-07-03T00:00:00Z'::timestamptz),
        ('TON-USDT-SWAP','30m', 1781067600000::bigint, 1781596800000::bigint, 'unknown_raw_gap', 'unrecoverable_without_archive',
         '{"decision":"no_trusted_ton_archive_found","evidence_docs":["Captains_Logbook/planning/data_layers/task3_2_ton_archive_decision_2026-07-03.md"],"last_ton_utc":"2026-06-10T04:30:00Z","gap_start_utc":"2026-06-10T05:00:00Z","gap_end_utc":"2026-06-16T08:00:00Z","missing_bars":294}'::jsonb,
         'data_layers_identity_plan_task_3_3', 'approved', '2026-07-03T00:00:00Z'::timestamptz, '2026-07-03T00:00:00Z'::timestamptz),
        ('TON-USDT-SWAP','1H',  1781067600000::bigint, 1781596800000::bigint, 'unknown_raw_gap', 'unrecoverable_without_archive',
         '{"decision":"no_trusted_ton_archive_found","evidence_docs":["Captains_Logbook/planning/data_layers/task3_2_ton_archive_decision_2026-07-03.md"],"last_ton_utc":"2026-06-10T04:00:00Z","gap_start_utc":"2026-06-10T05:00:00Z","gap_end_utc":"2026-06-16T08:00:00Z","missing_bars":147}'::jsonb,
         'data_layers_identity_plan_task_3_3', 'approved', '2026-07-03T00:00:00Z'::timestamptz, '2026-07-03T00:00:00Z'::timestamptz),
        ('TON-USDT-SWAP','4H',  1781064000000::bigint, 1781596800000::bigint, 'unknown_raw_gap', 'unrecoverable_without_archive',
         '{"decision":"no_trusted_ton_archive_found","evidence_docs":["Captains_Logbook/planning/data_layers/task3_2_ton_archive_decision_2026-07-03.md"],"last_ton_utc":"2026-06-10T00:00:00Z","gap_start_utc":"2026-06-10T04:00:00Z","gap_end_utc":"2026-06-16T08:00:00Z","missing_bars":37}'::jsonb,
         'data_layers_identity_plan_task_3_3', 'approved', '2026-07-03T00:00:00Z'::timestamptz, '2026-07-03T00:00:00Z'::timestamptz),
        ('TON-USDT-SWAP','12H', 1781049600000::bigint, 1781596800000::bigint, 'unknown_raw_gap', 'unrecoverable_without_archive',
         '{"decision":"no_trusted_ton_archive_found","evidence_docs":["Captains_Logbook/planning/data_layers/task3_2_ton_archive_decision_2026-07-03.md"],"last_ton_utc":"2026-06-09T12:00:00Z","gap_start_utc":"2026-06-10T00:00:00Z","gap_end_utc":"2026-06-16T08:00:00Z","missing_bars":12}'::jsonb,
         'data_layers_identity_plan_task_3_3', 'approved', '2026-07-03T00:00:00Z'::timestamptz, '2026-07-03T00:00:00Z'::timestamptz),
        ('TON-USDT-SWAP','1D',  1781049600000::bigint, 1781596800000::bigint, 'unknown_raw_gap', 'unrecoverable_without_archive',
         '{"decision":"no_trusted_ton_archive_found","evidence_docs":["Captains_Logbook/planning/data_layers/task3_2_ton_archive_decision_2026-07-03.md"],"last_ton_utc":"2026-06-09T00:00:00Z","gap_start_utc":"2026-06-10T00:00:00Z","gap_end_utc":"2026-06-16T08:00:00Z","missing_bars":6}'::jsonb,
         'data_layers_identity_plan_task_3_3', 'approved', '2026-07-03T00:00:00Z'::timestamptz, '2026-07-03T00:00:00Z'::timestamptz),
        ('TON-USDT-SWAP','1W',  1780876800000::bigint, 1781596800000::bigint, 'unknown_raw_gap', 'unrecoverable_without_archive',
         '{"decision":"no_trusted_ton_archive_found","evidence_docs":["Captains_Logbook/planning/data_layers/task3_2_ton_archive_decision_2026-07-03.md"],"last_ton_utc":"2026-06-01T00:00:00Z","gap_start_utc":"2026-06-08T00:00:00Z","gap_end_utc":"2026-06-16T08:00:00Z","missing_bars":1,"note":"coarse_bucket_overlaps_event"}'::jsonb,
         'data_layers_identity_plan_task_3_3', 'approved', '2026-07-03T00:00:00Z'::timestamptz, '2026-07-03T00:00:00Z'::timestamptz),
        ('TON-USDT-SWAP','1M',  1780272000000::bigint, 1781596800000::bigint, 'unknown_raw_gap', 'unrecoverable_without_archive',
         '{"decision":"no_trusted_ton_archive_found","evidence_docs":["Captains_Logbook/planning/data_layers/task3_2_ton_archive_decision_2026-07-03.md"],"last_ton_utc":"2026-05-01T00:00:00Z","gap_start_utc":"2026-06-01T00:00:00Z","gap_end_utc":"2026-06-16T08:00:00Z","missing_bars":0,"note":"monthly_bucket_requires_segment_metadata"}'::jsonb,
         'data_layers_identity_plan_task_3_3', 'approved', '2026-07-03T00:00:00Z'::timestamptz, '2026-07-03T00:00:00Z'::timestamptz),

        -- OKX delisting/migration halt. This is market/event metadata, not OHLCV.
        ('TON-USDT-SWAP','1m',  1781596800000::bigint, 1781692200000::bigint, 'migration_halt', 'not_repairable_by_design',
         '{"event":"OKX TON to GRAM migration","old_symbol":"TON-USDT-SWAP","new_symbol":"GRAM-USDT-SWAP","delist_utc":"2026-06-16T08:00:00Z","gram_list_time_utc":"2026-06-17T10:30:00Z","evidence_docs":["Captains_Logbook/planning/data_layers/data_layers_identity_model_2.md","Captains_Logbook/planning/data_layers/task3_1_gram_backfill_2026-07-03.md"]}'::jsonb,
         'data_layers_identity_plan_task_3_3', 'approved', '2026-07-03T00:00:00Z'::timestamptz, '2026-07-03T00:00:00Z'::timestamptz),
        ('TON-USDT-SWAP','5m',  1781596800000::bigint, 1781692200000::bigint, 'migration_halt',
         'not_repairable_by_design', '{"event":"OKX TON to GRAM migration","old_symbol":"TON-USDT-SWAP","new_symbol":"GRAM-USDT-SWAP","delist_utc":"2026-06-16T08:00:00Z","gram_list_time_utc":"2026-06-17T10:30:00Z","evidence_docs":["Captains_Logbook/planning/data_layers/data_layers_identity_model_2.md","Captains_Logbook/planning/data_layers/task3_1_gram_backfill_2026-07-03.md"]}'::jsonb,
         'data_layers_identity_plan_task_3_3', 'approved', '2026-07-03T00:00:00Z'::timestamptz, '2026-07-03T00:00:00Z'::timestamptz),
        ('TON-USDT-SWAP','15m', 1781596800000::bigint, 1781692200000::bigint, 'migration_halt',
         'not_repairable_by_design', '{"event":"OKX TON to GRAM migration","old_symbol":"TON-USDT-SWAP","new_symbol":"GRAM-USDT-SWAP","delist_utc":"2026-06-16T08:00:00Z","gram_list_time_utc":"2026-06-17T10:30:00Z","evidence_docs":["Captains_Logbook/planning/data_layers/data_layers_identity_model_2.md","Captains_Logbook/planning/data_layers/task3_1_gram_backfill_2026-07-03.md"]}'::jsonb,
         'data_layers_identity_plan_task_3_3', 'approved', '2026-07-03T00:00:00Z'::timestamptz, '2026-07-03T00:00:00Z'::timestamptz),
        ('TON-USDT-SWAP','30m', 1781596800000::bigint, 1781692200000::bigint, 'migration_halt',
         'not_repairable_by_design', '{"event":"OKX TON to GRAM migration","old_symbol":"TON-USDT-SWAP","new_symbol":"GRAM-USDT-SWAP","delist_utc":"2026-06-16T08:00:00Z","gram_list_time_utc":"2026-06-17T10:30:00Z","evidence_docs":["Captains_Logbook/planning/data_layers/data_layers_identity_model_2.md","Captains_Logbook/planning/data_layers/task3_1_gram_backfill_2026-07-03.md"]}'::jsonb,
         'data_layers_identity_plan_task_3_3', 'approved', '2026-07-03T00:00:00Z'::timestamptz, '2026-07-03T00:00:00Z'::timestamptz),
        ('TON-USDT-SWAP','1H',  1781596800000::bigint, 1781692200000::bigint, 'migration_halt',
         'not_repairable_by_design', '{"event":"OKX TON to GRAM migration","old_symbol":"TON-USDT-SWAP","new_symbol":"GRAM-USDT-SWAP","delist_utc":"2026-06-16T08:00:00Z","gram_list_time_utc":"2026-06-17T10:30:00Z","evidence_docs":["Captains_Logbook/planning/data_layers/data_layers_identity_model_2.md","Captains_Logbook/planning/data_layers/task3_1_gram_backfill_2026-07-03.md"]}'::jsonb,
         'data_layers_identity_plan_task_3_3', 'approved', '2026-07-03T00:00:00Z'::timestamptz, '2026-07-03T00:00:00Z'::timestamptz),
        ('TON-USDT-SWAP','4H',  1781596800000::bigint, 1781692200000::bigint, 'migration_halt',
         'not_repairable_by_design', '{"event":"OKX TON to GRAM migration","old_symbol":"TON-USDT-SWAP","new_symbol":"GRAM-USDT-SWAP","delist_utc":"2026-06-16T08:00:00Z","gram_list_time_utc":"2026-06-17T10:30:00Z","evidence_docs":["Captains_Logbook/planning/data_layers/data_layers_identity_model_2.md","Captains_Logbook/planning/data_layers/task3_1_gram_backfill_2026-07-03.md"]}'::jsonb,
         'data_layers_identity_plan_task_3_3', 'approved', '2026-07-03T00:00:00Z'::timestamptz, '2026-07-03T00:00:00Z'::timestamptz),
        ('TON-USDT-SWAP','12H', 1781596800000::bigint, 1781692200000::bigint, 'migration_halt',
         'not_repairable_by_design', '{"event":"OKX TON to GRAM migration","old_symbol":"TON-USDT-SWAP","new_symbol":"GRAM-USDT-SWAP","delist_utc":"2026-06-16T08:00:00Z","gram_list_time_utc":"2026-06-17T10:30:00Z","evidence_docs":["Captains_Logbook/planning/data_layers/data_layers_identity_model_2.md","Captains_Logbook/planning/data_layers/task3_1_gram_backfill_2026-07-03.md"]}'::jsonb,
         'data_layers_identity_plan_task_3_3', 'approved', '2026-07-03T00:00:00Z'::timestamptz, '2026-07-03T00:00:00Z'::timestamptz),
        ('TON-USDT-SWAP','1D',  1781596800000::bigint, 1781692200000::bigint, 'migration_halt',
         'not_repairable_by_design', '{"event":"OKX TON to GRAM migration","old_symbol":"TON-USDT-SWAP","new_symbol":"GRAM-USDT-SWAP","delist_utc":"2026-06-16T08:00:00Z","gram_list_time_utc":"2026-06-17T10:30:00Z","evidence_docs":["Captains_Logbook/planning/data_layers/data_layers_identity_model_2.md","Captains_Logbook/planning/data_layers/task3_1_gram_backfill_2026-07-03.md"]}'::jsonb,
         'data_layers_identity_plan_task_3_3', 'approved', '2026-07-03T00:00:00Z'::timestamptz, '2026-07-03T00:00:00Z'::timestamptz),
        ('TON-USDT-SWAP','1W',  1781596800000::bigint, 1781692200000::bigint, 'migration_halt',
         'not_repairable_by_design', '{"event":"OKX TON to GRAM migration","old_symbol":"TON-USDT-SWAP","new_symbol":"GRAM-USDT-SWAP","delist_utc":"2026-06-16T08:00:00Z","gram_list_time_utc":"2026-06-17T10:30:00Z","evidence_docs":["Captains_Logbook/planning/data_layers/data_layers_identity_model_2.md","Captains_Logbook/planning/data_layers/task3_1_gram_backfill_2026-07-03.md"],"note":"coarse_bucket_overlaps_event"}'::jsonb,
         'data_layers_identity_plan_task_3_3', 'approved', '2026-07-03T00:00:00Z'::timestamptz, '2026-07-03T00:00:00Z'::timestamptz),
        ('TON-USDT-SWAP','1M',  1781596800000::bigint, 1781692200000::bigint, 'migration_halt',
         'not_repairable_by_design', '{"event":"OKX TON to GRAM migration","old_symbol":"TON-USDT-SWAP","new_symbol":"GRAM-USDT-SWAP","delist_utc":"2026-06-16T08:00:00Z","gram_list_time_utc":"2026-06-17T10:30:00Z","evidence_docs":["Captains_Logbook/planning/data_layers/data_layers_identity_model_2.md","Captains_Logbook/planning/data_layers/task3_1_gram_backfill_2026-07-03.md"],"note":"monthly_bucket_requires_segment_metadata"}'::jsonb,
         'data_layers_identity_plan_task_3_3', 'approved', '2026-07-03T00:00:00Z'::timestamptz, '2026-07-03T00:00:00Z'::timestamptz)
)
INSERT INTO ops.gap_classification (
    series_id,
    timeframe,
    range_start_ts,
    range_end_ts,
    gap_type,
    recoverability,
    evidence,
    asserted_by,
    status,
    known_from,
    approved_at
)
SELECT
    rows.series_id,
    rows.timeframe,
    rows.range_start_ts,
    rows.range_end_ts,
    rows.gap_type,
    rows.recoverability,
    rows.evidence,
    rows.asserted_by,
    rows.status,
    rows.known_from,
    rows.approved_at
FROM rows
WHERE NOT EXISTS (
    SELECT 1
    FROM ops.gap_classification existing
    WHERE existing.series_id = rows.series_id
      AND COALESCE(existing.timeframe, '*') = COALESCE(rows.timeframe, '*')
      AND existing.range_start_ts = rows.range_start_ts
      AND existing.range_end_ts = rows.range_end_ts
      AND existing.gap_type = rows.gap_type
      AND existing.known_from = rows.known_from
);
