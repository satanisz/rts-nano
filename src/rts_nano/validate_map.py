"""Command-line validator for RTS Nano map JSON files."""

from __future__ import annotations

import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path

from rts_nano.map_schema import validate_map_settings


def _write_line(message: str) -> None:
    """Write one CLI output line without coupling validation to print."""
    sys.stdout.write(f"{message}\n")


def _parse_args() -> Namespace:
    """Parse validator CLI arguments."""
    parser = ArgumentParser(description="Validate RTS Nano map JSON files.")
    parser.add_argument("maps", nargs="+", type=Path, help="Map JSON files to validate.")
    return parser.parse_args()


def validate_map_file(path: Path) -> list[str]:
    """Return validation errors for one map file."""
    import json

    try:
        with path.open(encoding="utf-8") as map_file:
            payload = json.load(map_file)
    except OSError as exc:
        return [f"Could not read file: {exc}"]
    except json.JSONDecodeError as exc:
        return [f"Invalid JSON: {exc}"]
    return validate_map_settings(payload)


def main() -> None:
    """Validate one or more map files and exit non-zero on failures."""
    args = _parse_args()
    failed = False
    for path in args.maps:
        errors = validate_map_file(path)
        if errors:
            failed = True
            _write_line(f"{path}: invalid")
            for error in errors:
                _write_line(f"  - {error}")
        else:
            _write_line(f"{path}: ok")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
