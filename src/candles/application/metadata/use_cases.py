from __future__ import annotations

from typing import Any, cast

from ..api import market_meta_api
from .dto import (
    MetadataRefreshRequest,
    MetadataRefreshResult,
    OrderValidationRequest,
    OrderValidationResult,
)


async def refresh_market_metadata(
    request: MetadataRefreshRequest,
) -> MetadataRefreshResult:
    if request.extended:
        refreshed = await market_meta_api.refresh_okx_meta_extended(request.force)
    else:
        refreshed = await market_meta_api.refresh_okx_meta(force=request.force)

    instruments_count = 0
    if market_meta_api.market_metadata is not None:
        instruments_count = len(market_meta_api.market_metadata.instruments)

    reason = None
    if not refreshed:
        reason = "refresh_failed"

    return MetadataRefreshResult(
        refreshed=refreshed,
        instruments_count=instruments_count,
        provider_id=request.provider_id,
        reason=reason,
    )


async def run_metadata_refresh_job(
    request: MetadataRefreshRequest,
) -> dict[str, Any]:
    result = await refresh_market_metadata(request)
    return {
        "refreshed": result.refreshed,
        "instruments_count": result.instruments_count,
        "provider_id": result.provider_id,
        "reason": result.reason,
    }


def validate_instrument_order(
    request: OrderValidationRequest,
) -> OrderValidationResult:
    violations = market_meta_api.validate_order(
        request.symbol,
        request.price,
        request.qty,
        order_type=request.order_type,
        side=request.side,
        account_balance=request.account_balance,
        **request.extra_params,
    )
    return OrderValidationResult(
        is_valid=not violations,
        violations=tuple(violations),
        warnings=(),
    )


def get_market_instrument_info(symbol: str) -> dict[str, Any] | None:
    return cast("dict[str, Any] | None", market_meta_api.get_instrument_info(symbol))
