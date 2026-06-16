import platform


def test_platform_import_resolves_to_stdlib_for_pandas() -> None:
    import pandas

    assert pandas is not None
    assert hasattr(platform, "python_implementation")
    assert "src\\platform" not in str(getattr(platform, "__file__", ""))
