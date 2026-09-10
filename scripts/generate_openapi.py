"""Generate (or verify) openapi.yaml from the Flask app + route metadata.

Usage:
    python scripts/generate_openapi.py            # rewrite openapi.yaml
    python scripts/generate_openapi.py --check    # fail if openapi.yaml is stale
    python scripts/generate_openapi.py -o PATH    # write elsewhere
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.src.shared.openapi import build_openapi_spec, render_openapi_yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "openapi.yaml"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if the committed spec differs (no write)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="output path (default: openapi.yaml)",
    )
    args = parser.parse_args()

    rendered = render_openapi_yaml(build_openapi_spec())
    if args.check:
        if not args.output.exists() or args.output.read_text() != rendered:
            print(f"{args.output} is stale — run `invoke openapi` to regenerate.")
            return 1
        print(f"{args.output} is current.")
        return 0
    args.output.write_text(rendered)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
