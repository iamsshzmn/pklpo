"""
Командная строка для управления пользовательскими настройками
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Добавляем корневую директорию в путь для импортов
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.logging import setup_logging

from .defaults import DefaultSettings
from .manager import UserSettingsManager

setup_logging("settings.log")


class SettingsCLI:
    """Командная строка для управления настройками"""

    def __init__(self):
        self.manager = UserSettingsManager()

    def create_parser(self) -> argparse.ArgumentParser:
        """Создаёт парсер аргументов"""
        parser = argparse.ArgumentParser(
            description="Управление пользовательскими настройками для расчёта позиций"
        )

        subparsers = parser.add_subparsers(dest="command", help="Доступные команды")

        # Команда list
        list_parser = subparsers.add_parser("list", help="Список пользователей")
        list_parser.add_argument(
            "--json", action="store_true", help="Вывод в формате JSON"
        )

        # Команда show
        show_parser = subparsers.add_parser(
            "show", help="Показать настройки пользователя"
        )
        show_parser.add_argument("user_id", help="ID пользователя")
        show_parser.add_argument(
            "--json", action="store_true", help="Вывод в формате JSON"
        )

        # Команда create
        create_parser = subparsers.add_parser(
            "create", help="Создать настройки пользователя"
        )
        create_parser.add_argument("user_id", help="ID пользователя")
        create_parser.add_argument(
            "--preset",
            choices=DefaultSettings.list_presets(),
            help="Применить предустановленные настройки",
        )
        create_parser.add_argument("--file", help="Файл с настройками (JSON)")

        # Команда update
        update_parser = subparsers.add_parser(
            "update", help="Обновить настройки пользователя"
        )
        update_parser.add_argument("user_id", help="ID пользователя")
        update_parser.add_argument(
            "--preset",
            choices=DefaultSettings.list_presets(),
            help="Применить предустановленные настройки",
        )
        update_parser.add_argument("--file", help="Файл с настройками (JSON)")
        update_parser.add_argument("--balance", type=float, help="Баланс в USDT")
        update_parser.add_argument("--risk", type=float, help="Риск на сделку в %")
        update_parser.add_argument("--leverage", type=int, help="Целевое плечо")
        update_parser.add_argument(
            "--consensus", type=float, help="Порог консенсуса в %"
        )

        # Команда delete
        delete_parser = subparsers.add_parser(
            "delete", help="Удалить настройки пользователя"
        )
        delete_parser.add_argument("user_id", help="ID пользователя")
        delete_parser.add_argument(
            "--force", action="store_true", help="Подтвердить удаление"
        )

        # Команда presets
        presets_parser = subparsers.add_parser(
            "presets", help="Показать доступные пресеты"
        )
        presets_parser.add_argument(
            "--json", action="store_true", help="Вывод в формате JSON"
        )

        # Команда validate
        validate_parser = subparsers.add_parser(
            "validate", help="Валидировать настройки"
        )
        validate_parser.add_argument(
            "--file", required=True, help="Файл с настройками (JSON)"
        )

        return parser

    async def list_users(self, args: argparse.Namespace):
        """Список пользователей"""
        users = await self.manager.list_users()

        if args.json:
            print(json.dumps({"users": users}, indent=2))
        else:
            if users:
                print("📋 Пользователи с настройками:")
                for user_id in users:
                    print(f"  - {user_id}")
            else:
                print("📋 Пользователи с настройками не найдены")

    async def show_user(self, args: argparse.Namespace):
        """Показать настройки пользователя"""
        summary = await self.manager.get_settings_summary(args.user_id)

        if summary is None:
            print(f"❌ Настройки для пользователя {args.user_id} не найдены")
            return

        if args.json:
            print(json.dumps(summary, indent=2, default=str))
        else:
            print(f"📊 Настройки пользователя: {args.user_id}")
            print("=" * 50)
            print(f"💰 Баланс: {summary['balance_usdt']:,.2f} USDT")
            print(f"⚠️ Риск на сделку: {summary['risk_per_trade_pct']:.1f}%")
            print(f"💵 Сумма риска: {summary['risk_amount_usdt']:.2f} USDT")
            print(f"📈 Целевое плечо: {summary['leverage_target']}x")
            print(f"🎯 Порог консенсуса: {summary['consensus_threshold']:.1f}%")
            print(f"⏰ Таймфрейм входа: {summary['timeframe_entry']}")
            print(f"🛑 Стоп по умолчанию: {summary['default_stop_value']:.1f}%")
            print(
                f"🎯 Тейк-профиты: {', '.join([f'{x:.1f}%' for x in summary['default_tp_levels_pct']])}"
            )
            print(f"📅 Создано: {summary['created_at']}")
            print(f"📅 Обновлено: {summary['updated_at']}")

    async def create_user(self, args: argparse.Namespace):
        """Создать настройки пользователя"""
        settings = None

        if args.preset:
            print(f"🎯 Применяем пресет: {args.preset}")
            success = await self.manager.apply_preset(args.user_id, args.preset)
            if success:
                print(
                    f"✅ Настройки для пользователя {args.user_id} созданы с пресетом {args.preset}"
                )
            else:
                print(f"❌ Ошибка при создании настроек для {args.user_id}")
            return

        if args.file:
            try:
                with open(args.file, encoding="utf-8") as f:
                    settings = json.load(f)
                print(f"📄 Загружены настройки из файла: {args.file}")
            except Exception as e:
                print(f"❌ Ошибка при чтении файла {args.file}: {e}")
                return

        success = await self.manager.create_user_settings(args.user_id, settings)
        if success:
            print(f"✅ Настройки для пользователя {args.user_id} созданы успешно")
        else:
            print(f"❌ Ошибка при создании настроек для {args.user_id}")

    async def update_user(self, args: argparse.Namespace):
        """Обновить настройки пользователя"""
        settings = {}

        if args.preset:
            print(f"🎯 Применяем пресет: {args.preset}")
            success = await self.manager.apply_preset(args.user_id, args.preset)
            if success:
                print(
                    f"✅ Настройки для пользователя {args.user_id} обновлены с пресетом {args.preset}"
                )
            else:
                print(f"❌ Ошибка при обновлении настроек для {args.user_id}")
            return

        if args.file:
            try:
                with open(args.file, encoding="utf-8") as f:
                    settings = json.load(f)
                print(f"📄 Загружены настройки из файла: {args.file}")
            except Exception as e:
                print(f"❌ Ошибка при чтении файла {args.file}: {e}")
                return

        # Добавляем параметры командной строки
        if args.balance is not None:
            settings["balance_usdt"] = args.balance
        if args.risk is not None:
            settings["risk_per_trade_pct"] = (
                args.risk / 100
            )  # конвертируем в десятичную дробь
        if args.leverage is not None:
            settings["leverage_target"] = args.leverage
        if args.consensus is not None:
            settings["consensus_threshold"] = (
                args.consensus / 100
            )  # конвертируем в десятичную дробь

        if not settings:
            print("❌ Не указаны параметры для обновления")
            return

        success = await self.manager.update_user_settings(args.user_id, settings)
        if success:
            print(f"✅ Настройки для пользователя {args.user_id} обновлены успешно")
        else:
            print(f"❌ Ошибка при обновлении настроек для {args.user_id}")

    async def delete_user(self, args: argparse.Namespace):
        """Удалить настройки пользователя"""
        if not args.force:
            response = input(
                f"⚠️ Вы уверены, что хотите удалить настройки пользователя {args.user_id}? (y/N): "
            )
            if response.lower() != "y":
                print("❌ Удаление отменено")
                return

        success = await self.manager.delete_user_settings(args.user_id)
        if success:
            print(f"✅ Настройки для пользователя {args.user_id} удалены успешно")
        else:
            print(f"❌ Ошибка при удалении настроек для {args.user_id}")

    async def show_presets(self, args: argparse.Namespace):
        """Показать доступные пресеты"""
        presets = DefaultSettings.list_presets()

        if args.json:
            preset_data = {}
            for preset_name in presets:
                preset_data[preset_name] = DefaultSettings.get_preset_settings(
                    preset_name
                )
            print(json.dumps(preset_data, indent=2, default=str))
        else:
            print("🎯 Доступные пресеты:")
            for preset_name in presets:
                preset_settings = DefaultSettings.get_preset_settings(preset_name)
                print(f"\n📋 {preset_name.upper()}:")
                print(f"  💰 Баланс: {preset_settings['balance_usdt']:,.0f} USDT")
                print(f"  ⚠️ Риск: {preset_settings['risk_per_trade_pct'] * 100:.1f}%")
                print(f"  📈 Плечо: {preset_settings['leverage_target']}x")
                print(f"  🛑 Стоп: {preset_settings['default_stop_value'] * 100:.1f}%")
                print(
                    f"  🎯 Консенсус: {preset_settings['consensus_threshold'] * 100:.1f}%"
                )

    async def validate_settings(self, args: argparse.Namespace):
        """Валидировать настройки"""
        try:
            with open(args.file, encoding="utf-8") as f:
                settings = json.load(f)
        except Exception as e:
            print(f"❌ Ошибка при чтении файла {args.file}: {e}")
            return

        from .validator import SettingsValidator

        errors = SettingsValidator.validate_settings(settings)

        if errors:
            print(f"❌ Найдено {len(errors)} ошибок валидации:")
            for error in errors:
                print(f"  - {error.field}: {error.message}")
        else:
            print("✅ Настройки прошли валидацию успешно")

    async def run(self, args: argparse.Namespace):
        """Запуск команды"""
        if args.command == "list":
            await self.list_users(args)
        elif args.command == "show":
            await self.show_user(args)
        elif args.command == "create":
            await self.create_user(args)
        elif args.command == "update":
            await self.update_user(args)
        elif args.command == "delete":
            await self.delete_user(args)
        elif args.command == "presets":
            await self.show_presets(args)
        elif args.command == "validate":
            await self.validate_settings(args)
        else:
            print("❌ Не указана команда. Используйте --help для справки.")


async def main():
    """Основная функция"""
    cli = SettingsCLI()
    parser = cli.create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    await cli.run(args)


if __name__ == "__main__":
    asyncio.run(main())
