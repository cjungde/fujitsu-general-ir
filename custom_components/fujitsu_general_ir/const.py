"""Constants for the Fujitsu General IR integration."""

DOMAIN = "fujitsu_general_ir"

CONF_EMITTER_ENTITY_ID = "emitter_entity_id"
CONF_RECEIVER_ENTITY_ID = "receiver_entity_id"

# Optional power meter that the AC is plugged into. When configured, its draw
# is used to detect on/off (the one thing IR can't read back): at or above the
# threshold the AC is treated as on, below it as off. It cannot recover any
# other setting (mode, temperature, fan); on an off->on transition the last
# active HVAC mode is assumed.
CONF_POWER_SENSOR_ENTITY_ID = "power_sensor_entity_id"
CONF_POWER_ON_THRESHOLD = "power_on_threshold"
DEFAULT_POWER_ON_THRESHOLD = 20.0  # watts; above standby, below fan-only draw
# After we transmit, the AC's draw is transitional (compressor spinning down or
# ramping up); trust the commanded state and ignore power-derived flips for a
# short grace period so a just-sent command isn't immediately reverted.
POWER_SYNC_GRACE = 60.0  # seconds

# Resilience to a proxy that briefly leaves the LAN: instead of dropping the
# command, wait for the emitter entity to come back, then retry the send a few
# times with exponential backoff before giving up.
EMITTER_WAIT_TIMEOUT = 15.0  # seconds to wait for the emitter to (re)appear
SEND_RETRIES = 3
SEND_RETRY_BACKOFF = 0.5  # seconds, doubled after each failed attempt
