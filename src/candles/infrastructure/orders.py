from typing import Any

from .client import OKXClient


class OKXOrders(OKXClient):
    async def place_orders_batch(self, orders: list[dict[str, Any]]) -> dict[str, Any]:
        # Пример batch-запроса на размещение ордеров
        # orders — список ордеров (до 20-50 в batch)
        params = {"orders": orders}
        # Важно: order_count = len(orders) для лимитера
        return await self._request(
            "POST",
            "/api/v5/trade/batch-orders",
            params=params,
            is_order=True,
            order_count=len(orders),
        )
