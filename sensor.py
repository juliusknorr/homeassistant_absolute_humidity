from homeassistant.helpers.entity import Entity
from homeassistant.const import UnitOfTemperature, EVENT_STATE_CHANGED
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.core import callback, Event
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
import math
import logging

from .const import SIGNAL_ADD_SENSOR

_LOGGER = logging.getLogger(__name__)

class AbsoluteHumidityDiscovery:
    """Handles dynamic discovery of humidity/temperature sensor pairs."""
    
    def __init__(self, hass, async_add_entities):
        self._hass = hass
        self._async_add_entities = async_add_entities
        self._created_sensors = set()
        self._unsub_dispatcher = None
        self._unsub_state_listener = None
    
    async def async_setup(self):
        """Set up the discovery system."""
        # Initial discovery of existing entities
        await self._discover_existing_entities()
        
        # Set up dispatcher for manual sensor addition
        self._unsub_dispatcher = async_dispatcher_connect(
            self._hass, SIGNAL_ADD_SENSOR, self._async_add_sensor
        )
        
        # Listen for state changes to detect new entities
        self._unsub_state_listener = self._hass.bus.async_listen(
            EVENT_STATE_CHANGED, self._async_state_changed_listener
        )
        
        _LOGGER.info("Absolute humidity discovery system initialized")
    
    async def async_remove(self):
        """Clean up the discovery system."""
        if self._unsub_dispatcher:
            self._unsub_dispatcher()
        if self._unsub_state_listener:
            self._unsub_state_listener()
    
    async def _discover_existing_entities(self):
        """Discover existing humidity/temperature sensor pairs."""
        sensors = []
        
        for entity_id in self._hass.states.async_entity_ids('sensor'):
            state = self._hass.states.get(entity_id)
            _LOGGER.debug(f"Checking entity {entity_id} with state {state}")
            if state is None:
                continue
            if state.attributes.get('device_class') == 'humidity':
                sensor = await self._try_create_sensor(entity_id)
                if sensor:
                    sensors.append(sensor)
        
        if sensors:
            _LOGGER.info(f"Discovered {len(sensors)} existing absolute humidity sensors")
            self._async_add_entities(sensors, True)
    
    @callback
    def _async_state_changed_listener(self, event: Event):
        """Listen for state changes that might indicate new entities."""
        entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")
        
        if not entity_id or not new_state:
            return
        
        # Only process sensor entities with humidity device class
        if (entity_id.startswith("sensor.") and 
            new_state.attributes.get('device_class') == 'humidity'):
            # Schedule sensor creation (can't await in callback)
            self._hass.async_create_task(self._async_handle_new_humidity_entity(entity_id))
    
    async def _async_handle_new_humidity_entity(self, humidity_entity_id):
        """Handle discovery of a new humidity entity."""
        if humidity_entity_id in self._created_sensors:
            return
        
        sensor = await self._try_create_sensor(humidity_entity_id)
        if sensor:
            _LOGGER.info(f"Dynamically discovered new absolute humidity sensor: {sensor.name}")
            self._async_add_entities([sensor], True)
    
    async def _try_create_sensor(self, humidity_entity_id):
        """Try to create an absolute humidity sensor for the given humidity entity."""
        if humidity_entity_id in self._created_sensors:
            return None
        
        temp_entity_id = self._find_matching_temperature_sensor(humidity_entity_id)
        if temp_entity_id:
            temp_state = self._hass.states.get(temp_entity_id)
            if temp_state and temp_state.attributes.get('device_class') == 'temperature':
                _LOGGER.debug(f"Creating absolute humidity sensor for humidity: {humidity_entity_id}, temperature: {temp_entity_id}")
                self._created_sensors.add(humidity_entity_id)
                return AbsoluteHumiditySensor(self._hass, humidity_entity_id, temp_entity_id)
        
        _LOGGER.debug(f"No matching temperature sensor found for humidity sensor: {humidity_entity_id}")
        return None
    
    def _find_matching_temperature_sensor(self, humidity_entity_id):
        """Find a matching temperature sensor for the given humidity sensor using various patterns."""
        patterns = [
            # Pattern 1: replace '_humidity' with '_temperature'
            humidity_entity_id.replace('_humidity', '_temperature'),
            # Pattern 2: replace 'humidity' with 'temperature' anywhere
            humidity_entity_id.replace('humidity', 'temperature'),
            # Pattern 3: same base name + '_temp' instead of '_humidity'
            humidity_entity_id.replace('_humidity', '_temp'),
            # Pattern 4: same base name + '_temperature' (removing last part)
            f"{humidity_entity_id.rsplit('_', 1)[0]}_temperature",
            # Pattern 5: same base name + '_temp' (removing last part)
            f"{humidity_entity_id.rsplit('_', 1)[0]}_temp",
        ]
        
        for temp_entity_id in patterns:
            if temp_entity_id != humidity_entity_id and self._hass.states.get(temp_entity_id):
                _LOGGER.debug(f"Found potential temperature sensor {temp_entity_id} for humidity sensor {humidity_entity_id}")
                return temp_entity_id
        
        return None
    
    @callback
    def _async_add_sensor(self, humidity_entity_id, temperature_entity_id):
        """Add a sensor via dispatcher signal."""
        if humidity_entity_id not in self._created_sensors:
            self._created_sensors.add(humidity_entity_id)
            sensor = AbsoluteHumiditySensor(self._hass, humidity_entity_id, temperature_entity_id)
            self._async_add_entities([sensor], True)
            _LOGGER.info(f"Manually added absolute humidity sensor: {sensor.name}")

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the absolute humidity platform with dynamic discovery."""
    _LOGGER.debug("Setting up absolute humidity platform with dynamic discovery")
    
    # Create and set up the discovery system
    discovery = AbsoluteHumidityDiscovery(hass, async_add_entities)
    await discovery.async_setup()
    
    # Store the discovery instance for potential cleanup
    hass.data.setdefault("absolute_humidity_discovery", discovery)

async def async_discover(hass, humidity_entity_id, temperature_entity_id):
    """Manually trigger discovery of a specific sensor pair."""
    async_dispatcher_send(hass, SIGNAL_ADD_SENSOR, humidity_entity_id, temperature_entity_id)

class AbsoluteHumiditySensor(Entity):
    """Representation of an Absolute Humidity sensor."""
    
    def __init__(self, hass, humidity_entity_id, temperature_entity_id):
        self._hass = hass
        self._humidity_entity_id = humidity_entity_id
        self._temperature_entity_id = temperature_entity_id
        self._state = None
        
        # Create a more user-friendly name
        humidity_name = hass.states.get(humidity_entity_id).attributes.get('friendly_name', humidity_entity_id)
        self._name = f"Absolute Humidity {humidity_name.replace('Humidity', '').strip()}"
        self._unique_id = f"absolute_humidity_{humidity_entity_id}"
        
        _LOGGER.debug(f"Initialized AbsoluteHumiditySensor with humidity: {humidity_entity_id}, temperature: {temperature_entity_id}")

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name
    
    @property
    def unique_id(self):
        """Return a unique ID for this sensor."""
        return self._unique_id

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "g/m³"
    
    @property
    def device_class(self):
        """Return the device class."""
        return "humidity"
    
    @property
    def state_class(self):
        """Return the state class."""
        return "measurement"
    
    @property
    def icon(self):
        """Return the icon for the sensor."""
        return "mdi:water-percent"
    
    @property
    def extra_state_attributes(self):
        """Return additional state attributes."""
        return {
            "source_humidity": self._humidity_entity_id,
            "source_temperature": self._temperature_entity_id,
        }
    
    @property
    def available(self):
        """Return True if entity is available."""
        humidity_state = self._hass.states.get(self._humidity_entity_id)
        temperature_state = self._hass.states.get(self._temperature_entity_id)
        return (humidity_state is not None and 
                temperature_state is not None and
                humidity_state.state not in ['unknown', 'unavailable'] and
                temperature_state.state not in ['unknown', 'unavailable'])

    async def async_update(self):
        """Update the sensor state."""
        _LOGGER.debug(f"Updating absolute humidity sensor {self._name}")
        humidity = self._hass.states.get(self._humidity_entity_id)
        temperature = self._hass.states.get(self._temperature_entity_id)

        if humidity is None:
            _LOGGER.warning(f"Humidity entity {self._humidity_entity_id} state is None")
            return
        
        if temperature is None:
            _LOGGER.warning(f"Temperature entity {self._temperature_entity_id} state is None")
            return
        
        # Check if states are valid
        if humidity.state in ['unknown', 'unavailable']:
            _LOGGER.debug(f"Humidity entity {self._humidity_entity_id} is {humidity.state}")
            return
            
        if temperature.state in ['unknown', 'unavailable']:
            _LOGGER.debug(f"Temperature entity {self._temperature_entity_id} is {temperature.state}")
            return

        try:
            rh = float(humidity.state)
            temp_c = float(temperature.state)
            
            # Validate ranges
            if not 0 <= rh <= 100:
                _LOGGER.warning(f"Humidity value {rh}% is out of valid range (0-100%) for {self._name}")
                return
                
            if not -40 <= temp_c <= 80:
                _LOGGER.warning(f"Temperature value {temp_c}°C is out of reasonable range (-40 to 80°C) for {self._name}")
                return
            
            _LOGGER.debug(f"Calculating absolute humidity for {self._name}: RH={rh}%, T={temp_c}°C")

            # Calculate absolute humidity using Magnus formula
            saturation_vapor_pressure = 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5))
            ah = (saturation_vapor_pressure * rh * 2.1674) / (273.15 + temp_c)
            self._state = round(ah, 2)
            
            _LOGGER.debug(f"Calculated absolute humidity for {self._name}: {self._state} g/m³")
        except ValueError as e:
            _LOGGER.error(f"Invalid sensor values for {self._name} - humidity: {humidity.state}, temperature: {temperature.state}: {e}")
            self._state = None
        except Exception as e:
            _LOGGER.error(f"Error updating absolute humidity sensor {self._name}: {e}")
            self._state = None
