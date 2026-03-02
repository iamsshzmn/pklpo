#!/usr/bin/env python3
"""
Утилита для автоматической замены except Exception на специфичные исключения
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ExceptionFix:
    """Информация о замене except Exception"""

    file_path: str
    line_number: int
    original_code: str
    replacement_code: str
    context: str


class ExceptionFixer:
    """Утилита для замены except Exception на специфичные исключения"""

    def __init__(self):
        self.exception_mappings = {
            # Database operations
            "database": {
                "keywords": [
                    "session",
                    "commit",
                    "rollback",
                    "execute",
                    "query",
                    "database",
                ],
                "exceptions": [
                    "sqlalchemy.exc.SQLAlchemyError",
                    "sqlalchemy.exc.IntegrityError",
                    "sqlalchemy.exc.OperationalError",
                    "asyncpg.exceptions.PostgresError",
                ],
            },
            # Network/API operations
            "network": {
                "keywords": ["http", "request", "api", "client", "timeout", "fetch"],
                "exceptions": [
                    "aiohttp.ClientError",
                    "aiohttp.ClientTimeout",
                    "asyncio.TimeoutError",
                    "requests.RequestException",
                ],
            },
            # File operations
            "file": {
                "keywords": ["file", "read", "write", "open", "close", "path"],
                "exceptions": [
                    "FileNotFoundError",
                    "PermissionError",
                    "OSError",
                    "IOError",
                ],
            },
            # Data processing
            "data": {
                "keywords": [
                    "data",
                    "process",
                    "calculate",
                    "transform",
                    "pandas",
                    "df",
                ],
                "exceptions": [
                    "ValueError",
                    "TypeError",
                    "KeyError",
                    "IndexError",
                    "AttributeError",
                ],
            },
            # Configuration
            "config": {
                "keywords": ["config", "env", "setting", "validate"],
                "exceptions": ["KeyError", "ValueError", "TypeError"],
            },
            # Async operations
            "async": {
                "keywords": ["await", "async", "task", "coroutine"],
                "exceptions": ["asyncio.CancelledError", "asyncio.TimeoutError"],
            },
        }

    def analyze_context(self, context: str) -> list[str]:
        """Анализирует контекст и возвращает подходящие исключения"""
        context_lower = context.lower()
        suggested_exceptions = []

        for _category, mapping in self.exception_mappings.items():
            if any(keyword in context_lower for keyword in mapping["keywords"]):
                suggested_exceptions.extend(mapping["exceptions"])

        # Убираем дубликаты
        return list(dict.fromkeys(suggested_exceptions))

    def generate_replacement(
        self, original_code: str, suggested_exceptions: list[str]
    ) -> str:
        """Генерирует код замены для except Exception"""
        if not suggested_exceptions:
            # Если не можем определить специфичные исключения, оставляем как есть
            return original_code

        # Извлекаем отступ и остальную часть
        match = re.match(r"(\s*)(except Exception as e:.*)", original_code, re.DOTALL)
        if not match:
            return original_code

        indent = match.group(1)
        match.group(2)

        # Создаем специфичные обработчики
        handlers = []
        for exc in suggested_exceptions[:3]:  # Берем первые 3
            short_name = exc.split(".")[-1]
            handlers.append(f"{indent}except {exc} as e:")
            handlers.append(f"{indent}    logger.error(f'{short_name}: {{e}}')")
            handlers.append(f"{indent}    raise")

        # Добавляем общий обработчик в конце
        handlers.append(f"{indent}except Exception as e:")
        handlers.append(f"{indent}    logger.error(f'Unexpected error: {{e}}')")
        handlers.append(f"{indent}    raise")

        return "\n".join(handlers)

    def fix_file(self, file_path: str) -> list[ExceptionFix]:
        """Исправляет except Exception в файле"""
        fixes = []

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            lines = content.split("\n")
            new_lines = lines.copy()

            # Ищем except Exception
            for i, line in enumerate(lines):
                if "except Exception as e:" in line:
                    # Получаем контекст
                    context_start = max(0, i - 5)
                    context_end = min(len(lines), i + 5)
                    context = "\n".join(lines[context_start:context_end])

                    # Анализируем контекст
                    suggested_exceptions = self.analyze_context(context)

                    # Генерируем замену
                    replacement = self.generate_replacement(line, suggested_exceptions)

                    if replacement != line:
                        # Если есть специфичные исключения, заменяем
                        if suggested_exceptions:
                            # Находим конец блока except
                            j = i + 1
                            while j < len(lines) and (
                                lines[j].strip() == "" or lines[j].startswith("    ")
                            ):
                                j += 1

                            # Заменяем весь блок
                            replacement_lines = replacement.split("\n")
                            new_lines[i:j] = replacement_lines

                            fixes.append(
                                ExceptionFix(
                                    file_path=file_path,
                                    line_number=i + 1,
                                    original_code="\n".join(lines[i:j]),
                                    replacement_code=replacement,
                                    context=context,
                                )
                            )

            # Сохраняем изменения
            if fixes:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(new_lines))

        except Exception as e:
            logger.error(f"Ошибка при обработке файла {file_path}: {e}")

        return fixes

    def fix_critical_files(self) -> dict[str, list[ExceptionFix]]:
        """Исправляет except Exception в критических файлах"""
        critical_files = [
            "src/main.py",
            "src/main_with_options.py",
            "src/utils/session_utils.py",
            "src/okx/client.py",
            "src/database.py",
        ]

        results = {}

        for file_path in critical_files:
            if Path(file_path).exists():
                fixes = self.fix_file(file_path)
                if fixes:
                    results[file_path] = fixes

        return results

    def create_fix_report(self, results: dict[str, list[ExceptionFix]]) -> str:
        """Создает отчет по исправлениям"""
        report = ["# ОТЧЕТ ПО ИСПРАВЛЕНИЮ EXCEPT EXCEPTION", ""]

        total_files = len(results)
        total_fixes = sum(len(fixes) for fixes in results.values())

        report.append("## Сводка")
        report.append(f"- Исправлено файлов: {total_files}")
        report.append(f"- Всего исправлений: {total_fixes}")
        report.append("")

        for file_path, fixes in results.items():
            report.append(f"## {file_path}")
            report.append(f"Исправлений: {len(fixes)}")
            report.append("")

            for i, fix in enumerate(fixes, 1):
                report.append(f"### {i}. Строка {fix.line_number}")
                report.append("**Контекст:**")
                report.append("```python")
                report.append(fix.context)
                report.append("```")

                report.append("**Было:**")
                report.append("```python")
                report.append(fix.original_code)
                report.append("```")

                report.append("**Стало:**")
                report.append("```python")
                report.append(fix.replacement_code)
                report.append("```")
                report.append("")

        return "\n".join(report)


def main():
    """Основная функция"""
    fixer = ExceptionFixer()

    print("🔧 Исправляем except Exception в критических файлах...")
    results = fixer.fix_critical_files()

    if not results:
        print("✅ except Exception в критических файлах не найдены или уже исправлены!")
        return

    # Создаем отчет
    report = fixer.create_fix_report(results)

    # Сохраняем отчет
    report_path = Path("exception_fixes_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"📊 Отчет сохранен в: {report_path}")
    print(f"📈 Исправлено файлов: {len(results)}")

    total_fixes = sum(len(fixes) for fixes in results.values())
    print(f"📈 Всего исправлений: {total_fixes}")

    # Показываем краткую сводку
    print("\n📋 КРАТКАЯ СВОДКА:")
    for file_path, fixes in results.items():
        print(f"  {file_path}: {len(fixes)} исправлений")


if __name__ == "__main__":
    main()
