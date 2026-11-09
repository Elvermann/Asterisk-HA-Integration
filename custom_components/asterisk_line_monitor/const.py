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

# The provider line sensor entity names are intentionally only the phone numbers.
LINE_DEFINITIONS = {
    "1820": {"endpoint": "epcan-3"},
    "9092255": {"endpoint": "epcan-1"},
    "9092256": {"endpoint": "epcan-2"},
}
INBOUND_ENDPOINT = "epcan-in"
PROVIDER_ENDPOINTS = {item["endpoint"] for item in LINE_DEFINITIONS.values()}

# Display names for the endpoints present in the current Asterisk configuration.
KNOWN_CLIENTS = {
    "1001": "Gigaset 1001",
    "1002": "Android 1002",
    "1003": "MOBOTIX M26",
}
