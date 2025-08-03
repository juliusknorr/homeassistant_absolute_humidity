"""Constants for the Absolute Humidity integration."""

DOMAIN = "absolute_humidity"

# Dispatcher signals
SIGNAL_ADD_SENSOR = "absolute_humidity_add_sensor"
SIGNAL_ADD_WINDOW_SENSOR = "absolute_humidity_add_window_sensor"

# Window recommendation states
WINDOW_STATE_TOO_WET = "too wet"
WINDOW_STATE_TOO_WARM = "too warm"
WINDOW_STATE_OK_TO_OPEN = "ok to open"
WINDOW_STATE_OPENING_RECOMMENDED = "opening recommended"

# Default offsets for window recommendation logic
DEFAULT_TEMPERATURE_OFFSET = 3.0  # °C difference required for "too warm" state
DEFAULT_ABSOLUTE_HUMIDITY_OFFSET = 0.5  # g/m³ difference required for "too wet" state
DEFAULT_ABSOLUTE_HUMIDITY_WARNING_LEVEL = 12.0  # g/m³ warning level for "opening recommended" state