#!/usr/bin/env python3
"""
Компактный анализатор исключений для критических файлов
"""

import ast
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ExceptionLocation:
    """Информация о местоположении except Exception"""

    file_path: str
    line_number: int
    function_name: str | None
    context: str
    suggested_exceptions: list[str]


class CompactExceptionAnalyzer:
    """Компактный анализатор исключений"""

    def __init__(self):
        # Критические файлы для анализа
        self.critical_files = [
            "src/main.py",
            "src/main_with_options.py",
            "src/main_temp3.py",
            "src/utils/session_utils.py",
            "src/utils/safe_logging.py",
            "src/okx/client.py",
            "src/database.py",
            "src/indicators/calc_indicators.py",
            "src/signals/calculator/signal_calculator_detailed.py",
        ]

        self.common_exceptions = {
            "database": [
                "sqlalchemy.exc.SQLAlchemyError",
                "sqlalchemy.exc.IntegrityError",
                "sqlalchemy.exc.OperationalError",
                "asyncpg.exceptions.PostgresError",
            ],
            "network": [
                "aiohttp.ClientError",
                "aiohttp.ClientTimeout",
                "asyncio.TimeoutError",
            ],
            "file": ["FileNotFoundError", "PermissionError", "OSError"],
            "data": ["ValueError", "TypeError", "KeyError", "IndexError"],
            "config": ["KeyError", "ValueError", "TypeError"],
            "async": ["asyncio.CancelledError", "asyncio.TimeoutError"],
        }

    def analyze_file(self, file_path: str) -> list[ExceptionLocation]:
        """Анализирует файл на наличие except Exception"""
        locations = []

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    if node.type is None or (
                        isinstance(node.type, ast.Name) and node.type.id == "Exception"
                    ):
                        context = self._get_context(content, node.lineno)
                        function_name = self._get_function_name(tree, node.lineno)
                        suggested = self._suggest_exceptions(context, function_name)

                        locations.append(
                            ExceptionLocation(
                                file_path=file_path,
                                line_number=node.lineno,
                                function_name=function_name,
                                context=context,
                                suggested_exceptions=suggested,
                            )
                        )

        except Exception as e:
            logger.warning(f"Не удалось проанализировать {file_path}: {e}")

        return locations

    def _get_context(self, content: str, line_number: int) -> str:
        """Получает контекст вокруг строки"""
        lines = content.split("\n")
        start = max(0, line_number - 2)
        end = min(len(lines), line_number + 1)

        context_lines = []
        for i in range(start, end):
            prefix = ">>> " if i == line_number - 1 else "    "
            context_lines.append(f"{prefix}{i+1:4d}: {lines[i]}")

        return "\n".join(context_lines)

    def _get_function_name(self, tree: ast.AST, line_number: int) -> str | None:
        """Получает имя функции для строки"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                if (
                    node.lineno
                    <= line_number
                    <= getattr(node, "end_lineno", node.lineno)
                ):
                    return node.name
        return None

    def _suggest_exceptions(self, context: str, function_name: str | None) -> list[str]:
        """Предлагает специфичные исключения"""
        suggestions = []
        context_lower = context.lower()

        if any(
            word in context_lower for word in ["database", "sql", "session", "commit"]
        ):
            suggestions.extend(self.common_exceptions["database"])

        if any(word in context_lower for word in ["http", "request", "api", "client"]):
            suggestions.extend(self.common_exceptions["network"])

        if any(word in context_lower for word in ["file", "read", "write"]):
            suggestions.extend(self.common_exceptions["file"])

        if any(word in context_lower for word in ["await", "async"]):
            suggestions.extend(self.common_exceptions["async"])

        if any(word in context_lower for word in ["config", "env"]):
            suggestions.extend(self.common_exceptions["config"])

        if any(word in context_lower for word in ["data", "process"]):
            suggestions.extend(self.common_exceptions["data"])

        return list(dict.fromkeys(suggestions))

    def analyze_critical_files(self) -> dict[str, list[ExceptionLocation]]:
        """Анализирует только критические файлы"""
        results = {}

        for file_path in self.critical_files:
            if Path(file_path).exists():
                locations = self.analyze_file(file_path)
                if locations:
                    results[file_path] = locations

        return results

    def create_compact_report(self, results: dict[str, list[ExceptionLocation]]) -> str:
        """Создает компактный отчет"""
        report = ["# КОМПАКТНЫЙ ОТЧЕТ ПО КРИТИЧЕСКИМ EXCEPT EXCEPTION", ""]

        total_files = len(results)
        total_exceptions = sum(len(locations) for locations in results.values())

        report.append("## Сводка")
        report.append(f"- Критических файлов с except Exception: {total_files}")
        report.append(
            f"- Всего except Exception в критических файлах: {total_exceptions}"
        )
        report.append("")

        for file_path, locations in results.items():
            report.append(f"## {file_path}")
            report.append(f"Найдено except Exception: {len(locations)}")
            report.append("")

            for i, location in enumerate(locations, 1):
                report.append(f"### {i}. Строка {location.line_number}")
                if location.function_name:
                    report.append(f"**Функция:** {location.function_name}")

                report.append("**Контекст:**")
                report.append("```python")
                report.append(location.context)
                report.append("```")

                if location.suggested_exceptions:
                    report.append("**Предлагаемые исключения:**")
                    for exc in location.suggested_exceptions[
                        :3
                    ]:  # Показываем только первые 3
                        report.append(f"- `{exc}`")

                report.append("")

        return "\n".join(report)


def main():
    """Основная функция"""
    analyzer = CompactExceptionAnalyzer()

    print("🔍 Анализируем критические файлы...")
    results = analyzer.analyze_critical_files()

    if not results:
        print("✅ except Exception в критических файлах не найдены!")
        return

    # Создаем отчет
    report = analyzer.create_compact_report(results)

    # Сохраняем отчет
    report_path = Path("critical_exceptions_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"📊 Отчет сохранен в: {report_path}")
    print(f"📈 Критических файлов с except Exception: {len(results)}")

    total_exceptions = sum(len(locations) for locations in results.values())
    print(f"📈 Всего except Exception в критических файлах: {total_exceptions}")

    # Показываем краткую сводку
    print("\n📋 КРАТКАЯ СВОДКА:")
    for file_path, locations in results.items():
        print(f"  {file_path}: {len(locations)} except Exception")


if __name__ == "__main__":
    main()
