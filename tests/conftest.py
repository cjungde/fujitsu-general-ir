"""Test bootstrap.

Makes the integration package importable and provides a minimal stub for
``infrared_protocols.commands.Command`` when the real package (shipped with the
Home Assistant ``infrared`` integration) is not installed, so the codec unit
tests can run standalone.
"""

from __future__ import annotations

import abc
import sys
import types
from pathlib import Path

sys.path.insert(
    0,
    str(
        Path(__file__).resolve().parents[1] / "custom_components" / "fujitsu_general_ir"
    ),
)

try:  # prefer the real library when available (CI installs it)
    import infrared_protocols.commands  # noqa: F401
except ImportError:
    _pkg = types.ModuleType("infrared_protocols")
    _cmds = types.ModuleType("infrared_protocols.commands")

    class Command(abc.ABC):
        """Minimal stand-in matching infrared_protocols.commands.Command."""

        def __init__(self, *, modulation: int, repeat_count: int = 0) -> None:
            self.modulation = modulation
            self.repeat_count = repeat_count

        @abc.abstractmethod
        def get_raw_timings(self) -> list[int]: ...

    _cmds.Command = Command
    _pkg.commands = _cmds
    sys.modules["infrared_protocols"] = _pkg
    sys.modules["infrared_protocols.commands"] = _cmds
