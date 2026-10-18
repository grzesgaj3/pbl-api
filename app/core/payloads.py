"""On-air (LoRa) payload formatting.

Keeping the wire format in a single function means the bridge never has to
know how to build it and the format can be changed in one place.
"""

from __future__ import annotations


def build_command_payload(sensor_id: str, command_type: str = "clean") -> str:
    """Return the LoRa command string, e.g. ``sensor1;clean;``."""
    return f"{sensor_id};{command_type};"
