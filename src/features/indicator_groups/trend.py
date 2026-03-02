"""
Trend Indicators Module

Group: Trend
Dependencies: OHLC, often uses ATR
Max Lookback: 100 bars
Output Fields: adx_14, adx_pos_di, adx_neg_di, aroon_up, aroon_down, supertrend, psar, ichimoku_*

This module calculates trend-following and directional indicators:
- ADX (Average Directional Index): Trend strength measurement
- Aroon: Identifies trend changes and strength
- Supertrend: Dynamic support/resistance based on ATR
- PSAR (Parabolic SAR): Trailing stop and trend indicator
- Ichimoku Cloud: Multi-component trend system
"""

import numpy as np
import pandas as pd

from src.logging import get_logger

from ..ta_safe import safe_ta_with_fallback
from ..utils.indicator_utils import (
    _first_col_or_series,
    _get_col_by_prefix,
    _nan_series,
    check_min_length,
)

logger = get_logger(__name__)


def calc_trend_indicators(
    df: pd.DataFrame, available: set[str], **kwargs
) -> dict[str, pd.Series]:
    """Calculate Trend indicators for directional analysis.

    Гарантирует: все значения Series, индекс == df.index, float dtype где применимо.

    Args:
        df: DataFrame with OHLC data (must have 'open', 'high', 'low', 'close' columns)
        available: Set of indicator names to calculate
        **kwargs: Additional parameters (unused, for Protocol compliance)

    Returns:
        Dictionary mapping indicator names to pandas Series with calculated values

    Example:
        >>> trend_indicators = calc_trend_indicators(df, {'adx_14', 'supertrend', 'psar'})
        >>> adx = trend_indicators['adx_14']
    """
    result: dict[str, pd.Series] = {}

    # Очистка данных один раз в начале
    df = df.copy()
    for col_name in ("open", "high", "low", "close"):
        if col_name in df.columns:
            df[col_name] = pd.to_numeric(df[col_name], errors="coerce")

    # === Ichimoku Cloud ===
    ichimoku_keys = [key for key in available if key.startswith("ichimoku")]
    if ichimoku_keys:
        logger.info(f"ICHIMOKU: Calculating for keys: {ichimoku_keys}")
    if any(key.startswith("ichimoku") for key in available):
        if not check_min_length(df, "ichimoku"):
            logger.warning("ICHIMOKU: недостаточно данных (len<52), возвращаю NaN")
            for k in [
                "ichimoku_tenkan",
                "ichimoku_kijun",
                "ichimoku_senkou_a",
                "ichimoku_senkou_b",
                "ichimoku_chikou",
            ]:
                if k in available:
                    result[k] = _nan_series(df.index, k)
        else:
            try:
                ik = safe_ta_with_fallback(
                    df, "ichimoku", tenkan=9, kijun=26, senkou=52
                )
                if isinstance(ik, list | tuple):
                    ik = ik[0]

                if isinstance(ik, pd.Series):
                    # Если pandas_ta вернул Series, преобразуем в DataFrame
                    ik = ik.to_frame()

                if isinstance(ik, pd.DataFrame):
                    logger.debug(f"ICHIMOKU result columns: {list(ik.columns)}")
                    # Если только одна колонка 'ichimoku', используем fallback расчёт
                    if len(ik.columns) == 1 and "ichimoku" in ik.columns:
                        logger.warning(
                            f"ICHIMOKU: pandas_ta вернул только одну колонку 'ichimoku', "
                            f"используем fallback расчёт. Доступные: {list(ik.columns)}"
                        )
                        # Используем fallback для расчёта всех компонентов
                        try:
                            ik_fallback = safe_ta_with_fallback(
                                df, "ichimoku", tenkan=9, kijun=26, senkou=52
                            )
                            if isinstance(ik_fallback, pd.DataFrame):
                                colmap = {
                                    "ichimoku_tenkan": (
                                        "ITS_",
                                        "TENKAN",
                                        "TENKAN_",
                                        "ichimoku_tenkan",
                                    ),
                                    "ichimoku_kijun": (
                                        "IKS_",
                                        "KIJUN",
                                        "KIJUN_",
                                        "ichimoku_kijun",
                                    ),
                                    "ichimoku_senkou_a": (
                                        "ISA_",
                                        "SENKOU_A",
                                        "LEAD_A",
                                        "ichimoku_senkou_a",
                                    ),
                                    "ichimoku_senkou_b": (
                                        "ISB_",
                                        "SENKOU_B",
                                        "LEAD_B",
                                        "ichimoku_senkou_b",
                                    ),
                                    "ichimoku_chikou": (
                                        "ICS_",
                                        "CHIKOU",
                                        "LAGGING",
                                        "ichimoku_chikou",
                                    ),
                                }
                                for k, prefixes in colmap.items():
                                    if k in available:
                                        found_col = None
                                        if k in ik_fallback.columns:
                                            found_col = k
                                        else:
                                            for c in ik_fallback.columns:
                                                for p in prefixes:
                                                    if c.startswith(p):
                                                        found_col = c
                                                        break
                                                if found_col:
                                                    break
                                        if found_col:
                                            s = _first_col_or_series(
                                                ik_fallback[found_col], k, df.index
                                            )
                                            if k == "ichimoku_chikou":
                                                s = s.fillna(0.0)
                                            result[k] = s
                                        else:
                                            result[k] = _nan_series(df.index, k)
                            else:
                                # Если fallback тоже не сработал, возвращаем NaN
                                for k in [
                                    "ichimoku_tenkan",
                                    "ichimoku_kijun",
                                    "ichimoku_senkou_a",
                                    "ichimoku_senkou_b",
                                    "ichimoku_chikou",
                                ]:
                                    if k in available:
                                        result[k] = _nan_series(df.index, k)
                        except Exception as fallback_e:
                            logger.error(f"ICHIMOKU fallback failed: {fallback_e}")
                            for k in [
                                "ichimoku_tenkan",
                                "ichimoku_kijun",
                                "ichimoku_senkou_a",
                                "ichimoku_senkou_b",
                                "ichimoku_chikou",
                            ]:
                                if k in available:
                                    result[k] = _nan_series(df.index, k)
                    else:
                        # Сначала проверяем канонические имена, потом префиксы
                        colmap = {
                            "ichimoku_tenkan": ("ITS_", "TENKAN", "TENKAN_"),
                            "ichimoku_kijun": ("IKS_", "KIJUN", "KIJUN_"),
                            "ichimoku_senkou_a": ("ISA_", "SENKOU_A", "LEAD_A"),
                            "ichimoku_senkou_b": ("ISB_", "SENKOU_B", "LEAD_B"),
                            "ichimoku_chikou": ("ICS_", "CHIKOU", "LAGGING"),
                        }

                        for k, prefixes in colmap.items():
                            if k in available:
                                # Сначала проверяем каноническое имя
                                found_col: str | None = None
                                if k in ik.columns:
                                    found_col = k
                                else:
                                    # Потом ищем по префиксам
                                    for c in ik.columns:
                                        for p in prefixes:
                                            if c.startswith(p):
                                                found_col = c
                                                break
                                        if found_col:
                                            break
                                if found_col:
                                    s = _first_col_or_series(ik[found_col], k, df.index)
                                else:
                                    logger.warning(
                                        f"ICHIMOKU: не найдена колонка {k}, доступные: {list(ik.columns)}"
                                    )
                                    s = _nan_series(df.index, k)
                                if k == "ichimoku_chikou":
                                    s = s.fillna(0.0)
                                result[k] = s
                else:
                    for k in [
                        "ichimoku_tenkan",
                        "ichimoku_kijun",
                        "ichimoku_senkou_a",
                        "ichimoku_senkou_b",
                        "ichimoku_chikou",
                    ]:
                        if k in available:
                            result[k] = _nan_series(df.index, k)
            except Exception as e:
                logger.error(f"Ошибка расчёта Ichimoku: {type(e).__name__}: {e}")
                for k in [
                    "ichimoku_tenkan",
                    "ichimoku_kijun",
                    "ichimoku_senkou_a",
                    "ichimoku_senkou_b",
                    "ichimoku_chikou",
                ]:
                    if k in available:
                        result[k] = _nan_series(df.index, k)

    # === ADX ===
    if any(key.startswith("adx") for key in available):
        try:
            adx_result = safe_ta_with_fallback(df, "adx", length=14)
            if isinstance(adx_result, pd.DataFrame):
                if "adx_14" in available:
                    result["adx_14"] = _first_col_or_series(
                        (
                            adx_result.get("adx_14")
                            if "adx_14" in adx_result.columns
                            else None
                        ),
                        "adx_14",
                        df.index,
                    )
                if "adx_pos_di" in available:
                    result["adx_pos_di"] = _first_col_or_series(
                        (
                            adx_result.get("adx_pos_di")
                            if "adx_pos_di" in adx_result.columns
                            else None
                        ),
                        "adx_pos_di",
                        df.index,
                    )
                if "adx_neg_di" in available:
                    result["adx_neg_di"] = _first_col_or_series(
                        (
                            adx_result.get("adx_neg_di")
                            if "adx_neg_di" in adx_result.columns
                            else None
                        ),
                        "adx_neg_di",
                        df.index,
                    )
            else:
                for key in ["adx_14", "adx_pos_di", "adx_neg_di"]:
                    if key in available:
                        result[key] = _nan_series(df.index, key)
        except Exception as e:
            logger.error(f"Ошибка расчёта ADX: {type(e).__name__}: {e}")
            for key in ["adx_14", "adx_pos_di", "adx_neg_di"]:
                if key in available:
                    result[key] = _nan_series(df.index, key)

    # === Supertrend ===
    if any(key.startswith("supertrend") for key in available):
        try:
            st = safe_ta_with_fallback(df, "supertrend", length=10, multiplier=3.0)
            logger.debug(
                f"SUPERTREND result type: {type(st)}, columns: {st.columns if isinstance(st, pd.DataFrame) else 'N/A'}"
            )
            if isinstance(st, pd.DataFrame):
                if "supertrend" in available:
                    # Сначала проверяем каноническое имя, потом префикс
                    if "supertrend" in st.columns:
                        result["supertrend"] = _first_col_or_series(
                            st["supertrend"], "supertrend", df.index
                        )
                    else:
                        c = _get_col_by_prefix(st, "SUPERT_")
                        if c:
                            result["supertrend"] = _first_col_or_series(
                                st[[c]], "supertrend", df.index
                            )
                        else:
                            logger.warning(
                                f"SUPERTREND: не найдена колонка supertrend, доступные: {list(st.columns)}"
                            )
                            result["supertrend"] = _nan_series(df.index, "supertrend")
                if "supertrend_direction" in available:
                    if "supertrend_direction" in st.columns:
                        result["supertrend_direction"] = _first_col_or_series(
                            st["supertrend_direction"], "supertrend_direction", df.index
                        )
                    else:
                        c = _get_col_by_prefix(st, "SUPERTd_")
                        if c:
                            result["supertrend_direction"] = _first_col_or_series(
                                st[[c]], "supertrend_direction", df.index
                            )
                        else:
                            logger.warning(
                                f"SUPERTREND: не найдена колонка supertrend_direction, доступные: {list(st.columns)}"
                            )
                            result["supertrend_direction"] = _nan_series(
                                df.index, "supertrend_direction"
                            )
                if "supertrend_long" in available:
                    if "supertrend_long" in st.columns:
                        result["supertrend_long"] = _first_col_or_series(
                            st["supertrend_long"], "supertrend_long", df.index
                        )
                    else:
                        c = _get_col_by_prefix(st, "SUPERTl_")
                        if c:
                            result["supertrend_long"] = _first_col_or_series(
                                st[[c]], "supertrend_long", df.index
                            )
                        else:
                            logger.warning(
                                f"SUPERTREND: не найдена колонка supertrend_long, доступные: {list(st.columns)}"
                            )
                            result["supertrend_long"] = _nan_series(
                                df.index, "supertrend_long"
                            )
                if "supertrend_short" in available:
                    if "supertrend_short" in st.columns:
                        result["supertrend_short"] = _first_col_or_series(
                            st["supertrend_short"], "supertrend_short", df.index
                        )
                    else:
                        c = _get_col_by_prefix(st, "SUPERTs_")
                        if c:
                            result["supertrend_short"] = _first_col_or_series(
                                st[[c]], "supertrend_short", df.index
                            )
                        else:
                            logger.warning(
                                f"SUPERTREND: не найдена колонка supertrend_short, доступные: {list(st.columns)}"
                            )
                            result["supertrend_short"] = _nan_series(
                                df.index, "supertrend_short"
                            )
            else:
                for k in [
                    "supertrend",
                    "supertrend_direction",
                    "supertrend_long",
                    "supertrend_short",
                ]:
                    if k in available:
                        result[k] = _nan_series(df.index, k)
        except Exception as e:
            logger.error(f"Ошибка расчёта Supertrend: {type(e).__name__}: {e}")
            for k in [
                "supertrend",
                "supertrend_direction",
                "supertrend_long",
                "supertrend_short",
            ]:
                if k in available:
                    result[k] = _nan_series(df.index, k)

    # === Chande Kroll Stop (CKSP) ===
    if any(key.startswith("cksp") for key in available):
        try:
            ck = safe_ta_with_fallback(df, "cksp", p=10, x=1, q=9)
            if isinstance(ck, pd.DataFrame):
                if "cksp_upper" in available:
                    col_u = _get_col_by_prefix(ck, "CKSPU_")
                    result["cksp_upper"] = _first_col_or_series(
                        ck[[col_u]] if col_u else None, "cksp_upper", df.index
                    )
                if "cksp_lower" in available:
                    col_l = _get_col_by_prefix(ck, "CKSPL_")
                    result["cksp_lower"] = _first_col_or_series(
                        ck[[col_l]] if col_l else None, "cksp_lower", df.index
                    )
            else:
                for key in ["cksp_upper", "cksp_lower"]:
                    if key in available:
                        result[key] = _nan_series(df.index, key)
        except Exception as e:
            logger.error(f"Ошибка расчёта CKSP: {type(e).__name__}: {e}")
            for key in ["cksp_upper", "cksp_lower"]:
                if key in available:
                    result[key] = _nan_series(df.index, key)

    # === PSAR (Parabolic SAR) ===
    if any(key.startswith("psar") for key in available):
        try:
            if not check_min_length(df, "psar"):
                logger.warning("PSAR: недостаточно данных (len<5), возвращаю NaN")
                ps = pd.DataFrame(index=df.index)
            else:
                ps = safe_ta_with_fallback(df, "psar", af=0.02, max_af=0.2)
                logger.debug(
                    f"PSAR result type: {type(ps)}, columns: {ps.columns if isinstance(ps, pd.DataFrame) else 'N/A'}"
                )

            if isinstance(ps, pd.DataFrame):
                # Сначала проверяем канонические имена, потом префиксы
                long_c = (
                    "psar_long"
                    if "psar_long" in ps.columns
                    else _get_col_by_prefix(ps, "PSARl_")
                )
                short_c = (
                    "psar_short"
                    if "psar_short" in ps.columns
                    else _get_col_by_prefix(ps, "PSARs_")
                )

                if "psar" in available:
                    # Пробуем найти основную колонку PSAR
                    if "psar" in ps.columns:
                        result["psar"] = _first_col_or_series(
                            ps["psar"], "psar", df.index
                        )
                    else:
                        base_c = (
                            long_c
                            or short_c
                            or (ps.columns[0] if len(ps.columns) > 0 else None)
                        )
                        result["psar"] = _first_col_or_series(
                            ps[[base_c]] if base_c else None, "psar", df.index
                        )

                if "psar_direction" in available:
                    if long_c and short_c:
                        dir_arr = np.zeros(len(df), dtype="int8")
                        idx = df.index
                        long_mask = ps[long_c].reindex(idx).notna().to_numpy()
                        short_mask = ps[short_c].reindex(idx).notna().to_numpy()
                        dir_arr[long_mask] = 1
                        dir_arr[short_mask] = -1
                        result["psar_direction"] = pd.Series(
                            dir_arr, index=idx, name="psar_direction", dtype="int8"
                        )
                    else:
                        result["psar_direction"] = _nan_series(
                            df.index, "psar_direction"
                        )

                if "psar_long" in available:
                    if long_c:
                        result["psar_long"] = _first_col_or_series(
                            ps[[long_c]], "psar_long", df.index
                        )
                    else:
                        logger.warning(
                            f"PSAR: не найдена колонка psar_long, доступные: {list(ps.columns)}"
                        )
                        result["psar_long"] = _nan_series(df.index, "psar_long")

                if "psar_short" in available:
                    if short_c:
                        result["psar_short"] = _first_col_or_series(
                            ps[[short_c]], "psar_short", df.index
                        )
                    else:
                        logger.warning(
                            f"PSAR: не найдена колонка psar_short, доступные: {list(ps.columns)}"
                        )
                        result["psar_short"] = _nan_series(df.index, "psar_short")
            else:
                for k in ["psar", "psar_direction", "psar_long", "psar_short"]:
                    if k in available:
                        result[k] = _nan_series(df.index, k)
        except Exception as e:
            logger.error(f"Ошибка расчёта PSAR: {type(e).__name__}: {e}")
            for k in ["psar", "psar_direction", "psar_long", "psar_short"]:
                if k in available:
                    result[k] = _nan_series(df.index, k)

    # === Aroon ===
    if any(key.startswith("aroon") for key in available):
        try:
            ar = safe_ta_with_fallback(df, "aroon", length=14)
            if isinstance(ar, pd.DataFrame):
                if "aroon_up" in available:
                    result["aroon_up"] = _first_col_or_series(
                        ar.get("aroon_up") if "aroon_up" in ar.columns else None,
                        "aroon_up",
                        df.index,
                    )
                if "aroon_down" in available:
                    result["aroon_down"] = _first_col_or_series(
                        ar.get("aroon_down") if "aroon_down" in ar.columns else None,
                        "aroon_down",
                        df.index,
                    )
                if "aroon_osc" in available:
                    result["aroon_osc"] = _first_col_or_series(
                        ar.get("aroon_osc") if "aroon_osc" in ar.columns else None,
                        "aroon_osc",
                        df.index,
                    )
            else:
                for key in ["aroon_up", "aroon_down", "aroon_osc"]:
                    if key in available:
                        result[key] = _nan_series(df.index, key)
        except Exception as e:
            logger.error(f"Ошибка расчёта Aroon: {type(e).__name__}: {e}")
            for key in ["aroon_up", "aroon_down", "aroon_osc"]:
                if key in available:
                    result[key] = _nan_series(df.index, key)

    # Stage E: Additional trend indicators
    if "amat" in available:
        try:
            if len(df) >= 14:
                amat_result = safe_ta_with_fallback(df, "amat", length=14)
                result["amat"] = _first_col_or_series(amat_result, "amat", df.index)
            else:
                result["amat"] = _nan_series(df.index, "amat")
        except Exception as e:
            logger.error(f"Ошибка расчёта AMAT: {type(e).__name__}: {e}")
            result["amat"] = _nan_series(df.index, "amat")

    if "chop" in available:
        try:
            if len(df) >= 14:
                chop_result = safe_ta_with_fallback(df, "chop", length=14)
                result["chop"] = _first_col_or_series(chop_result, "chop", df.index)
            else:
                result["chop"] = _nan_series(df.index, "chop")
        except Exception as e:
            logger.error(f"Ошибка расчёта CHOP: {type(e).__name__}: {e}")
            result["chop"] = _nan_series(df.index, "chop")

    if "decay" in available:
        try:
            if len(df) >= 5:
                decay_result = safe_ta_with_fallback(df, "decay", length=5)
                result["decay"] = _first_col_or_series(decay_result, "decay", df.index)
            else:
                result["decay"] = _nan_series(df.index, "decay")
        except Exception as e:
            logger.error(f"Ошибка расчёта DECAY: {type(e).__name__}: {e}")
            result["decay"] = _nan_series(df.index, "decay")

    if "decreasing" in available:
        try:
            if len(df) >= 5:
                decreasing_result = safe_ta_with_fallback(df, "decreasing", length=5)
                result["decreasing"] = _first_col_or_series(
                    decreasing_result, "decreasing", df.index
                )
            else:
                result["decreasing"] = _nan_series(df.index, "decreasing")
        except Exception as e:
            logger.error(f"Ошибка расчёта DECREASING: {type(e).__name__}: {e}")
            result["decreasing"] = _nan_series(df.index, "decreasing")

    if "dpo" in available:
        try:
            if len(df) >= 20:
                dpo_result = safe_ta_with_fallback(df, "dpo", length=20)
                result["dpo"] = _first_col_or_series(dpo_result, "dpo", df.index)
            else:
                result["dpo"] = _nan_series(df.index, "dpo")
        except Exception as e:
            logger.error(f"Ошибка расчёта DPO: {type(e).__name__}: {e}")
            result["dpo"] = _nan_series(df.index, "dpo")

    if "increasing" in available:
        try:
            if len(df) >= 5:
                increasing_result = safe_ta_with_fallback(df, "increasing", length=5)
                result["increasing"] = _first_col_or_series(
                    increasing_result, "increasing", df.index
                )
            else:
                result["increasing"] = _nan_series(df.index, "increasing")
        except Exception as e:
            logger.error(f"Ошибка расчёта INCREASING: {type(e).__name__}: {e}")
            result["increasing"] = _nan_series(df.index, "increasing")

    if "long_run" in available:
        try:
            if len(df) >= 14:
                long_run_result = safe_ta_with_fallback(df, "long_run")
                result["long_run"] = _first_col_or_series(
                    long_run_result, "long_run", df.index
                )
            else:
                result["long_run"] = _nan_series(df.index, "long_run")
        except Exception as e:
            logger.error(f"Ошибка расчёта LONG_RUN: {type(e).__name__}: {e}")
            result["long_run"] = _nan_series(df.index, "long_run")

    if "qstick" in available:
        try:
            if len(df) >= 14:
                qstick_result = safe_ta_with_fallback(df, "qstick", length=14)
                result["qstick"] = _first_col_or_series(
                    qstick_result, "qstick", df.index
                )
            else:
                result["qstick"] = _nan_series(df.index, "qstick")
        except Exception as e:
            logger.error(f"Ошибка расчёта QSTICK: {type(e).__name__}: {e}")
            result["qstick"] = _nan_series(df.index, "qstick")

    if "short_run" in available:
        try:
            if len(df) >= 14:
                short_run_result = safe_ta_with_fallback(df, "short_run")
                result["short_run"] = _first_col_or_series(
                    short_run_result, "short_run", df.index
                )
            else:
                result["short_run"] = _nan_series(df.index, "short_run")
        except Exception as e:
            logger.error(f"Ошибка расчёта SHORT_RUN: {type(e).__name__}: {e}")
            result["short_run"] = _nan_series(df.index, "short_run")

    if "ttm_trend" in available:
        try:
            if len(df) >= 14:
                ttm_trend_result = safe_ta_with_fallback(df, "ttm_trend", length=14)
                result["ttm_trend"] = _first_col_or_series(
                    ttm_trend_result, "ttm_trend", df.index
                )
            else:
                result["ttm_trend"] = _nan_series(df.index, "ttm_trend")
        except Exception as e:
            logger.error(f"Ошибка расчёта TTM_TREND: {type(e).__name__}: {e}")
            result["ttm_trend"] = _nan_series(df.index, "ttm_trend")

    # === Vortex Indicator ===
    vortex_keys = ["vortex", "vortex_pos", "vortex_neg"]
    if any(key in available for key in vortex_keys):
        try:
            if check_min_length(df, "vortex"):
                vortex_result = safe_ta_with_fallback(df, "vortex", length=14)
                if isinstance(vortex_result, pd.DataFrame):
                    # Проверяем наличие всех компонентов
                    if (
                        "vortex_pos" in vortex_result.columns
                        and "vortex_pos" in available
                    ):
                        result["vortex_pos"] = _first_col_or_series(
                            vortex_result["vortex_pos"], "vortex_pos", df.index
                        )
                    if (
                        "vortex_neg" in vortex_result.columns
                        and "vortex_neg" in available
                    ):
                        result["vortex_neg"] = _first_col_or_series(
                            vortex_result["vortex_neg"], "vortex_neg", df.index
                        )
                    if "vortex" in vortex_result.columns and "vortex" in available:
                        result["vortex"] = _first_col_or_series(
                            vortex_result["vortex"], "vortex", df.index
                        )
                    # Если есть только одна колонка "vortex", используем fallback
                    elif (
                        len(vortex_result.columns) == 1
                        and "vortex" in vortex_result.columns
                    ):
                        # Fallback уже должен вернуть все компоненты
                        vortex_fallback = safe_ta_with_fallback(df, "vortex", length=14)
                        if isinstance(vortex_fallback, pd.DataFrame):
                            if (
                                "vortex_pos" in vortex_fallback.columns
                                and "vortex_pos" in available
                            ):
                                result["vortex_pos"] = _first_col_or_series(
                                    vortex_fallback["vortex_pos"],
                                    "vortex_pos",
                                    df.index,
                                )
                            if (
                                "vortex_neg" in vortex_fallback.columns
                                and "vortex_neg" in available
                            ):
                                result["vortex_neg"] = _first_col_or_series(
                                    vortex_fallback["vortex_neg"],
                                    "vortex_neg",
                                    df.index,
                                )
                            if (
                                "vortex" in vortex_fallback.columns
                                and "vortex" in available
                            ):
                                result["vortex"] = _first_col_or_series(
                                    vortex_fallback["vortex"], "vortex", df.index
                                )
                else:
                    # Если не DataFrame, возвращаем NaN для всех компонентов
                    for key in vortex_keys:
                        if key in available:
                            result[key] = _nan_series(df.index, key)
            else:
                for key in vortex_keys:
                    if key in available:
                        result[key] = _nan_series(df.index, key)
        except Exception as e:
            logger.error(f"Ошибка расчёта VORTEX: {type(e).__name__}: {e}")
            for key in vortex_keys:
                if key in available:
                    result[key] = _nan_series(df.index, key)

    # === Stochastic ===
    if "stoch_k" in available or "stoch_d" in available:
        try:
            stoch_result = safe_ta_with_fallback(df, "stoch", k=14, d=3)
            if isinstance(stoch_result, pd.DataFrame):
                if "stoch_k" in available:
                    col_k = _get_col_by_prefix(stoch_result, "STOCHk")
                    if col_k:
                        result["stoch_k"] = _first_col_or_series(
                            stoch_result[[col_k]], "stoch_k", df.index
                        )
                    elif len(stoch_result.columns) > 0:
                        result["stoch_k"] = _first_col_or_series(
                            stoch_result.iloc[:, [0]], "stoch_k", df.index
                        )
                    else:
                        result["stoch_k"] = _nan_series(df.index, "stoch_k")

                if "stoch_d" in available:
                    col_d = _get_col_by_prefix(stoch_result, "STOCHd")
                    if col_d:
                        result["stoch_d"] = _first_col_or_series(
                            stoch_result[[col_d]], "stoch_d", df.index
                        )
                    elif len(stoch_result.columns) > 1:
                        result["stoch_d"] = _first_col_or_series(
                            stoch_result.iloc[:, [1]], "stoch_d", df.index
                        )
                    else:
                        result["stoch_d"] = _nan_series(df.index, "stoch_d")
            else:
                for key in ["stoch_k", "stoch_d"]:
                    if key in available:
                        result[key] = _nan_series(df.index, key)
        except Exception as e:
            logger.error(f"Ошибка расчёта Stochastic: {type(e).__name__}: {e}")
            for key in ["stoch_k", "stoch_d"]:
                if key in available:
                    result[key] = _nan_series(df.index, key)

    # === Ultimate Oscillator ===
    if "ultosc" in available:
        try:
            ultosc_result = safe_ta_with_fallback(df, "uo", short=7, medium=14, long=28)
            result["ultosc"] = _first_col_or_series(ultosc_result, "ultosc", df.index)
        except Exception as e:
            logger.error(f"Ошибка расчёта Ultimate Oscillator: {type(e).__name__}: {e}")
            result["ultosc"] = _nan_series(df.index, "ultosc")

    # Гарантируем, что все значения - Series
    assert all(
        isinstance(v, pd.Series) for v in result.values()
    ), "Все значения должны быть Series"

    return result
