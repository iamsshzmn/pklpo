"""Legacy audit compatibility module."""


def run_audit() -> dict[str, object]:
    return {"status": "ok"}


__all__ = ["run_audit"]
