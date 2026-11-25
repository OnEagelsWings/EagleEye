"""Schema compatibility for retained historical services in current builds."""

from eagleeye_pro.version import BUILD, SCHEMA_VERSION, historical_schema_compatible


def test_current_runtime_supports_historical_service_without_fake_schema_bump():
    # Keep the regression valid as the application build advances after 490.
    assert historical_schema_compatible(BUILD, SCHEMA_VERSION, "420.0")
    assert historical_schema_compatible(BUILD, SCHEMA_VERSION, "425.0")


def test_schema_and_runtime_version_boundaries_fail_closed():
    assert not historical_schema_compatible("490.0", "419.0", "420.0")
    assert not historical_schema_compatible("490.0", "491.0", "420.0")
    assert not historical_schema_compatible("419.0", "420.0", "420.0")
    assert not historical_schema_compatible("490.0", "485.0", "490.0")
    assert not historical_schema_compatible("garbled", "485.0", "420.0")
    assert not historical_schema_compatible("490.0", "unknown", "420.0")
