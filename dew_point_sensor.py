"""Dew Point Sensor class."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfTemperature
import math
import logging

_LOGGER = logging.getLogger(__name__)


class DewPointSensor(SensorEntity):
    """Representation of a Dew Point sensor."""
    
    def __init__(self, hass, humidity_entity_id, temperature_entity_id):
        self._hass = hass
        self._humidity_entity_id = humidity_entity_id
        self._temperature_entity_id = temperature_entity_id
        self._state = None
        
        # Create a more user-friendly name
        humidity_name = hass.states.get(humidity_entity_id).attributes.get('friendly_name', humidity_entity_id)
        self._name = f"{humidity_name.replace('Humidity', '').strip()} Dew Point"
        self._unique_id = f"dew_point_{humidity_entity_id}"
        
        _LOGGER.debug(f"Initialized DewPointSensor with humidity: {humidity_entity_id}, temperature: {temperature_entity_id}")

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
    def native_unit_of_measurement(self):
        """Return the native unit of measurement."""
        return UnitOfTemperature.CELSIUS
    
    @property
    def device_class(self):
        """Return the device class."""
        return "temperature"
    
    @property
    def state_class(self):
        """Return the state class."""
        return "measurement"
    
    @property
    def native_value(self):
        """Return the native value of the sensor."""
        return self._state
    
    @property
    def icon(self):
        """Return the icon for the sensor."""
        return "mdi:thermometer-water"
    
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
        _LOGGER.debug(f"Updating dew point sensor {self._name}")
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
            
            # Calculate dew point using Magnus formula
            # First calculate the vapor pressure
            saturation_vapor_pressure = 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5))
            actual_vapor_pressure = (rh / 100.0) * saturation_vapor_pressure
            
            # Then calculate dew point from vapor pressure
            if actual_vapor_pressure > 0:
                # Inverse Magnus formula
                ln_vp = math.log(actual_vapor_pressure / 6.112)
                dew_point = (243.5 * ln_vp) / (17.67 - ln_vp)
                self._state = round(dew_point, 1)
            else:
                self._state = None
                _LOGGER.warning(f"Invalid vapor pressure for dew point calculation: {actual_vapor_pressure}")
            
            _LOGGER.debug(f"Calculated dew point for {self._name} RH={rh}%, T={temp_c}°C: {self._state}°C")
        except ValueError as e:
            _LOGGER.error(f"Invalid sensor values for {self._name} - humidity: {humidity.state}, temperature: {temperature.state}: {e}")
            self._state = None
        except Exception as e:
            _LOGGER.error(f"Error updating dew point sensor {self._name}: {e}")
            self._state = None
