"""Shared dev/test helper.

Ensures ``infrared_protocols.commands.Command`` is importable so the codec can
be exercised without Home Assistant (which ships the real library). Used by the
test suite (``tests/conftest.py``) and the standalone ``scripts/decode.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_PKG = _ROOT / "custom_components" / "fujitsu_general_ir"


def setup() -> None:
    """Add the integration package to the path and stub the codec dependency."""
    if str(_PKG) not in sys.path:
        sys.path.insert(0, str(_PKG))

    try:  # prefer the real library when available
        import infrared_protocols.commands  # noqa: F401

        return
    except ImportError:
        pass

    import abc
    import types

    pkg = types.ModuleType("infrared_protocols")
    cmds = types.ModuleType("infrared_protocols.commands")

    class Command(abc.ABC):
        """Minimal stand-in matching infrared_protocols.commands.Command."""

        def __init__(self, *, modulation: int, repeat_count: int = 0) -> None:
            self.modulation = modulation
            self.repeat_count = repeat_count

        @abc.abstractmethod
        def get_raw_timings(self) -> list[int]: ...

    cmds.Command = Command
    pkg.commands = cmds
    sys.modules["infrared_protocols"] = pkg
    sys.modules["infrared_protocols.commands"] = cmds
