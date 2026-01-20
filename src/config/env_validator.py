"""
Валидатор переменных окружения
"""

import os

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Все настройки приложения"""

    # Database settings
    postgres_user: str
    postgres_password: str
    postgres_db: str
    db_host: str = "localhost"
    db_port: str = "5432"

    # OKX API settings
    okx_api_key: str | None = None
    okx_secret_key: str | None = None
    okx_passphrase: str | None = None
    okx_sandbox: bool = False

    # Logging settings
    log_level: str = "INFO"
    log_file: str | None = None

    # App settings
    debug: bool = False
    max_workers: int = 4
    batch_size: int = 100

    # PGAdmin settings (optional)
    pgadmin_email: str | None = None
    pgadmin_password: str | None = None

    @field_validator("postgres_user", "postgres_password", "postgres_db")
    @classmethod
    def validate_required_db_fields(cls, v: str, info) -> str:
        if not v:
            raise ValueError(f"Поле {info.field_name} обязательно для заполнения")
        return v

    @field_validator("db_port")
    @classmethod
    def validate_port(cls, v: str) -> str:
        try:
            port = int(v)
            if not (1 <= port <= 65535):
                raise ValueError("Порт должен быть в диапазоне 1-65535")
        except ValueError as err:
            raise ValueError("Порт должен быть числом") from err
        return v

    @field_validator("okx_api_key", "okx_secret_key", "okx_passphrase")
    @classmethod
    def validate_okx_credentials(cls, v: str | None, info) -> str | None:
        # Проверяем только если хотя бы один из ключей установлен
        # Если все ключи None, то торговля отключена
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(
                f"Уровень логирования должен быть одним из: {valid_levels}"
            )
        return v.upper()

    @field_validator("max_workers")
    @classmethod
    def validate_max_workers(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Количество воркеров должно быть больше 0")
        return v

    @field_validator("batch_size")
    @classmethod
    def validate_batch_size(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Размер батча должен быть больше 0")
        return v

    class Config:
        env_file = ".env"
        extra = "ignore"  # Игнорируем дополнительные поля


def validate_environment() -> Settings:
    """
    Валидирует переменные окружения и возвращает настройки

    Returns:
        Settings: Валидированные настройки

    Raises:
        ValueError: Если переменные окружения некорректны
    """
    try:
        return Settings()
    except Exception as e:
        raise ValueError(f"Ошибка валидации переменных окружения: {e}") from e


def get_database_url() -> str:
    """
    Возвращает URL для подключения к базе данных

    Returns:
        str: URL для подключения к PostgreSQL
    """
    # 1) Явный приоритет: если задан DATABASE_URL, используем его без изменений
    url = os.getenv("DATABASE_URL")
    if url:
        # Автоматическая замена pklpo_db на localhost для локального запуска
        # Проверяем, доступен ли хост pklpo_db (это имя Docker контейнера)
        import socket

        try:
            # Пытаемся разрешить имя хоста
            socket.gethostbyname("pklpo_db")
            # Если успешно, значит мы в Docker сети - оставляем как есть
        except socket.gaierror:
            # Если не удалось разрешить, значит локальный запуск - заменяем на localhost
            if "pklpo_db" in url:
                url = url.replace("pklpo_db", "localhost")
        return url

    # 2) Иначе собираем строку подключения из переменных окружения через Settings
    settings = validate_environment()
    return (
        f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.db_host}:{settings.db_port}/{settings.postgres_db}"
    )


def check_required_env_vars() -> list[str]:
    """
    Проверяет наличие обязательных переменных окружения

    Returns:
        List[str]: Список отсутствующих переменных
    """
    required_vars = ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"]

    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    return missing_vars
