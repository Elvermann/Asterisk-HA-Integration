"""Constants for the Asterisk Line Monitor integration."""

DOMAIN = "asterisk_line_monitor"
CONF_HOST = "host"
CONF_PORT = "port"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SHOW_CALL_DETAILS = "show_call_details"
DEFAULT_PORT = 5038
DEFAULT_SHOW_CALL_DETAILS = True

PLATFORMS = ["binary_sensor", "sensor"]

# Inbound provider endpoint. Outbound lines are discovered from AMI registration details.
INBOUND_ENDPOINT = "epcan-in"

# Display names for the endpoints present in the current Asterisk configuration.
KNOWN_CLIENTS = {
    "1001": "Gigaset 1001",
    "1002": "Android 1002",
    "1003": "MOBOTIX M26",
}
