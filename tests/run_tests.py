"""Minimal pytest-free test runner (offline-safe)."""

from __future__ import annotations

import importlib
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

MODULE = importlib.import_module("test_smoke")

def main() -> int:
    tests = sorted((name, fn) for name, fn in vars(MODULE).items()
                   if name.startswith("test_") and callable(fn))
    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
            print(f"PASS  {name}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL  {name}: {exc}")
            traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed, {len(tests)} total")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())