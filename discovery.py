"""Discovery system for Absolute Humidity sensors."""
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.core import callback, Event
import logging

from .const import SIGNAL_ADD_SENSOR, SIGNAL_ADD_WINDOW_SENSOR, DEFAULT_TEMPERATURE_OFFSET, DEFAULT_ABSOLUTE_HUMIDITY_OFFSET, DEFAULT_ABSOLUTE_HUMIDITY_WARNING_LEVEL
from .absolute_humidity_sensor import AbsoluteHumiditySensor
from .window_recommendation_sensor import WindowRecommendationSensor

_LOGGER = logging.getLogger(__name__)


class AbsoluteHumidityDiscovery:
    """Handles dynamic discovery of humidity/temperature sensor pairs."""
    
    def __init__(self, hass, async_add_entities, config=None):
        self._hass = hass
        self._async_add_entities = async_add_entities
        self._created_sensors = set()
        self._created_window_sensors = set()
        self._unsub_dispatcher = None
        self._unsub_window_dispatcher = None
        self._unsub_state_listener = None
        self._config = config or {}
        
        # Get configured outdoor sensors
        self._outdoor_temperature_sensor = self._config.get('outdoor_temperature_sensor')
        self._outdoor_humidity_sensor = self._config.get('outdoor_humidity_sensor')
        
        # Get configured offsets with defaults
        self._temperature_offset = self._config.get('temperature_offset', DEFAULT_TEMPERATURE_OFFSET)
        self._absolute_humidity_offset = self._config.get('absolute_humidity_offset', DEFAULT_ABSOLUTE_HUMIDITY_OFFSET)
        self._absolute_humidity_warning_level = self._config.get('absolute_humidity_warning_level', DEFAULT_ABSOLUTE_HUMIDITY_WARNING_LEVEL)
    
    async def async_setup(self):
        """Set up the discovery system."""
        # Initial discovery of existing entities
        await self._discover_existing_entities()
        
        # Set up dispatcher for manual sensor addition
        self._unsub_dispatcher = async_dispatcher_connect(
            self._hass, SIGNAL_ADD_SENSOR, self._async_add_sensor
        )
        
        # Set up dispatcher for manual window sensor addition
        self._unsub_window_dispatcher = async_dispatcher_connect(
            self._hass, SIGNAL_ADD_WINDOW_SENSOR, self._async_add_window_sensor
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
        if self._unsub_window_dispatcher:
            self._unsub_window_dispatcher()
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
            # Skip self-generated absolute humidity sensors to avoid recursive discovery
            if entity_id.startswith('sensor.absolute_humidity_'):
                _LOGGER.debug(f"Skipping self-generated absolute humidity sensor: {entity_id}")
                continue
            if state.attributes.get('device_class') == 'humidity':
                result = await self._try_create_sensor(entity_id)
                if result:
                    if isinstance(result, list):
                        sensors.extend(result)
                    else:
                        sensors.append(result)
        
        if sensors:
            _LOGGER.info(f"Discovered {len(sensors)} sensors (absolute humidity and window recommendation sensors)")
            self._async_add_entities(sensors, True)
    
    @callback
    def _async_state_changed_listener(self, event: Event):
        """Listen for state changes that might indicate new entities."""
        entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")
        
        if not entity_id or not new_state:
            return
        
        # Process sensor entities with humidity or temperature device class
        if entity_id.startswith("sensor."):
            device_class = new_state.attributes.get('device_class')
            
            if device_class == 'humidity':
                # Skip self-generated absolute humidity sensors to avoid recursive discovery
                if entity_id.startswith('sensor.absolute_humidity_'):
                    _LOGGER.debug(f"Skipping self-generated absolute humidity sensor: {entity_id}")
                    return
                
                # Handle both indoor humidity sensors (for absolute humidity) and outdoor humidity sensors (for window recommendations)
                self._hass.async_create_task(self._async_handle_new_humidity_entity(entity_id))
                self._hass.async_create_task(self._check_and_handle_outdoor_sensor(entity_id, 'humidity'))
                
            elif device_class == 'temperature':
                # Check if this might be an outdoor temperature sensor and trigger window sensor re-evaluation
                self._hass.async_create_task(self._check_and_handle_outdoor_sensor(entity_id, 'temperature'))
    
    async def _async_handle_new_humidity_entity(self, humidity_entity_id):
        """Handle discovery of a new humidity entity."""
        if humidity_entity_id in self._created_sensors:
            return
        
        result = await self._try_create_sensor(humidity_entity_id)
        if result:
            if isinstance(result, list):
                sensor_names = [sensor.name for sensor in result]
                _LOGGER.info(f"Dynamically discovered new sensors: {', '.join(sensor_names)}")
                self._async_add_entities(result, True)
            else:
                _LOGGER.info(f"Dynamically discovered new absolute humidity sensor: {result.name}")
                self._async_add_entities([result], True)
    
    async def _async_handle_new_temperature_entity(self, temperature_entity_id):
        """Handle discovery of a new temperature entity that might enable window sensors."""
        # Check if this looks like an outdoor temperature sensor
        await self._check_and_handle_outdoor_sensor(temperature_entity_id, 'temperature')
    
    async def _check_and_handle_outdoor_sensor(self, entity_id, sensor_type):
        """Check if an entity is an outdoor sensor and handle accordingly."""
        entity_lower = entity_id.lower()
        sensor_state = self._hass.states.get(entity_id)
        if not sensor_state:
            return
            
        name_lower = sensor_state.attributes.get('friendly_name', '').lower()
        
        # Common patterns for outdoor sensors
        outdoor_patterns = [
            'outdoor', 'outside', 'exterior', 'external', 'weather', 
            'yard', 'garden', 'patio', 'deck', 'balcony'
        ]
        
        # Check if this looks like an outdoor sensor
        is_outdoor = any(pattern in entity_lower or pattern in name_lower 
                        for pattern in outdoor_patterns)
        
        if is_outdoor:
            _LOGGER.debug(f"New outdoor {sensor_type} sensor detected: {entity_id}")
            # Re-evaluate existing indoor sensors for window recommendation creation
            await self._reevaluate_window_sensors()
    
    async def _reevaluate_window_sensors(self):
        """Re-evaluate existing indoor sensors to see if window sensors can now be created."""
        _LOGGER.debug("Re-evaluating existing indoor sensors for window recommendation creation")
        
        # Find outdoor sensors
        outdoor_temp, outdoor_humidity = self._find_outdoor_sensors()
        
        if not (outdoor_temp and outdoor_humidity):
            _LOGGER.debug("Outdoor sensors not available yet for window recommendations")
            return
        
        new_window_sensors = []
        
        # Check all existing absolute humidity sensors to see if we can create window sensors
        for humidity_entity_id in self._created_sensors:
            # Find the corresponding temperature sensor for this humidity sensor
            temp_entity_id = self._find_matching_temperature_sensor(humidity_entity_id)
            if not temp_entity_id:
                continue
                
            sensor_key = f"{humidity_entity_id}_{temp_entity_id}"
            
            # Skip if we already created a window sensor for this pair
            if sensor_key in self._created_window_sensors:
                continue
            
            # Try to create window sensor
            window_sensor = await self._try_create_window_sensor(humidity_entity_id, temp_entity_id)
            if window_sensor:
                new_window_sensors.append(window_sensor)
                _LOGGER.info(f"Created window recommendation sensor after outdoor sensor became available: {window_sensor.name}")
        
        if new_window_sensors:
            self._async_add_entities(new_window_sensors, True)
    
    async def _try_create_sensor(self, humidity_entity_id):
        """Try to create an absolute humidity sensor for the given humidity entity."""
        if humidity_entity_id in self._created_sensors:
            return None
        
        # Skip self-generated absolute humidity sensors to avoid recursive discovery
        if humidity_entity_id.startswith('sensor.absolute_humidity_'):
            _LOGGER.debug(f"Skipping self-generated absolute humidity sensor: {humidity_entity_id}")
            return None
        
        temp_entity_id = self._find_matching_temperature_sensor(humidity_entity_id)
        if temp_entity_id:
            temp_state = self._hass.states.get(temp_entity_id)
            if temp_state and temp_state.attributes.get('device_class') == 'temperature':
                _LOGGER.debug(f"Creating absolute humidity sensor for humidity: {humidity_entity_id}, temperature: {temp_entity_id}")
                self._created_sensors.add(humidity_entity_id)
                
                # Create the absolute humidity sensor
                abs_humidity_sensor = AbsoluteHumiditySensor(self._hass, humidity_entity_id, temp_entity_id)
                
                # Also try to create a window recommendation sensor
                window_sensor = await self._try_create_window_sensor(humidity_entity_id, temp_entity_id)
                
                # Return both sensors if window sensor was created, otherwise just the abs humidity sensor
                if window_sensor:
                    return [abs_humidity_sensor, window_sensor]
                else:
                    return abs_humidity_sensor
        
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
            # Pattern 6: same base name without suffix
            humidity_entity_id.replace('_humidity', ''),
            # Pattern 7: same base without the suffix and without starting sensor_
            humidity_entity_id.replace('sensor_', '').replace('_humidity', ''),
        ]
        
        for temp_entity_id in patterns:
            if temp_entity_id != humidity_entity_id and self._hass.states.get(temp_entity_id):
                _LOGGER.debug(f"Found potential temperature sensor {temp_entity_id} for humidity sensor {humidity_entity_id}")
                return temp_entity_id
        
        return None
    
    def _find_outdoor_sensors(self):
        """Find outdoor temperature and humidity sensors based on configuration or common naming patterns."""
        outdoor_temp = None
        outdoor_humidity = None
        
        # First, try to use configured outdoor sensors
        if self._outdoor_temperature_sensor:
            if self._hass.states.get(self._outdoor_temperature_sensor):
                outdoor_temp = self._outdoor_temperature_sensor
                _LOGGER.debug(f"Using configured outdoor temperature sensor: {outdoor_temp}")
            else:
                _LOGGER.warning(f"Configured outdoor temperature sensor not found: {self._outdoor_temperature_sensor}")
        
        if self._outdoor_humidity_sensor:
            if self._hass.states.get(self._outdoor_humidity_sensor):
                outdoor_humidity = self._outdoor_humidity_sensor
                _LOGGER.debug(f"Using configured outdoor humidity sensor: {outdoor_humidity}")
            else:
                _LOGGER.warning(f"Configured outdoor humidity sensor not found: {self._outdoor_humidity_sensor}")
        
        # If both configured sensors are found, return them
        if outdoor_temp and outdoor_humidity:
            _LOGGER.debug(f"Using configured outdoor sensor pair: temp={outdoor_temp}, humidity={outdoor_humidity}")
            return outdoor_temp, outdoor_humidity
        
        # Fall back to auto-detection if configuration is incomplete
        if not outdoor_temp or not outdoor_humidity:
            _LOGGER.debug("Falling back to auto-detection for missing outdoor sensors...")
            
            # Common patterns for outdoor sensors
            outdoor_patterns = [
                'outdoor', 'outside', 'exterior', 'external', 'weather', 
                'yard', 'garden', 'patio', 'deck', 'balcony'
            ]
            
            _LOGGER.debug("Searching for outdoor sensors...")
            
            for entity_id in self._hass.states.async_entity_ids('sensor'):
                state = self._hass.states.get(entity_id)
                if not state:
                    continue
                    
                entity_lower = entity_id.lower()
                name_lower = state.attributes.get('friendly_name', '').lower()
                
                # Check if this looks like an outdoor sensor
                is_outdoor = any(pattern in entity_lower or pattern in name_lower 
                               for pattern in outdoor_patterns)
                
                if is_outdoor:
                    device_class = state.attributes.get('device_class')
                    if device_class == 'temperature' and not outdoor_temp:
                        outdoor_temp = entity_id
                        _LOGGER.debug(f"Found outdoor temperature sensor: {entity_id}")
                    elif device_class == 'humidity' and not outdoor_humidity:
                        outdoor_humidity = entity_id
                        _LOGGER.debug(f"Found outdoor humidity sensor: {entity_id}")
                        
                    # Break early if we found both
                    if outdoor_temp and outdoor_humidity:
                        break
        
        if outdoor_temp and outdoor_humidity:
            _LOGGER.debug(f"Found outdoor sensor pair: temp={outdoor_temp}, humidity={outdoor_humidity}")
        elif outdoor_temp:
            _LOGGER.debug(f"Found outdoor temperature sensor only: {outdoor_temp}")
        elif outdoor_humidity:
            _LOGGER.debug(f"Found outdoor humidity sensor only: {outdoor_humidity}")
        else:
            _LOGGER.debug("No outdoor sensors found")
        
        return outdoor_temp, outdoor_humidity
    
    async def _try_create_window_sensor(self, indoor_humidity_entity_id, indoor_temp_entity_id):
        """Try to create a window recommendation sensor for the given indoor sensors."""
        sensor_key = f"{indoor_humidity_entity_id}_{indoor_temp_entity_id}"
        if sensor_key in self._created_window_sensors:
            _LOGGER.debug(f"Window sensor already exists for {sensor_key}")
            return None
        
        outdoor_temp, outdoor_humidity = self._find_outdoor_sensors()
        
        if not outdoor_temp:
            _LOGGER.debug(f"No outdoor temperature sensor found for window recommendation (indoor: {indoor_humidity_entity_id})")
            return None
            
        if not outdoor_humidity:
            _LOGGER.debug(f"No outdoor humidity sensor found for window recommendation (indoor: {indoor_humidity_entity_id})")
            return None
        
        # Find corresponding absolute humidity sensors
        indoor_abs_humidity_entity_id = f"sensor.absolute_humidity_{indoor_humidity_entity_id.split('.')[-1]}"
        
        # Try to find outdoor absolute humidity sensor
        outdoor_abs_humidity_entity_id = None
        outdoor_abs_temp_entity_id = self._find_matching_temperature_sensor(outdoor_humidity)
        if outdoor_abs_temp_entity_id:
            outdoor_abs_humidity_entity_id = f"sensor.absolute_humidity_{outdoor_humidity.split('.')[-1]}"
        
        _LOGGER.debug(f"Creating window recommendation sensor for indoor sensors: {indoor_humidity_entity_id}, {indoor_temp_entity_id}")
        _LOGGER.debug(f"Using outdoor sensors: {outdoor_humidity}, {outdoor_temp}")
        _LOGGER.debug(f"Using absolute humidity sensors: indoor={indoor_abs_humidity_entity_id}, outdoor={outdoor_abs_humidity_entity_id}")
        
        self._created_window_sensors.add(sensor_key)
        return WindowRecommendationSensor(
            self._hass, 
            indoor_humidity_entity_id, 
            indoor_temp_entity_id,
            outdoor_humidity, 
            outdoor_temp,
            indoor_abs_humidity_entity_id,
            outdoor_abs_humidity_entity_id,
            self._temperature_offset,
            self._absolute_humidity_offset,
            self._absolute_humidity_warning_level
        )

    @callback
    def _async_add_window_sensor(self, indoor_humidity_entity_id, indoor_temp_entity_id, 
                                outdoor_humidity_entity_id, outdoor_temp_entity_id):
        """Add a window recommendation sensor via dispatcher signal."""
        sensor_key = f"{indoor_humidity_entity_id}_{indoor_temp_entity_id}"
        if sensor_key not in self._created_window_sensors:
            # Find corresponding absolute humidity sensors
            indoor_abs_humidity_entity_id = f"sensor.absolute_humidity_{indoor_humidity_entity_id.split('.')[-1]}"
            outdoor_abs_humidity_entity_id = f"sensor.absolute_humidity_{outdoor_humidity_entity_id.split('.')[-1]}"
            
            self._created_window_sensors.add(sensor_key)
            sensor = WindowRecommendationSensor(
                self._hass, 
                indoor_humidity_entity_id, 
                indoor_temp_entity_id,
                outdoor_humidity_entity_id, 
                outdoor_temp_entity_id,
                indoor_abs_humidity_entity_id,
                outdoor_abs_humidity_entity_id,
                self._temperature_offset,
                self._absolute_humidity_offset,
                self._absolute_humidity_warning_level
            )
            self._async_add_entities([sensor], True)
            _LOGGER.info(f"Manually added window recommendation sensor: {sensor.name}")
    
    @callback
    def _async_add_sensor(self, humidity_entity_id, temperature_entity_id):
        """Add a sensor via dispatcher signal."""
        if humidity_entity_id not in self._created_sensors:
            self._created_sensors.add(humidity_entity_id)
            sensor = AbsoluteHumiditySensor(self._hass, humidity_entity_id, temperature_entity_id)
            self._async_add_entities([sensor], True)
            _LOGGER.info(f"Manually added absolute humidity sensor: {sensor.name}")
