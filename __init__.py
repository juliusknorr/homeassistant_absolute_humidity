"""Absolute Humidity integration for Home Assistant."""
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
import logging
import voluptuous as vol

from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

DOMAIN = "absolute_humidity"

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Absolute Humidity component."""
    _LOGGER.info("Setting up Absolute Humidity integration")
    
    # Set up services
    await async_setup_services(hass)
    
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Absolute Humidity from a config entry."""
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    # Clean up discovery system if it exists
    discovery = hass.data.get("absolute_humidity_discovery")
    if discovery:
        await discovery.async_remove()
        hass.data.pop("absolute_humidity_discovery", None)
    
    # Unload services
    await async_unload_services(hass)
    
    return True
