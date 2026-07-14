#!/usr/bin/env python3
"""
Утилита для анализа и замены except Exception на специфичные исключения
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


class ExceptionAnalyzer:
    """Анализатор исключений для поиска и замены except Exception"""

    def __init__(self):
        self.common_exceptions = {
            # Database exceptions
            "database": [
                "sqlalchemy.exc.SQLAlchemyError",
                "sqlalchemy.exc.IntegrityError",
                "sqlalchemy.exc.OperationalError",
                "asyncpg.exceptions.PostgresError",
            ],
            # Network/API exceptions
            "network": [
                "aiohttp.ClientError",
                "aiohttp.ClientTimeout",
                "asyncio.TimeoutError",
                "requests.RequestException",
                "urllib3.exceptions.URLError",
            ],
            # File operations
            "file": ["FileNotFoundError", "PermissionError", "OSError", "IOError"],
            # Data processing
            "data": [
                "ValueError",
                "TypeError",
                "KeyError",
                "IndexError",
                "AttributeError",
            ],
            # Configuration
            "config": ["KeyError", "ValueError", "TypeError"],
            # Validation
            "validation": ["ValueError", "TypeError", "AssertionError"],
            # General async
            "async": ["asyncio.CancelledError", "asyncio.TimeoutError"],
            # JSON/Serialization
            "json": ["json.JSONDecodeError", "ValueError", "TypeError"],
            # Logging
            "logging": ["OSError", "PermissionError"],
        }

    def analyze_file(self, file_path: str) -> list[ExceptionLocation]:
        """Анализирует файл на наличие except Exception"""
        locations = []

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            # Парсим AST
            tree = ast.parse(content)

            # Ищем все except Exception
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    if node.type is None or (
                        isinstance(node.type, ast.Name) and node.type.id == "Exception"
                    ):
                        # Получаем контекст
                        context = self._get_context(content, node.lineno)

                        # Определяем функцию
                        function_name = self._get_function_name(tree, node.lineno)

                        # Предлагаем исключения
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
        start = max(0, line_number - 3)
        end = min(len(lines), line_number + 2)

        context_lines = []
        for i in range(start, end):
            prefix = ">>> " if i == line_number - 1 else "    "
            context_lines.append(f"{prefix}{i + 1:4d}: {lines[i]}")

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
        """Предлагает специфичные исключения на основе контекста"""
        suggestions = []
        context_lower = context.lower()

        # Анализируем контекст
        if any(
            word in context_lower
            for word in ["database", "sql", "session", "commit", "rollback"]
        ):
            suggestions.extend(self.common_exceptions["database"])

        if any(
            word in context_lower
            for word in ["http", "request", "api", "client", "timeout"]
        ):
            suggestions.extend(self.common_exceptions["network"])

        if any(
            word in context_lower for word in ["file", "read", "write", "open", "close"]
        ):
            suggestions.extend(self.common_exceptions["file"])

        if any(
            word in context_lower for word in ["json", "parse", "serialize", "decode"]
        ):
            suggestions.extend(self.common_exceptions["json"])

        if any(word in context_lower for word in ["validate", "check", "assert"]):
            suggestions.extend(self.common_exceptions["validation"])

        if any(word in context_lower for word in ["config", "env", "setting"]):
            suggestions.extend(self.common_exceptions["config"])

        if any(word in context_lower for word in ["await", "async", "task"]):
            suggestions.extend(self.common_exceptions["async"])

        if any(word in context_lower for word in ["log", "logger"]):
            suggestions.extend(self.common_exceptions["logging"])

        # Общие исключения для обработки данных
        if any(
            word in context_lower
            for word in ["data", "process", "calculate", "transform"]
        ):
            suggestions.extend(self.common_exceptions["data"])

        # Убираем дубликаты и возвращаем уникальные
        return list(dict.fromkeys(suggestions))

    def generate_replacement(self, location: ExceptionLocation) -> str:
        """Генерирует код замены для except Exception"""
        if not location.suggested_exceptions:
            return "except Exception as e:\n    logger.error(f'Unexpected error: {e}')\n    raise"

        # Создаем специфичные обработчики
        handlers = []
        for exc in location.suggested_exceptions[:3]:  # Берем первые 3
            short_name = exc.split(".")[-1]
            handlers.append(
                f"except {exc} as e:\n    logger.error(f'{short_name}: {{e}}')\n    raise"
            )

        # Добавляем общий обработчик в конце
        handlers.append(
            "except Exception as e:\n    logger.error(f'Unexpected error: {e}')\n    raise"
        )

        return "\n".join(handlers)

    def analyze_directory(
        self, directory: str, pattern: str = "*.py"
    ) -> dict[str, list[ExceptionLocation]]:
        """Анализирует директорию на наличие except Exception"""
        results = {}
        directory_path = Path(directory)

        for file_path in directory_path.rglob(pattern):
            if file_path.is_file():
                locations = self.analyze_file(str(file_path))
                if locations:
                    results[str(file_path)] = locations

        return results

    def create_report(self, results: dict[str, list[ExceptionLocation]]) -> str:
        """Создает отчет по найденным except Exception"""
        report = ["# ОТЧЕТ ПО АНАЛИЗУ EXCEPT EXCEPTION", ""]

        total_files = len(results)
        total_exceptions = sum(len(locations) for locations in results.values())

        report.append("## Сводка")
        report.append(f"- Всего файлов с except Exception: {total_files}")
        report.append(f"- Всего except Exception: {total_exceptions}")
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
                    for exc in location.suggested_exceptions:
                        report.append(f"- `{exc}`")

                report.append("**Предлагаемая замена:**")
                report.append("```python")
                report.append(self.generate_replacement(location))
                report.append("```")
                report.append("")

        return "\n".join(report)


def main():
    """Основная функция для запуска анализа"""
    import sys

    if len(sys.argv) < 2:
        print("Использование: python exception_analyzer.py <директория>")
        sys.exit(1)

    directory = sys.argv[1]
    analyzer = ExceptionAnalyzer()

    print(f"Анализируем директорию: {directory}")
    results = analyzer.analyze_directory(directory)

    if not results:
        print("✅ except Exception не найдены!")
        return

    # Создаем отчет
    report = analyzer.create_report(results)

    # Сохраняем отчет
    report_path = Path(directory) / "exception_analysis_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"📊 Отчет сохранен в: {report_path}")
    print(f"📈 Найдено файлов с except Exception: {len(results)}")

    total_exceptions = sum(len(locations) for locations in results.values())
    print(f"📈 Всего except Exception: {total_exceptions}")


if __name__ == "__main__":
    main()
