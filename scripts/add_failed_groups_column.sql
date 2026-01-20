-- Добавление колонки failed_groups для детальной диагностики
-- Автор: система
-- Дата: 2025-10-29

ALTER TABLE public.indicators
ADD COLUMN IF NOT EXISTS failed_groups TEXT;

COMMENT ON COLUMN public.indicators.failed_groups IS
'Список групп, не прошедших gate validation (через запятую): moving_averages, oscillators, volatility, trend';
