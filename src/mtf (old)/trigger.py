from __future__ import annotations

try:
    import joblib  # type: ignore
except Exception:  # pragma: no cover
    joblib = None


MODEL_PATH = "data/model_trigger.pkl"


def load_trigger_model():
    if joblib is None:
        return None
    try:
        return joblib.load(MODEL_PATH)
    except Exception:
        return None


def evaluate_trigger_probabilities(
    features_15m: dict | None, features_5m: dict | None
) -> tuple[float, float]:
    """Return (p_reversal_up, p_reversal_down).

    If XGBoost model is available, use it; otherwise, fallback to a neutral 0.5/0.5
    so that consensus logic remains deterministic during development.
    """
    model = load_trigger_model()
    if model is None:
        return 0.5, 0.5
    try:
        # Placeholder: construct a feature vector from provided dicts.
        # Extend with real features when available.
        x = []
        for src in (features_15m or {}).values():
            if isinstance(src, int | float):
                x.append(float(src))
        for src in (features_5m or {}).values():
            if isinstance(src, int | float):
                x.append(float(src))
        proba = model.predict_proba([x])[0]
        # Assume order: [down, flat, up] or similar; adjust mapping as needed
        if len(proba) == 2:
            p_down, p_up = float(proba[0]), float(proba[1])
            return p_up, p_down
        if len(proba) >= 3:
            p_down = float(proba[0])
            p_up = float(proba[-1])
            return p_up, p_down
    except Exception:
        pass
    return 0.5, 0.5
