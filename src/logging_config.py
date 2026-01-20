import logging


def setup_logging(log_file="app.log"):
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Удаляем все старые хендлеры (чтобы не дублировался вывод)
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Консоль
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    ch.setLevel(logging.INFO)
    root_logger.addHandler(ch)

    # Файл
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(formatter)
    fh.setLevel(logging.DEBUG)
    root_logger.addHandler(fh)

    # SQLAlchemy engine — только WARNING и выше
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    # aiohttp — только WARNING и выше
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    # Другие сторонние — по необходимости

    # Ваши модули — можно оставить INFO/DEBUG
    # logging.getLogger("your_project").setLevel(logging.INFO)
