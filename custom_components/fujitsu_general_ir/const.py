"""Constants for the Fujitsu General IR integration."""

DOMAIN = "fujitsu_general_ir"

CONF_EMITTER_ENTITY_ID = "emitter_entity_id"
CONF_RECEIVER_ENTITY_ID = "receiver_entity_id"

# Resilience to a proxy that briefly leaves the LAN: instead of dropping the
# command, wait for the emitter entity to come back, then retry the send a few
# times with exponential backoff before giving up.
EMITTER_WAIT_TIMEOUT = 15.0  # seconds to wait for the emitter to (re)appear
SEND_RETRIES = 3
SEND_RETRY_BACKOFF = 0.5  # seconds, doubled after each failed attempt
