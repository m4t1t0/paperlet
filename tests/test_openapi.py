"""OpenAPI spec freshness: docs/openapi.yaml must match the generator."""
from __future__ import annotations

from pathlib import Path


def test_openapi_yaml_is_current() -> None:
    from backend.src.shared.openapi import build_openapi_spec, render_openapi_yaml

    spec = build_openapi_spec()
    assert spec["openapi"].startswith("3.0.")
    assert len(spec["paths"]) > 0
    for path, item in spec["paths"].items():
        assert "<" not in path and ">" not in path, f"unconverted Flask param: {path}"
        for method, operation in item.items():
            assert operation.get("responses"), f"no responses: {method} {path}"

    root = Path(__file__).resolve().parent.parent
    committed = (root / "docs" / "openapi.yaml").read_text()
    assert committed == render_openapi_yaml(spec), (
        "openapi.yaml is stale — run `invoke openapi` to regenerate."
    )
