"""Test bootstrap.

Makes the integration package importable and stubs ``infrared_protocols`` when
the real package (shipped with the HA ``infrared`` integration) is not
installed, so the codec/mapping unit tests run standalone.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import irstub  # noqa: E402

irstub.setup()
