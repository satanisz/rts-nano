"""Generate a dependency-free SVG preview of a v2 or v3 map."""

from __future__ import annotations

import sys
from argparse import ArgumentParser
from pathlib import Path

from rts_nano.map_schema import load_map_settings
from rts_nano.map_tools import render_map_svg


def main() -> None:
    """Render one map to SVG and report the generated path."""
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("map", type=Path)
    parser.add_argument("--output", type=Path, help="Output path; defaults to <name>.svg")
    args = parser.parse_args()
    output = args.output or args.map.with_suffix(".svg")
    settings = load_map_settings(args.map)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_map_svg(settings, title=args.map.stem), encoding="utf-8")
    sys.stdout.write(f"{output}\n")


if __name__ == "__main__":
    main()
