# MTF Data Cleanup - Очистка старых MTF данных

## 🎯 Назначение

Скрипт для очистки старых MTF данных из таблиц `mtf.context`, `mtf.triggers`, `mtf.consensus`. Удаляет записи старше указанного времени для поддержания актуальности данных.

## 🚀 Использование

### 1. Через основной файл

```bash
# Очистка данных старше 24 часов (по умолчанию)
python src/main_with_options.py --mtf-cleanup

# Очистка данных старше 48 часов
python src/main_with_options.py --mtf-cleanup --mtf-cleanup-hours 48

# Очистка для конкретного символа
python src/main_with_options.py --mtf-cleanup --symbol BTC-USDT-SWAP

# Проверка без удаления (dry-run)
python src/main_with_options.py --mtf-cleanup --dry-run
```

### 2. Через MTF manager

```bash
# Очистка всех данных старше 24 часов
python src/mtf/manager.py --mode cleanup

# Очистка данных старше 12 часов
python src/mtf/manager.py --mode cleanup --hours 12

# Очистка для конкретного символа
python src/mtf/manager.py --mode cleanup --symbol ETH-USDT-SWAP

# Проверка без удаления
python src/mtf/manager.py --mode cleanup --dry-run
```

### 3. Прямой запуск скрипта

```bash
# Очистка всех данных старше 24 часов
python src/mtf/cleanup_old_data.py

# Очистка данных старше 6 часов
python src/mtf/cleanup_old_data.py --hours 6

# Очистка для конкретного символа
python src/mtf/cleanup_old_data.py --symbol BTC-USDT-SWAP

# Проверка без удаления
python src/mtf/cleanup_old_data.py --dry-run
```

## 📊 Что очищается

### Таблицы для очистки:
- `mtf.context` - контекстные данные по таймфреймам
- `mtf.triggers` - триггерные данные
- `mtf.consensus` - финальные решения

### Критерий очистки:
- **Временная метка**: `ts < (текущее_время - указанные_часы)`
- **По умолчанию**: 24 часа

## 🔧 Параметры

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `--hours` | Возраст данных в часах | 24 |
| `--symbol` | Конкретный символ | Все символы |
| `--dry-run` | Только проверка без удаления | False |

## 📈 Примеры использования

### Регулярная очистка (ежедневно)
```bash
# Очистка данных старше 24 часов
python src/main_with_options.py --mtf-cleanup
```

### Очистка старых данных
```bash
# Очистка данных старше недели
python src/main_with_options.py --mtf-cleanup --mtf-cleanup-hours 168
```

### Очистка конкретного символа
```bash
# Очистка только BTC данных старше 12 часов
python src/main_with_options.py --mtf-cleanup --symbol BTC-USDT-SWAP --mtf-cleanup-hours 12
```

### Проверка перед очисткой
```bash
# Сначала проверить что будет удалено
python src/main_with_options.py --mtf-cleanup --dry-run

# Затем выполнить очистку
python src/main_with_options.py --mtf-cleanup
```

## ⚠️ Важные замечания

1. **Безопасность**: Всегда используйте `--dry-run` для проверки перед реальной очисткой
2. **Время**: Учитывайте часовой пояс - используется UTC
3. **Необратимость**: Удаленные данные восстановить нельзя
4. **Производительность**: Очистка может занять время на больших объемах данных

## 🔍 Логирование

Все операции логируются в файл `mtf_cleanup.log` с подробной информацией:
- Количество записей до и после очистки
- Временные границы
- Ошибки и предупреждения
- Статистика удаления

## 🎯 Рекомендации

### Для продакшена:
```bash
# Ежедневная очистка в cron
0 2 * * * cd /path/to/project && python src/main_with_options.py --mtf-cleanup
```

### Для разработки:
```bash
# Частая очистка для тестирования
python src/main_with_options.py --mtf-cleanup --mtf-cleanup-hours 1
```

### Для отладки:
```bash
# Проверка состояния данных
python src/main_with_options.py --mtf-validate
python src/main_with_options.py --mtf-cleanup --dry-run
```
