#!/usr/bin/env python3
"""
CLI скрипт для расчета торговых сигналов.
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent))

from src.signals.calculator.cli import main

if __name__ == "__main__":
    asyncio.run(main())
