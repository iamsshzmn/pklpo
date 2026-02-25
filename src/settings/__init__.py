"""
Модуль управления пользовательскими настройками

Содержит:
- UserSettingsManager - менеджер настроек пользователей
- SettingsValidator - валидация настроек
- DefaultSettings - настройки по умолчанию
- SettingsCLI - командная строка для управления настройками
"""

from .cli import SettingsCLI
from .defaults import DefaultSettings
from .manager import UserSettingsManager
from .validator import SettingsValidator

__all__ = ["DefaultSettings", "SettingsCLI", "SettingsValidator", "UserSettingsManager"]
