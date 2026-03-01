-- Добавление колонки data_status для отслеживания полноты расчётов
-- Автор: система
-- Дата: 2025-10-29

-- 1. Добавляем колонку если её нет
ALTER TABLE public.indicators
ADD COLUMN IF NOT EXISTS data_status VARCHAR(10) DEFAULT 'ok';

-- 2. Создаём индекс для быстрой фильтрации incomplete записей
CREATE INDEX IF NOT EXISTS idx_indicators_data_status
ON public.indicators(data_status)
WHERE data_status = 'inc';

-- 3. Обновляем существующие записи (считаем их полными)
UPDATE public.indicators
SET data_status = 'ok'
WHERE data_status IS NULL;

-- 4. Комментарий к колонке
COMMENT ON COLUMN public.indicators.data_status IS
'Статус полноты расчётов: ok - все группы рассчитаны, inc - частичные данные (gate validation failed)';
