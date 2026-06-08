# Trading Glossary

This glossary defines the domain concepts used throughout the **pklpo** quantitative trading system. Terms cover the full pipeline: instrument selection and eligibility, candle data and quality, feature computation, regime classification, and market selection scoring. Definitions reference the authoritative source file or database table where the concept is implemented.

Sections:
1. [Instruments](#instruments)
2. [Candles & OHLCV](#candles--ohlcv)
3. [Eligibility & Data Quality](#eligibility--data-quality)
4. [Timeframes](#timeframes)
5. [Features Pipeline](#features-pipeline-1)
6. [Market Selection & Regimes](#market-selection--regimes)
7. [NaN Semantics](#nan-semantics-1)

---

<!-- Instruments -->

## Active Instrument

**Definition:** A perpetual swap instrument that is currently listed on OKX and available for trading. An instrument is considered active when it appears in the live OKX instruments endpoint and has not been delisted or suspended. The candle sync pipeline filters down to active instruments before attempting OHLCV ingestion.

**Source of truth:** `src/candles/infrastructure/` (OKX exchange adapter); instruments list backed by `ops/airflow/dags/` load-instruments DAG.

**Gotchas:**
- An instrument can be active on the exchange but still fail the eligibility gate due to insufficient history.
- Instruments that were delisted mid-history window produce gaps that can cause `INCOMPLETE_HISTORY` state even after relisting.
- "Active" is an exchange-side concept; do not conflate with `ELIGIBLE` (a pipeline-side concept).

---

## Eligible Instrument

**Definition:** An instrument that has passed all eligibility checks and is cleared for use in feature computation and ML scoring. Eligibility is the output of the eligibility gate — it requires sufficient candle history, high coverage (>=99.5%), and a non-disabled timeframe role. An eligible instrument has `EligibilityState.ELIGIBLE` across the required timeframe roles.

**Source of truth:** `src/candles/application/eligibility/evaluate.py`; result persisted via `src/candles/infrastructure/eligibility_repository.py`.

**Gotchas:**
- Eligibility is per-instrument per-timeframe, not global. An instrument can be ELIGIBLE on 1H but INSUFFICIENT_HISTORY on 1D.
- Eligibility state is recomputed each pipeline run; a previously eligible instrument can become ineligible if new gaps appear.
- Do not use `eligible_instrument` as a synonym for `active_instrument` — they are distinct pipeline stages.

---

## Swap Instrument

**Definition:** A perpetual futures contract (perpetual swap) on OKX, denominated and margined in USDT. The pklpo system exclusively processes swap instruments (e.g., `BTC-USDT-SWAP`), not spot pairs or dated futures. Swap OHLCV data is stored in its own schema partition.

**Source of truth:** `src/candles/` (application and infrastructure layers); DB tables `candles_swap_1h` / `swap_ohlcv_p`.

**Gotchas:**
- Swaps trade continuously (24/7), so there are no market-open gaps — any missing candle is a genuine data gap, not a weekend/holiday artifact.
- Funding rates, liquidation cascades, and listing events can produce anomalous candles; these are not filtered by default.
- The `-SWAP` suffix in the instrument ID is required for OKX API calls; omitting it returns spot data silently.

---

## Universe Size

**Definition:** The count of instruments that have passed market selection and are included in the active trading universe at a given evaluation cycle. `universe_size` is a scalar output of the market selection pipeline that feeds downstream position sizing and portfolio construction.

**Source of truth:** `src/market_selection/application/pipeline.py`; stored in `market_selection_results`.

**Gotchas:**
- Universe size can shrink significantly during high-volatility regimes as noise and stability scores deteriorate.
- A hard floor or ceiling on universe size is not enforced in the pipeline itself — downstream consumers must guard against empty or overly large universes.
- `universe_size` reflects selected instruments, not all eligible ones; selection imposes additional scoring criteria on top of eligibility.

---

<!-- Candles & OHLCV -->

## Bar

**Definition:** A synonym for `candle` used in the context of aggregated OHLCV data, emphasising the time-period unit rather than the visual representation. In code, "bar" often appears in variable names (`required_bars`, `lookback_bars`) and refers to a single time-period data record. One bar = one candle = one OHLCV row.

**Source of truth:** `src/candles/domain/`; CLI command `build-bars`.

**Gotchas:**
- "Bar" is interchangeable with "candle" in this codebase, but prefer `bar` in numerical/count contexts and `candle` in data-model contexts to match the dominant naming in each layer.
- A bar covering a period where no trades occurred may be forward-filled from the previous close; this is a synthetic bar and can distort volume indicators.

---

## Candle

**Definition:** A single OHLCV record representing all trade activity within one time period (e.g., one hour). Each candle has five fields: Open (first trade price), High (maximum price), Low (minimum price), Close (last trade price), and Volume (total base-asset volume traded). Candles are the atomic unit of market data in pklpo.

**Source of truth:** `src/candles/domain/`; DB table `candles_swap_1h`.

**Gotchas:**
- A candle with `volume = 0` may be a padding/fill artifact rather than a genuine illiquid candle — treat it with caution in volume-sensitive indicators.
- OKX delivers candles in UTC; any timezone conversion must happen at the presentation layer, never in the domain.
- The timestamp on a candle represents the **open** of the period, not the close.

---

## OHLCV

**Definition:** Acronym for Open, High, Low, Close, Volume — the five standard fields that describe trading activity within a time period. This is the canonical market data format ingested from OKX and stored in the pklpo database. All downstream feature calculations derive from OHLCV candles.

**Source of truth:** `src/candles/domain/`; DB tables `candles_swap_1h` / `swap_ohlcv_p`.

**Gotchas:**
- Volume in OKX swap OHLCV is denominated in contracts (lot units), not base-asset units in all endpoints — confirm the unit before building volume-normalised features.
- High and Low represent the intraperiod extremes; they can spike far beyond Open/Close on liquidation wicks, distorting ATR and volatility calculations.
- Never treat OHLCV as tick data — information within the period (e.g., trade sequence, order book) is irretrievably lost.

---

## Grain

**Definition:** The temporal resolution of a candle series, expressed as a timeframe string (e.g., `1H`, `4H`, `1D`, `1W`). Grain determines how many candles fit into a given lookback window and is the primary axis along which the timeframe hierarchy is defined. In pklpo, features are computed at the grain of their source candle series.

**Source of truth:** `src/candles/application/`; timeframe configuration in `src/candles/application/eligibility/ports.py`.

**Gotchas:**
- "Grain" and "timeframe" are used interchangeably in some parts of the codebase, but grain is the more precise term when referring to resolution of the raw data.
- Coarser grains (1D, 1W) have fewer bars per year, so `required_bars` translates to much longer calendar history at coarser grains.
- Mixing grains in a single indicator calculation without explicit alignment can silently produce look-ahead bias.

---

<!-- Eligibility & Data Quality -->

## Coverage PCT

**Definition:** The ratio of non-null candles to expected candles in a given window, expressed as a percentage. `coverage_pct` quantifies how complete the historical data is for an instrument-timeframe combination. The eligibility gate requires `coverage_pct >= 99.5%` for FULL and CONTEXT roles to proceed to feature computation.

**Source of truth:** `src/candles/infrastructure/eligibility_repository.py`; computed in `src/candles/application/eligibility/evaluate.py`.

**Gotchas:**
- Coverage is computed over the window defined by `required_bars`, not over all available history — an instrument with 2 years of data but a gap in the recent window will fail.
- A coverage of exactly 99.5% passes; anything below is `INCOMPLETE_HISTORY`.
- High coverage does not guarantee data quality — all 99.5% of candles could be zero-volume padding artifacts.

---

## Data Quality Gate

**Definition:** The combined set of checks that a candle series must pass before it is considered usable for feature computation. The gate validates coverage percentage, minimum bar count, and history validity. It is the broader concept of which `coverage_pct` and `required_bars` are sub-checks.

**Source of truth:** `src/candles/application/eligibility/evaluate.py`; `src/candles/infrastructure/eligibility_repository.py`.

**Gotchas:**
- The data quality gate is evaluated per timeframe per instrument — passing on 1H does not imply passing on 1D.
- Gate results are cached in the eligibility repository; stale results can persist if the recomputation DAG has not run.
- "Data quality gate" and "eligibility gate" are closely related but not synonyms: the eligibility gate is the broader pipeline check (role + state), while the data quality gate refers specifically to the coverage/history checks.

---

## Eligibility Gate

**Definition:** The pipeline checkpoint that decides whether an instrument-timeframe combination is cleared for downstream processing (feature computation, scoring, or training). The gate combines the `EligibilityState` (data quality outcome) with the `TimeframeRole` (structural assignment) to derive capability flags (`can_score`, `can_compute_features`). Only instruments that pass the eligibility gate enter the features pipeline.

**Source of truth:** `src/candles/application/eligibility/evaluate.py`.

**Gotchas:**
- The gate blocks the entire instrument if any mandatory timeframe fails — not just the failing timeframe.
- Eligibility gate results must be recomputed after every candle sync batch; using stale gate outputs can cause feature computation on incomplete data.
- The gate does not inspect candle values (e.g., price anomalies), only presence/absence.

---

## EligibilityState

**Definition:** An enum encoding the outcome of the data quality check for a single instrument-timeframe pair. Values: `ELIGIBLE` — sufficient history, high coverage, passes all checks; `INSUFFICIENT_HISTORY` — not enough bars to meet `required_bars` but some data exists; `INCOMPLETE_HISTORY` — enough bars exist but `coverage_pct < 99.5%`; `INVALID_HISTORY` — data is present but fails integrity checks; `INFORMATIONAL_ONLY` — assigned to INFORMATIONAL role timeframes; `DISABLED` — explicitly disabled, no computation attempted.

**Source of truth:** `src/candles/application/eligibility/evaluate.py`.

**Gotchas:**
- `INSUFFICIENT_HISTORY` still allows `can_compute_features = True` for FULL/CONTEXT roles — partial feature computation is permitted.
- `INFORMATIONAL_ONLY` is not a failure state; it is the expected state for coarse timeframes (e.g., 1M) that provide macro context without full feature sets.
- Do not compare `EligibilityState` values ordinally — there is no implied severity ranking between INSUFFICIENT and INCOMPLETE.

---

## QualityResult

**Definition:** A data class or named tuple returned by the data quality gate evaluation, encapsulating the `EligibilityState`, the measured `coverage_pct`, the actual bar count, and any diagnostic messages. `QualityResult` is the internal transfer object passed between the eligibility evaluator and the eligibility repository.

**Source of truth:** `src/candles/application/eligibility/evaluate.py`.

**Gotchas:**
- `QualityResult` is an internal type; do not expose it directly to CLI output without formatting — raw values (e.g., floating point coverage) should be rounded for display.
- A `QualityResult` with `state=ELIGIBLE` and `coverage_pct=99.4` should not exist; if observed, it indicates a rounding inconsistency between the threshold check and the stored value.

---

## Window-Based Coverage

**Definition:** Coverage calculation performed over a sliding or fixed-length window of the most recent N bars (where N = `required_bars` for the role), rather than over the entire available history. Window-based coverage ensures that recent data completeness is evaluated, preventing old complete history from masking recent gaps.

**Source of truth:** `src/candles/infrastructure/eligibility_repository.py`.

**Gotchas:**
- If the total available history is shorter than the window, coverage is computed over all available bars — this can artificially inflate coverage for newly listed instruments.
- Changing `required_bars` changes the window, and therefore changes `coverage_pct` for the same raw data.
- Window-based coverage was introduced to replace total-history coverage; old DAG runs may have stored total-history metrics — verify the computation method when auditing historical eligibility records.

---

## Required Bars

**Definition:** The minimum number of candles that must be present in the lookback window for an instrument-timeframe pair to be considered for ELIGIBLE status. Required bars are defined per `TimeframeRole`: FULL = 500 bars, CONTEXT = 280 bars, INFORMATIONAL = 0 bars (no check performed).

**Source of truth:** `src/candles/application/eligibility/evaluate.py`; `src/candles/application/eligibility/ports.py`.

**Gotchas:**
- `required_bars` is a necessary condition for ELIGIBLE, not sufficient — `coverage_pct` must also meet the threshold.
- For INFORMATIONAL role, `required_bars = 0` means no data check is performed; the state is always `INFORMATIONAL_ONLY`.
- On a 1D grain, 500 bars ≈ 2 years of history; on a 1H grain, 500 bars ≈ 21 days — the same threshold implies very different calendar lookbacks.

---

## Lookback Bars

**Definition:** The number of historical bars consumed by a specific indicator or feature calculation. `lookback_bars` is indicator-specific and may be smaller than `required_bars`. It defines how far back a single feature computation looks into the candle series.

**Source of truth:** `src/features/` (individual indicator implementations).

**Gotchas:**
- `lookback_bars` for a feature must be <= the available bars after the eligibility gate; otherwise the first N rows of the feature series will be NaN.
- Cascaded indicators (e.g., smoothed RSI) have a `lookback_bars` equal to the sum of each component's lookback, not the maximum.
- Do not confuse `lookback_bars` (per-indicator) with `required_bars` (per-role threshold for eligibility).

---

<!-- Timeframes -->

## Timeframe Hierarchy

**Definition:** The ordered set of granularities used in the pklpo multi-timeframe analysis framework, from finest to coarsest: `1H → 4H → 1D → 1W → 1M`. Each timeframe is assigned a `TimeframeRole` that determines how its data participates in feature computation and scoring. The hierarchy enforces that coarser timeframes provide strategic context while finer timeframes drive signal generation.

**Source of truth:** `src/candles/application/eligibility/ports.py`.

**Gotchas:**
- There is no automatic alignment between timeframes — a 4H bar is not guaranteed to align to the boundary of four 1H bars if any 1H bars are missing.
- The hierarchy is fixed in configuration; adding a new timeframe (e.g., `2H`) requires explicit role assignment and `required_bars` configuration.
- 1M is INFORMATIONAL — it is in the hierarchy but contributes no scored features.

---

## TimeframeRole

**Definition:** An enum assigning a structural role to each timeframe grain, determining what computation is allowed. `FULL` — full feature set, can score and train ML models, assigned to 1H, 4H, 1D. `CONTEXT` — context features only, no scoring, assigned to 1W. `INFORMATIONAL` — read-only macro context, no computation, assigned to 1M. `INACTIVE` — explicitly disabled, no computation or data ingestion.

**Source of truth:** `src/candles/application/eligibility/ports.py`.

**Gotchas:**
- `TimeframeRole` is a static configuration assignment, not derived from data quality — CONTEXT does not mean the data is incomplete.
- Changing a timeframe's role has cascading effects on `required_bars`, capability flags, and feature group execution.
- `INACTIVE` is distinct from `DISABLED` EligibilityState: INACTIVE is a deliberate configuration choice, DISABLED can be set dynamically by the pipeline.

---

## Can Score

**Definition:** A boolean capability flag that is `True` when an instrument-timeframe combination is cleared for ML model scoring. Derived condition: `EligibilityState == ELIGIBLE AND TimeframeRole == FULL`. If either condition fails, `can_score = False`.

**Source of truth:** `src/candles/application/eligibility/evaluate.py`.

**Gotchas:**
- `can_score = True` is required for the instrument to appear in market selection output; instruments with `can_score = False` on all FULL timeframes are excluded from the ranked universe.
- `can_score` does not imply the model has been trained on this instrument — it only means the data is sufficient to run inference.
- An instrument that was previously `can_score = True` can lose this flag if a recent candle gap drops coverage below threshold.

---

## Can Compute Features

**Definition:** A boolean capability flag that is `True` when partial or full feature computation is permitted for an instrument-timeframe. Derived condition: `EligibilityState in {ELIGIBLE, INSUFFICIENT_HISTORY} AND TimeframeRole in {FULL, CONTEXT}`. Looser than `can_score` — allows feature computation to proceed even when history is not yet complete.

**Source of truth:** `src/candles/application/eligibility/evaluate.py`.

**Gotchas:**
- Features computed when `can_compute_features = True` but `can_score = False` (i.e., INSUFFICIENT_HISTORY state) may have NaN-heavy early rows — downstream consumers must handle this.
- Setting `can_compute_features = True` for INFORMATIONAL role timeframes is intentionally blocked — those timeframes do not participate in feature computation at all.
- This flag exists to avoid wasting compute on instruments that cannot ultimately be scored; it is an optimisation gate, not a quality guarantee.

---

<!-- Features Pipeline -->

## Confluence

**Definition:** The degree of agreement across multiple independent indicators or timeframes pointing to the same directional signal. In pklpo, confluence is used as a signal quality multiplier — a valid signal with high confluence (many confirming indicators) is weighted more heavily than one backed by a single indicator. High confluence reduces false positive rate.

**Source of truth:** `src/features/application/features_calc_short_service.py`; feature group outputs in `src/features/`.

**Gotchas:**
- Confluence is undefined when indicator outputs contain NaN — the agreement count collapses silently. Always check NaN propagation before computing confluence scores.
- High confluence can be spurious when indicators share inputs (e.g., two moving-average crossovers on the same MA length) — correlated indicators do not add independent confirmation.
- Confluence across timeframes requires explicit alignment; using raw daily and hourly values as if they are contemporaneous is a common look-ahead error.

---

## Features Pipeline

**Definition:** The end-to-end process that transforms raw OHLCV candle data into a rich set of engineered features (indicators, statistics, regime labels) stored in the `features_1h` database table. The pipeline is orchestrated by Airflow and executed by `features_calc_short_service`. Features are grouped and executed in a fixed order defined by `GroupRegistry`.

**Source of truth:** `src/features/application/features_calc_short_service.py`; `src/features/indicator_groups/registry.py`; DB table `features_1h`.

**Gotchas:**
- The pipeline is stateful — it reads the last stored timestamp per instrument and only computes forward-incremental updates. A corrupted last-timestamp leads to duplicate or missing rows.
- Feature group execution order matters: later groups (e.g., `statistics`) can depend on outputs from earlier groups (e.g., `ma`). Running groups out of order produces NaN cascades.
- Features are not recomputed retroactively by default; historical feature values are frozen at the time of original computation.

---

## GroupRegistry

**Definition:** The registry that defines the ordered set of feature groups to be executed during the features pipeline, along with their execution sequence. The execution order is: `overlap → ma → oscillators → volatility → volume → trend → squeeze → candles → statistics → performance`.

**Source of truth:** `src/features/indicator_groups/registry.py`.

**Gotchas:**
- Groups later in the order may depend on columns written by earlier groups within the same pipeline run — reordering groups without auditing dependencies will break feature computation silently.
- Adding a new group to `GroupRegistry` requires explicit placement in the execution order, not just registration.
- The `candles` group in the registry refers to candle-pattern features (e.g., doji, engulfing), not raw OHLCV columns.

---

## Valid Signal

**Definition:** A trading signal that passes all quality filters: non-NaN indicator values, passes the eligibility gate, has sufficient confluence, and falls within defined regime constraints. A valid signal is the final output of the features + market selection pipeline and represents a potential trade candidate.

**Source of truth:** `src/market_selection/application/pipeline.py`.

**Gotchas:**
- Validity is evaluated at signal generation time — a signal valid at T may be stale or invalid at T+1 if market conditions change before execution.
- A signal can be valid but not actionable if position limits, correlation constraints, or drawdown guards are active.
- The term "signal" in isolation (without "valid") refers to raw indicator output, which has not yet passed quality checks.

---

<!-- Market Selection & Regimes -->

## Global Regime

**Definition:** A macro-level classification of the overall market state (e.g., trending, ranging, volatile) derived from aggregated cross-instrument signals. `global_regime` is distinct from per-instrument regime — it reflects the dominant condition across the traded universe and is used to adjust selection thresholds and position sizing at portfolio level.

**Source of truth:** `src/market_selection/application/pipeline.py`.

**Gotchas:**
- `global_regime` is a derived aggregate; its latency is at least one pipeline cycle behind real-time market conditions.
- A RANGE global regime does not mean all instruments are ranging — it reflects the median/modal condition. Individual instruments can still trend.
- Changes in global regime should trigger a full re-evaluation of the universe, not just incremental updates.

---

## Market Selection

**Definition:** The pipeline stage that ranks all eligible instruments by composite score and selects the top N for active trading. Market selection consumes features and regime outputs, computes `PairMetrics` (vol_score, trend_q_score, noise_score, stability_score, liq_score), and produces a ranked list stored in `market_selection_results`.

**Source of truth:** `src/market_selection/application/pipeline.py`; DB table `market_selection_results`.

**Gotchas:**
- Market selection is downstream of the eligibility gate — only instruments with `can_score = True` are considered.
- The five `PairMetrics` scores are combined with weights; changing weight configuration without rerunning selection produces stale rankings.
- Market selection output is a snapshot at the time of pipeline execution; it does not update intraday.

---

## Percentile Rank

**Definition:** The rank of an instrument's score relative to all other instruments in the eligible universe, expressed as a percentile (0–100). `percentile_rank` is used in market selection to normalise scores across different market regimes and universe sizes, ensuring that relative positioning is stable even when absolute score values shift.

**Source of truth:** `src/market_selection/application/pipeline.py`.

**Gotchas:**
- Percentile rank is sensitive to `universe_size` — adding or removing instruments from the eligible pool changes the percentile of every other instrument without changing their absolute scores.
- A percentile rank of 100 means highest-scoring in the current universe, not that the score is objectively good — in a weak universe, a poor instrument can rank at the 100th percentile.
- Do not compare percentile ranks across different pipeline runs without checking that universe composition has not changed significantly.

---

## Regime

**Definition:** A classification of the prevailing market condition for a single instrument, used to apply context-appropriate indicator settings and signal filters. The `Regime` enum values are: `TREND_UP`, `TREND_DOWN`, `RANGE`, `VOLATILE`. Classification thresholds: ADX > 25 classifies a trend regime; ADX < 18 classifies a range regime; elevated realised volatility triggers `VOLATILE`.

**Source of truth:** `src/market_selection/` (regime classification module).

**Gotchas:**
- ADX thresholds (25/18) are hysteresis boundaries — the regime does not flip on every bar that crosses the threshold; confirm whether hysteresis is implemented before assuming smooth transitions.
- `VOLATILE` can occur simultaneously with `TREND_UP` or `TREND_DOWN`; the enum represents a single label, so the volatility condition overrides trend classification when both are present.
- Regime misclassification at trend/range boundaries is common (ADX 20–25 zone); signals generated in this zone have higher false positive rates.

---

<!-- NaN Semantics -->

## NaN Propagation

**Definition:** The behaviour by which a NaN (Not a Number) value in one calculation step flows into all downstream calculations that depend on it. In pandas and numpy, arithmetic operations involving NaN return NaN, causing NaN to spread through derived columns unless explicitly handled. In pklpo, NaN propagation can silently invalidate entire feature rows.

**Source of truth:** `src/features/` (all indicator implementations); pandas default behaviour.

**Gotchas:**
- NaN propagation is asymmetric with respect to the `GroupRegistry` execution order — a NaN in an early group (e.g., `ma`) can corrupt all subsequent groups (e.g., `statistics`) in the same run.
- Filling NaN with zero (`.fillna(0)`) is semantically incorrect for price-derived features — it implies a zero return or zero indicator value, which is typically wrong.
- The correct response to a NaN in a required input is usually to propagate it further (preserve NaN) and let the eligibility gate or validity check exclude the row.

---

## NaN Semantics

**Definition:** The set of rules governing how NaN values are produced, propagated, and handled throughout the pklpo pipeline. Key semantics: (1) NaN in OHLCV candles signals a missing bar. (2) NaN in a feature column signals an insufficient lookback window. (3) NaN in eligibility or score outputs signals that evaluation was not possible. NaN must be treated as "unknown", not as zero or as a valid value.

**Source of truth:** `src/candles/domain/`; `src/features/application/features_calc_short_service.py`.

**Gotchas:**
- Pandas boolean indexing on NaN-containing columns silently drops rows — use `.notna()` checks explicitly when filtering.
- `coverage_pct` calculation must not count NaN bars as present — verify the counting logic counts non-null rows, not all rows.
- JSON serialisation of NaN typically produces `null` or raises an error depending on the serialiser — always sanitise NaN before API responses or DB writes that use JSON columns.
