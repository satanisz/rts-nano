"""Print an LLM-readable strategic summary of a v2 or v3 map."""

from __future__ import annotations

import sys
from argparse import ArgumentParser
from pathlib import Path

from rts_nano.map_tools import inspect_map_file


def main() -> None:
    """Inspect one or more maps and write their reports to stdout."""
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("maps", nargs="+", type=Path)
    args = parser.parse_args()
    reports = [inspect_map_file(path) for path in args.maps]
    sys.stdout.write("\n\n".join(reports) + "\n")


if __name__ == "__main__":
    main()
