# Absolute Humidity Sensor

> [!NOTE]  
> Experimental and mostly vibe coded, so use with care 


This Home Assistant custom component automatically creates absolute humidity sensors based on existing relative humidity and temperature sensor pairs.

## Features

- **Automatic Discovery**: Automatically discovers humidity/temperature sensor pairs on startup
- **Dynamic Discovery**: Monitors for new sensors added to the system and automatically creates corresponding absolute humidity sensors
- **Smart Pairing**: Automatically pairs humidity sensors with corresponding temperature sensors based on naming conventions
- **Robust Error Handling**: Validates sensor values and handles edge cases gracefully
- **Enhanced Attributes**: Provides additional state attributes and proper Home Assistant integration

## How it Works

The component uses Home Assistant's event system to:

1. **Initial Discovery**: On startup, scans all existing sensor entities for humidity sensors with corresponding temperature sensors
2. **Dynamic Monitoring**: Listens for `EVENT_STATE_CHANGED` events to detect new humidity sensors as they're added
3. **Automatic Pairing**: For each humidity sensor found (e.g., `sensor.bedroom_humidity`), it looks for a corresponding temperature sensor (e.g., `sensor.bedroom_temperature`)
4. **Smart Creation**: Creates absolute humidity sensors automatically when valid pairs are found

## Naming Convention

The component expects sensors to follow this naming pattern:
- Humidity sensor: `sensor.{location}_humidity`
- Temperature sensor: `sensor.{location}_temperature`

For example:
- `sensor.bedroom_humidity` → `sensor.bedroom_temperature`
- `sensor.living_room_humidity` → `sensor.living_room_temperature`

## Manual Discovery

You can also manually trigger discovery for specific sensor pairs using the dispatcher:

```python
from homeassistant.helpers.dispatcher import async_dispatcher_send
from custom_components.absolute_humidity.sensor import async_discover

# Manually add a sensor pair
await async_discover(hass, "sensor.kitchen_humidity", "sensor.kitchen_temperature")
```

## Configuration

Add to your `configuration.yaml`:

```yaml
sensor:
  - platform: absolute_humidity
```

No additional configuration is required - the component will automatically discover and create sensors.

## Calculated Values

Absolute humidity is calculated using the Magnus formula:

```
SVP = 6.112 × e^((17.67 × T) / (T + 243.5))
AH = (SVP × RH × 2.1674) / (273.15 + T)
```

Where:
- SVP = Saturation Vapor Pressure (hPa)
- T = Temperature (°C)
- RH = Relative Humidity (%)
- AH = Absolute Humidity (g/m³)

## Attributes

Each absolute humidity sensor provides:
- **State**: Absolute humidity value in g/m³
- **source_humidity**: Source humidity sensor entity ID
- **source_temperature**: Source temperature sensor entity ID
- **device_class**: "humidity"
- **state_class**: "measurement"
- **unit_of_measurement**: "g/m³"
