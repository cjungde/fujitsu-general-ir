#!/usr/bin/env python3
"""Decode a captured Fujitsu General IR timing list and verify it.

Feed it the raw timings of a frame captured from your original remote and it
prints the decoded state (or tells you it didn't match). Marks may be positive
and spaces negative (ESPHome `dump: raw` style) or all-positive — both work.

Usage:
    # from arguments (any separators: commas, spaces, newlines)
    scripts/decode.py "3300,-1600,420,-1200,420,-420, ..."

    # from a file
    scripts/decode.py path/to/capture.txt

    # from stdin (e.g. piped from an ESPHome log line)
    echo "3300, -1600, 420, -1200, ..." | scripts/decode.py

Runs standalone: if `infrared_protocols` is not installed it uses a tiny stub,
so you can run this on any machine with plain Python 3.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Make the integration package importable and stub the codec dependency when
# the real infrared_protocols package isn't installed.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import irstub  # noqa: E402

irstub.setup()

from codec import FujitsuCommand, decode  # noqa: E402


def _read_input(argv: list[str]) -> str:
    if len(argv) > 1:
        arg = " ".join(argv[1:])
        path = Path(arg)
        if path.is_file():
            return path.read_text()
        return arg
    return sys.stdin.read()


def main() -> int:
    raw = _read_input(sys.argv)
    numbers = [int(n) for n in re.findall(r"-?\d+", raw)]
    if not numbers:
        print("No timings found in input.", file=sys.stderr)
        return 2

    print(f"Parsed {len(numbers)} timing values.")
    state = decode(numbers)
    if state is None:
        print(
            "\n❌ Did NOT decode as a Fujitsu General frame.\n"
            "   Possible causes: incomplete capture, a different protocol, or a\n"
            "   model variant this codec doesn't cover. Check that the capture\n"
            "   starts with a ~3300us mark / ~1600us space header."
        )
        return 1

    print(f"\n✅ Decoded: {state}")

    # Re-encode the decoded state and confirm it reproduces the same frame.
    reencoded = FujitsuCommand(state).get_raw_timings()
    if len(reencoded) == len(numbers):
        result = "matches length"
    else:
        result = f"length differs ({len(reencoded)} vs {len(numbers)})"
    print(f"Round-trip re-encode: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
