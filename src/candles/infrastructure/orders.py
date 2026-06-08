from typing import Any, cast

from .client import OKXClient


class OKXOrders(OKXClient):
    async def place_orders_batch(self, orders: list[dict[str, Any]]) -> dict[str, Any]:
        # Example batch request for placing orders
        # orders — list of orders (up to 20-50 per batch)
        params = {"orders": orders}
        # Important: order_count = len(orders) for the rate limiter
        return cast(
            "dict[str, Any]",
            await self._request(
                "POST",
                "/api/v5/trade/batch-orders",
                params=params,
                is_order=True,
                order_count=len(orders),
            ),
        )
