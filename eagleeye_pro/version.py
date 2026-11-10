BUILD = "500.0"
SCHEMA_VERSION = "485.0"
BUILD_NAME = "EagleEye Intelligence Platform – Build 500 Internal Release Candidate"

def historical_schema_compatible(runtime_build: str, schema_version: str, required_build: str) -> bool:
    """Historical service is usable when the installed schema supports it.

    Later application builds do not require a schema version bump for every
    release. However, the schema must not predate the historical service
    contract, and a newer schema than the executing runtime is not accepted.
    This is not a release-readiness or permission grant.
    """
    try:
        runtime_major = int(str(runtime_build).split(".", 1)[0])
        schema_major = int(str(schema_version).split(".", 1)[0])
        required_major = int(str(required_build).split(".", 1)[0])
    except (TypeError, ValueError):
        return False
    return required_major <= schema_major <= runtime_major
