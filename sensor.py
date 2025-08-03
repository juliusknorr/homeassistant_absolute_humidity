"""Sensor platform setup for Absolute Humidity integration."""
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers import config_validation as cv
from homeassistant.const import CONF_PLATFORM
import voluptuous as vol
import logging

from .const import SIGNAL_ADD_SENSOR, SIGNAL_ADD_WINDOW_SENSOR
from .discovery import AbsoluteHumidityDiscovery

_LOGGER = logging.getLogger(__name__)

# Configuration schema for the platform
PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): "absolute_humidity",
    vol.Optional("outdoor_temperature_sensor"): cv.entity_id,
    vol.Optional("outdoor_humidity_sensor"): cv.entity_id,
    vol.Optional("temperature_offset", default=3.0): vol.Coerce(float),
    vol.Optional("absolute_humidity_offset", default=0.5): vol.Coerce(float),
    vol.Optional("absolute_humidity_warning_level", default=12.0): vol.Coerce(float),
}, extra=vol.ALLOW_EXTRA)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the absolute humidity platform with dynamic discovery."""
    _LOGGER.debug("Setting up absolute humidity platform with dynamic discovery")
    _LOGGER.debug(f"Platform config: {config}")
    
    # Create and set up the discovery system with configuration
    discovery = AbsoluteHumidityDiscovery(hass, async_add_entities, config)
    await discovery.async_setup()
    
    # Store the discovery instance for potential cleanup
    hass.data.setdefault("absolute_humidity_discovery", discovery)


async def async_discover(hass, humidity_entity_id, temperature_entity_id):
    """Manually trigger discovery of a specific sensor pair."""
    async_dispatcher_send(hass, SIGNAL_ADD_SENSOR, humidity_entity_id, temperature_entity_id)


async def async_discover_window_sensor(hass, indoor_humidity_entity_id, indoor_temp_entity_id,
                                     outdoor_humidity_entity_id, outdoor_temp_entity_id):
    """Manually trigger discovery of a specific window recommendation sensor."""
    async_dispatcher_send(
        hass, 
        SIGNAL_ADD_WINDOW_SENSOR, 
        indoor_humidity_entity_id,
        indoor_temp_entity_id,
        outdoor_humidity_entity_id,
        outdoor_temp_entity_id
    )
