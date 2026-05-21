"""CLI entry point — ``python -m quorum_backend.eval`` prints a scorecard.

Designed for ad-hoc development runs. CI exercises the harness via the
test suite (``backend/tests/test_eval.py``), which fails on regressions.
"""

from __future__ import annotations

import asyncio
import sys

from quorum_backend.eval import run_suite
from quorum_backend.llm import init_llm


def main() -> int:
    init_llm()
    results = asyncio.run(run_suite())

    print("\n=== Quorum eval scorecard ===")
    passed = 0
    for r in results:
        print(r.score)
        if r.score.notes:
            for note in r.score.notes:
                print(f"   - {note}")
        if r.score.passed:
            passed += 1

    total = len(results)
    print(f"\n{passed}/{total} cases passed.")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
