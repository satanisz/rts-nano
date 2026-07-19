"""Compile semantic MapSpec v3 JSON into canonical runtime v2 JSON."""

from __future__ import annotations

import json
import sys
from argparse import ArgumentParser
from pathlib import Path

from rts_nano.map_spec import compile_map_spec


def main() -> None:
    """Compile one MapSpec file and report the generated path."""
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("map", type=Path, help="MapSpec v3 JSON file")
    parser.add_argument("--output", type=Path, help="Output path; defaults to <name>.compiled.json")
    args = parser.parse_args()
    payload = json.loads(args.map.read_text(encoding="utf-8"))
    compiled = compile_map_spec(payload)
    output = args.output or args.map.with_suffix(".compiled.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(compiled, indent=4) + "\n", encoding="utf-8")
    sys.stdout.write(f"{output}\n")


if __name__ == "__main__":
    main()
