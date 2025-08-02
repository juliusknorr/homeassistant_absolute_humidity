"""Services for the Absolute Humidity integration."""
import logging
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, SIGNAL_ADD_SENSOR

_LOGGER = logging.getLogger(__name__)

async def async_setup_services(hass: HomeAssistant):
    """Set up services for the Absolute Humidity integration."""
    
    async def async_add_sensor_service(call: ServiceCall):
        """Service to manually add an absolute humidity sensor."""
        humidity_entity_id = call.data.get("humidity_entity_id")
        temperature_entity_id = call.data.get("temperature_entity_id")
        
        if not humidity_entity_id or not temperature_entity_id:
            _LOGGER.error("Both humidity_entity_id and temperature_entity_id are required")
            return
        
        # Validate entities exist
        if not hass.states.get(humidity_entity_id):
            _LOGGER.error(f"Humidity entity {humidity_entity_id} does not exist")
            return
            
        if not hass.states.get(temperature_entity_id):
            _LOGGER.error(f"Temperature entity {temperature_entity_id} does not exist")
            return
        
        # Send signal to add sensor
        async_dispatcher_send(hass, SIGNAL_ADD_SENSOR, humidity_entity_id, temperature_entity_id)
        _LOGGER.info(f"Manually triggered creation of absolute humidity sensor for {humidity_entity_id}")
    
    async def async_rediscover_service(call: ServiceCall):
        """Service to trigger rediscovery of all sensors."""
        discovery = hass.data.get("absolute_humidity_discovery")
        if discovery:
            await discovery._discover_existing_entities()
            _LOGGER.info("Triggered rediscovery of absolute humidity sensors")
        else:
            _LOGGER.error("Discovery system not initialized")
    
    # Register services
    hass.services.async_register(
        DOMAIN,
        "add_sensor",
        async_add_sensor_service,
        schema=vol.Schema({
            vol.Required("humidity_entity_id"): str,
            vol.Required("temperature_entity_id"): str,
        })
    )
    
    hass.services.async_register(
        DOMAIN,
        "rediscover",
        async_rediscover_service,
        schema=vol.Schema({})
    )
    
    _LOGGER.info("Absolute Humidity services registered")

async def async_unload_services(hass: HomeAssistant):
    """Unload services for the Absolute Humidity integration."""
    hass.services.async_remove(DOMAIN, "add_sensor")
    hass.services.async_remove(DOMAIN, "rediscover")
    _LOGGER.info("Absolute Humidity services unloaded")
