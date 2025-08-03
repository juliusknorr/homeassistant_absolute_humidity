"""Window Recommendation Sensor class."""
from homeassistant.helpers.entity import Entity
import math
import logging

from .const import WINDOW_STATE_TOO_WET, WINDOW_STATE_TOO_WARM, WINDOW_STATE_OK_TO_OPEN, WINDOW_STATE_OPENING_RECOMMENDED, DEFAULT_TEMPERATURE_OFFSET, DEFAULT_ABSOLUTE_HUMIDITY_OFFSET, DEFAULT_ABSOLUTE_HUMIDITY_WARNING_LEVEL

_LOGGER = logging.getLogger(__name__)


class WindowRecommendationSensor(Entity):
    """Representation of a Window Recommendation sensor."""
    
    def __init__(self, hass, indoor_humidity_entity_id, indoor_temp_entity_id, 
                 outdoor_humidity_entity_id, outdoor_temp_entity_id,
                 indoor_abs_humidity_entity_id=None, outdoor_abs_humidity_entity_id=None,
                 temperature_offset=DEFAULT_TEMPERATURE_OFFSET, 
                 absolute_humidity_offset=DEFAULT_ABSOLUTE_HUMIDITY_OFFSET,
                 absolute_humidity_warning_level=DEFAULT_ABSOLUTE_HUMIDITY_WARNING_LEVEL):
        self._hass = hass
        self._indoor_humidity_entity_id = indoor_humidity_entity_id
        self._indoor_temp_entity_id = indoor_temp_entity_id
        self._outdoor_humidity_entity_id = outdoor_humidity_entity_id
        self._outdoor_temp_entity_id = outdoor_temp_entity_id
        self._indoor_abs_humidity_entity_id = indoor_abs_humidity_entity_id
        self._outdoor_abs_humidity_entity_id = outdoor_abs_humidity_entity_id
        self._temperature_offset = temperature_offset
        self._absolute_humidity_offset = absolute_humidity_offset
        self._absolute_humidity_warning_level = absolute_humidity_warning_level
        self._state = None
        
        # Store calculated values for attributes
        self._indoor_temp_value = None
        self._outdoor_temp_value = None
        self._indoor_abs_humidity_value = None
        self._outdoor_abs_humidity_value = None
        
        # Create a user-friendly name
        indoor_humidity_name = hass.states.get(indoor_humidity_entity_id).attributes.get('friendly_name', indoor_humidity_entity_id)
        location_name = indoor_humidity_name.replace('Humidity', '').strip()
        self._name = f"{location_name} window recommendation"
        self._unique_id = f"window_recommendation_{indoor_humidity_entity_id}"
        
        _LOGGER.debug(f"Initialized WindowRecommendationSensor: {self._name}")
        _LOGGER.debug(f"Using absolute humidity sensors: indoor={indoor_abs_humidity_entity_id}, outdoor={outdoor_abs_humidity_entity_id}")
        _LOGGER.debug(f"Using offsets: temperature={temperature_offset}°C, absolute_humidity={absolute_humidity_offset}g/m³, warning_level={absolute_humidity_warning_level}g/m³")

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
    def icon(self):
        """Return the icon for the sensor."""
        if self._state == WINDOW_STATE_OK_TO_OPEN:
            return "mdi:window-open"
        elif self._state == WINDOW_STATE_TOO_WET:
            return "mdi:water-alert"
        elif self._state == WINDOW_STATE_TOO_WARM:
            return "mdi:thermometer-alert"
        elif self._state == WINDOW_STATE_OPENING_RECOMMENDED:
            return "mdi:window-open-variant"
        else:
            return "mdi:window-closed"
    
    @property
    def extra_state_attributes(self):
        """Return additional state attributes."""
        attrs = {
            "indoor_humidity": self._indoor_humidity_entity_id,
            "indoor_temperature": self._indoor_temp_entity_id,
            "outdoor_humidity": self._outdoor_humidity_entity_id,
            "outdoor_temperature": self._outdoor_temp_entity_id,
        }
        
        # Add absolute humidity entity IDs if available
        if self._indoor_abs_humidity_entity_id:
            attrs["indoor_absolute_humidity"] = self._indoor_abs_humidity_entity_id
        if self._outdoor_abs_humidity_entity_id:
            attrs["outdoor_absolute_humidity"] = self._outdoor_abs_humidity_entity_id
        
        # Add current values if available
        indoor_humidity = self._hass.states.get(self._indoor_humidity_entity_id)
        indoor_temp = self._hass.states.get(self._indoor_temp_entity_id)
        outdoor_humidity = self._hass.states.get(self._outdoor_humidity_entity_id)
        outdoor_temp = self._hass.states.get(self._outdoor_temp_entity_id)
        
        if indoor_humidity and indoor_humidity.state not in ['unknown', 'unavailable']:
            attrs["indoor_humidity_value"] = f"{indoor_humidity.state}%"
        if indoor_temp and indoor_temp.state not in ['unknown', 'unavailable']:
            attrs["indoor_temperature_value"] = f"{indoor_temp.state}°C"
        if outdoor_humidity and outdoor_humidity.state not in ['unknown', 'unavailable']:
            attrs["outdoor_humidity_value"] = f"{outdoor_humidity.state}%"
        if outdoor_temp and outdoor_temp.state not in ['unknown', 'unavailable']:
            attrs["outdoor_temperature_value"] = f"{outdoor_temp.state}°C"
            
        # Add absolute humidity values if available
        # Try to find indoor absolute humidity sensor
        indoor_abs_sensor = self._find_absolute_humidity_sensor(self._indoor_humidity_entity_id)
        if indoor_abs_sensor:
            indoor_abs_state = self._hass.states.get(indoor_abs_sensor)
            if indoor_abs_state and indoor_abs_state.state not in ['unknown', 'unavailable']:
                attrs["indoor_absolute_humidity_value"] = f"{indoor_abs_state.state} g/m³"
        elif self._indoor_abs_humidity_entity_id:
            # Fallback to original method
            indoor_abs_humidity = self._hass.states.get(self._indoor_abs_humidity_entity_id)
            if indoor_abs_humidity and indoor_abs_humidity.state not in ['unknown', 'unavailable']:
                attrs["indoor_absolute_humidity_value"] = f"{indoor_abs_humidity.state} g/m³"
                
        # Try to find outdoor absolute humidity sensor
        outdoor_abs_sensor = self._find_absolute_humidity_sensor(self._outdoor_humidity_entity_id)
        if outdoor_abs_sensor:
            outdoor_abs_state = self._hass.states.get(outdoor_abs_sensor)
            if outdoor_abs_state and outdoor_abs_state.state not in ['unknown', 'unavailable']:
                attrs["outdoor_absolute_humidity_value"] = f"{outdoor_abs_state.state} g/m³"
        elif self._outdoor_abs_humidity_entity_id:
            # Fallback to original method
            outdoor_abs_humidity = self._hass.states.get(self._outdoor_abs_humidity_entity_id)
            if outdoor_abs_humidity and outdoor_abs_humidity.state not in ['unknown', 'unavailable']:
                attrs["outdoor_absolute_humidity_value"] = f"{outdoor_abs_humidity.state} g/m³"
        
        # Add temperature and absolute humidity differences if values are available
        if (self._indoor_temp_value is not None and self._outdoor_temp_value is not None):
            temp_diff = self._indoor_temp_value - self._outdoor_temp_value
            attrs["temperature_difference"] = f"{temp_diff:+.1f}°C"  # + for positive, - for negative
            
        if (self._indoor_abs_humidity_value is not None and self._outdoor_abs_humidity_value is not None):
            abs_humidity_diff = self._indoor_abs_humidity_value - self._outdoor_abs_humidity_value
            attrs["absolute_humidity_difference"] = f"{abs_humidity_diff:+.2f} g/m³"
        
        # Add configuration offsets
        attrs["temperature_offset"] = f"{self._temperature_offset}°C"
        attrs["absolute_humidity_offset"] = f"{self._absolute_humidity_offset} g/m³"
        attrs["absolute_humidity_warning_level"] = f"{self._absolute_humidity_warning_level} g/m³"
        
        return attrs
    
    @property
    def available(self):
        """Return True if entity is available."""
        indoor_humidity = self._hass.states.get(self._indoor_humidity_entity_id)
        indoor_temp = self._hass.states.get(self._indoor_temp_entity_id)
        outdoor_humidity = self._hass.states.get(self._outdoor_humidity_entity_id)
        outdoor_temp = self._hass.states.get(self._outdoor_temp_entity_id)
        
        return (indoor_humidity is not None and 
                indoor_temp is not None and
                outdoor_humidity is not None and
                outdoor_temp is not None and
                indoor_humidity.state not in ['unknown', 'unavailable'] and
                indoor_temp.state not in ['unknown', 'unavailable'] and
                outdoor_humidity.state not in ['unknown', 'unavailable'] and
                outdoor_temp.state not in ['unknown', 'unavailable'])

    async def async_update(self):
        """Update the sensor state."""
        _LOGGER.debug(f"Updating window recommendation sensor {self._name}")
        
        # Get all sensor states
        indoor_humidity = self._hass.states.get(self._indoor_humidity_entity_id)
        indoor_temp = self._hass.states.get(self._indoor_temp_entity_id)
        outdoor_humidity = self._hass.states.get(self._outdoor_humidity_entity_id)
        outdoor_temp = self._hass.states.get(self._outdoor_temp_entity_id)

        # Check if all states are available
        if not all([indoor_humidity, indoor_temp, outdoor_humidity, outdoor_temp]):
            _LOGGER.warning(f"Some entities are None for {self._name}")
            return
        
        # Check if states are valid
        states = [indoor_humidity, indoor_temp, outdoor_humidity, outdoor_temp]
        if any(state.state in ['unknown', 'unavailable'] for state in states):
            _LOGGER.debug(f"Some entities are unavailable for {self._name}")
            return

        try:
            indoor_rh = float(indoor_humidity.state)
            indoor_temp_c = float(indoor_temp.state)
            outdoor_rh = float(outdoor_humidity.state)
            outdoor_temp_c = float(outdoor_temp.state)
            
            # Validate ranges
            if not all(0 <= rh <= 100 for rh in [indoor_rh, outdoor_rh]):
                _LOGGER.warning(f"Humidity values out of range for {self._name}")
                return
                
            if not all(-40 <= temp <= 80 for temp in [indoor_temp_c, outdoor_temp_c]):
                _LOGGER.warning(f"Temperature values out of range for {self._name}")
                return
            
            _LOGGER.debug(f"Calculating window recommendation for {self._name}: "
                         f"Indoor: {indoor_temp_c}°C, {indoor_rh}% RH; "
                         f"Outdoor: {outdoor_temp_c}°C, {outdoor_rh}% RH")

            # Try to get absolute humidity values directly from sensors first
            indoor_abs_humidity = None
            outdoor_abs_humidity = None

            _LOGGER.debug(f"Checking absolute humidity sensors if available: {self._indoor_abs_humidity_entity_id}, {self._outdoor_abs_humidity_entity_id}")

            # Try to find indoor absolute humidity sensor
            indoor_abs_sensor = self._find_absolute_humidity_sensor(self._indoor_humidity_entity_id)
            if indoor_abs_sensor:
                indoor_abs_state = self._hass.states.get(indoor_abs_sensor)
                _LOGGER.debug(f"Found indoor absolute humidity sensor: {indoor_abs_sensor} with state {indoor_abs_state.state if indoor_abs_state else 'None'}")
                if indoor_abs_state and indoor_abs_state.state not in ['unknown', 'unavailable']:
                    try:
                        indoor_abs_humidity = float(indoor_abs_state.state)
                        _LOGGER.debug(f"Using indoor absolute humidity sensor: {indoor_abs_humidity} g/m³")
                    except ValueError:
                        pass
            elif self._indoor_abs_humidity_entity_id:
                # Fallback to original method
                indoor_abs_state = self._hass.states.get(self._indoor_abs_humidity_entity_id)
                _LOGGER.debug(f"Checking indoor absolute humidity sensor (fallback): {self._indoor_abs_humidity_entity_id} {indoor_abs_state.state if indoor_abs_state else 'None'}")
                if indoor_abs_state and indoor_abs_state.state not in ['unknown', 'unavailable']:
                    try:
                        indoor_abs_humidity = float(indoor_abs_state.state)
                        _LOGGER.debug(f"Using indoor absolute humidity sensor (fallback): {indoor_abs_humidity} g/m³")
                    except ValueError:
                        pass
                        
            # Try to find outdoor absolute humidity sensor
            outdoor_abs_sensor = self._find_absolute_humidity_sensor(self._outdoor_humidity_entity_id)
            if outdoor_abs_sensor:
                outdoor_abs_state = self._hass.states.get(outdoor_abs_sensor)
                _LOGGER.debug(f"Found outdoor absolute humidity sensor: {outdoor_abs_sensor} with state {outdoor_abs_state.state if outdoor_abs_state else 'None'}")
                if outdoor_abs_state and outdoor_abs_state.state not in ['unknown', 'unavailable']:
                    try:
                        outdoor_abs_humidity = float(outdoor_abs_state.state)
                        _LOGGER.debug(f"Using outdoor absolute humidity sensor: {outdoor_abs_humidity} g/m³")
                    except ValueError:
                        pass
            elif self._outdoor_abs_humidity_entity_id:
                # Fallback to original method  
                outdoor_abs_state = self._hass.states.get(self._outdoor_abs_humidity_entity_id)
                _LOGGER.debug(f"Checking outdoor absolute humidity sensor (fallback): {self._outdoor_abs_humidity_entity_id} {outdoor_abs_state.state if outdoor_abs_state else 'None'}")
                if outdoor_abs_state and outdoor_abs_state.state not in ['unknown', 'unavailable']:
                    try:
                        outdoor_abs_humidity = float(outdoor_abs_state.state)
                        _LOGGER.debug(f"Using outdoor absolute humidity sensor (fallback): {outdoor_abs_humidity} g/m³")
                    except ValueError:
                        pass

            # Calculate absolute humidity if sensors not available
            def calc_abs_humidity(temp_c, rh):
                saturation_vapor_pressure = 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5))
                return (saturation_vapor_pressure * rh * 2.1674) / (273.15 + temp_c)
            
            if indoor_abs_humidity is None:
                indoor_abs_humidity = calc_abs_humidity(indoor_temp_c, indoor_rh)
                _LOGGER.debug(f"Calculated indoor absolute humidity: {indoor_abs_humidity} g/m³")
                
            if outdoor_abs_humidity is None:
                outdoor_abs_humidity = calc_abs_humidity(outdoor_temp_c, outdoor_rh)
                _LOGGER.debug(f"Calculated outdoor absolute humidity: {outdoor_abs_humidity} g/m³")
            
            # Store values for use in attributes
            self._indoor_temp_value = indoor_temp_c
            self._outdoor_temp_value = outdoor_temp_c
            self._indoor_abs_humidity_value = indoor_abs_humidity
            self._outdoor_abs_humidity_value = outdoor_abs_humidity
            
            # Determine recommendation based on absolute humidity comparison
            # If outdoor absolute humidity is higher than indoor by the configured offset, opening windows would increase indoor humidity
            if outdoor_abs_humidity > indoor_abs_humidity + self._absolute_humidity_offset:
                self._state = WINDOW_STATE_TOO_WET
            # Check if indoor absolute humidity is above the warning level first
            elif indoor_abs_humidity > self._absolute_humidity_warning_level:
                self._state = WINDOW_STATE_OPENING_RECOMMENDED
            # If outdoor temperature is significantly higher than indoor by the configured offset and indoor is comfortable
            elif outdoor_temp_c > indoor_temp_c + self._temperature_offset and indoor_temp_c < 24:
                self._state = WINDOW_STATE_TOO_WARM
            # Otherwise, it's generally OK to open
            else:
                self._state = WINDOW_STATE_OK_TO_OPEN
            
            _LOGGER.debug(f"Window recommendation for {self._name}: {self._state} "
                         f"(Indoor AH: {indoor_abs_humidity:.2f}, Outdoor AH: {outdoor_abs_humidity:.2f}, "
                         f"Temp offset: {self._temperature_offset}°C, AH offset: {self._absolute_humidity_offset}g/m³, "
                         f"AH warning level: {self._absolute_humidity_warning_level}g/m³)")
            
        except ValueError as e:
            _LOGGER.error(f"Invalid sensor values for {self._name}: {e}")
            self._state = None
            self._indoor_temp_value = None
            self._outdoor_temp_value = None
            self._indoor_abs_humidity_value = None
            self._outdoor_abs_humidity_value = None
        except Exception as e:
            _LOGGER.error(f"Error updating window recommendation sensor {self._name}: {e}")
            self._state = None
            self._indoor_temp_value = None
            self._outdoor_temp_value = None
            self._indoor_abs_humidity_value = None
            self._outdoor_abs_humidity_value = None
    
    def _find_absolute_humidity_sensor(self, humidity_entity_id):
        """Find the corresponding absolute humidity sensor for a given humidity sensor."""
        if not humidity_entity_id:
            return None
            
        _LOGGER.debug(f"Looking for absolute humidity sensor for: {humidity_entity_id}")
        
        # Search through all sensor entities to find one with matching source_humidity attribute
        for entity_id in self._hass.states.async_entity_ids('sensor'):
            if entity_id.startswith('sensor.') and 'absolute_humidity' in entity_id.lower():
                state = self._hass.states.get(entity_id)
                if state and state.attributes:
                    source_humidity = state.attributes.get('source_humidity')
                    if source_humidity == humidity_entity_id:
                        _LOGGER.debug(f"Found absolute humidity sensor {entity_id} for humidity sensor {humidity_entity_id}")
                        return entity_id
        
        # Also try the original expected pattern as fallback
        expected_entity_id = f"sensor.absolute_humidity_{humidity_entity_id.split('.')[-1]}"
        if self._hass.states.get(expected_entity_id):
            _LOGGER.debug(f"Found absolute humidity sensor using expected pattern: {expected_entity_id}")
            return expected_entity_id
            
        _LOGGER.debug(f"No absolute humidity sensor found for: {humidity_entity_id}")
        return None
