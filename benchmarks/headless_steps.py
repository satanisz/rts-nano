"""Runnable headless throughput benchmark.

Usage:
    python benchmarks/headless_steps.py [steps]

Reports single-instance headless steps/sec on the default map without opening a
window. The reusable logic lives in ``rts_nano.benchmark`` so tests and other
tools can import it; this script is just a thin CLI entry point.
"""

from __future__ import annotations

import sys

from rts_nano.benchmark import measure_steps_per_second


def main() -> None:
    """Run the benchmark with an optional step count argument."""
    steps = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    result = measure_steps_per_second(steps=steps)
    print(f"steps={result.steps} elapsed={result.elapsed_seconds:.3f}s steps_per_second={result.steps_per_second:.0f}")


if __name__ == "__main__":
    main()
