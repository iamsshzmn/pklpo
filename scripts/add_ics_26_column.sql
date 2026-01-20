-- Скрипт для добавления отсутствующей колонки ics_26 в таблицу indicators
-- Проблема: В логах видно ошибку 'Database insertion failed: 'ics_26'',
-- что означает, что поле ics_26 присутствует в данных, но отсутствует в схеме БД.

-- Проверяем, существует ли уже колонка ics_26
SELECT column_name, data_type, numeric_precision, numeric_scale
FROM information_schema.columns
WHERE table_name = 'indicators'
AND column_name = 'ics_26'
AND table_schema = 'public';

-- Если колонка не существует, добавляем её
-- (раскомментируйте следующую строку, если колонка отсутствует)
-- ALTER TABLE indicators ADD COLUMN ics_26 DECIMAL(20,8);

-- Проверяем результат
SELECT column_name, data_type, numeric_precision, numeric_scale
FROM information_schema.columns
WHERE table_name = 'indicators'
AND column_name = 'ics_26'
AND table_schema = 'public';
