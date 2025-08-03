````markdown
# Absolute Humidity Sensor

> [!NOTE]  
> Experimental and mostly vibe coded, so use with care 

This Home Assistant custom component automatically creates absolute humidity sensors and window opening recommendation sensors based on existing relative humidity and temperature sensor pairs.

## Features

- **Automatic Discovery**: Automatically discovers humidity/temperature sensor pairs on startup
- **Dynamic Discovery**: Monitors for new sensors added to the system and automatically creates corresponding sensors
- **Window Recommendations**: Creates window opening recommendation sensors (manual setup required)
- **Smart Pairing**: Automatically pairs humidity sensors with corresponding temperature sensors based on naming conventions
- **Robust Error Handling**: Validates sensor values and handles edge cases gracefully
- **Enhanced Attributes**: Provides additional state attributes and proper Home Assistant integration

## How it Works

The component uses Home Assistant's event system to:

1. **Initial Discovery**: On startup, scans all existing sensor entities for humidity sensors with corresponding temperature sensors
2. **Dynamic Monitoring**: Listens for `EVENT_STATE_CHANGED` events to detect new humidity and temperature sensors as they're added
3. **Automatic Pairing**: For each humidity sensor found (e.g., `sensor.bedroom_humidity`), it looks for a corresponding temperature sensor (e.g., `sensor.bedroom_temperature`)
4. **Smart Creation**: Creates absolute humidity sensors automatically when valid pairs are found
5. **Outdoor Sensor Detection**: Monitors for new outdoor sensors and automatically re-evaluates existing indoor sensors for window recommendation creation
6. **Re-evaluation**: When outdoor sensors become available, automatically checks all existing indoor sensor pairs to create window recommendation sensors

The system now properly handles the scenario where outdoor sensors become available after indoor sensors have already been discovered.

## Window Opening Recommendations

The component can create window recommendation sensors that analyze indoor vs outdoor conditions and provide one of three states:

- **"ok to open"**: Outdoor conditions are better than indoor (lower absolute humidity and reasonable temperature)
- **"too wet"**: Outdoor absolute humidity is higher than indoor (opening windows would increase indoor humidity)
- **"too warm"**: Outdoor temperature is significantly higher than indoor temperature

Window recommendation sensors must be created manually using the `add_window_sensor` service, specifying both indoor and outdoor sensor entity IDs.

## Naming Convention

The component expects sensors to follow this naming pattern:
- Humidity sensor: `sensor.{location}_humidity`
- Temperature sensor: `sensor.{location}_temperature`

For example:
- `sensor.bedroom_humidity` → `sensor.bedroom_temperature`
- `sensor.living_room_humidity` → `sensor.living_room_temperature`

Alternative patterns supported:
- `sensor.{location}_temp` instead of `_temperature`
- `humidity` and `temperature` anywhere in the name

## Services

### Add Absolute Humidity Sensor
```yaml
service: absolute_humidity.add_sensor
data:
  humidity_entity_id: sensor.custom_humidity
  temperature_entity_id: sensor.custom_temperature
```

### Add Window Recommendation Sensor
```yaml
service: absolute_humidity.add_window_sensor
data:
  indoor_humidity_entity_id: sensor.bedroom_humidity
  indoor_temperature_entity_id: sensor.bedroom_temperature
  outdoor_humidity_entity_id: sensor.outdoor_humidity
  outdoor_temperature_entity_id: sensor.outdoor_temperature
```

### Rediscover All Sensors
```yaml
service: absolute_humidity.rediscover
```

### Re-evaluate Window Sensors
```yaml
service: absolute_humidity.reevaluate_window_sensors
```
This service re-evaluates existing indoor sensors to see if window recommendation sensors can now be created (useful when outdoor sensors become available after indoor sensors).

## Configuration

Add to your `configuration.yaml`:

```yaml
sensor:
  - platform: absolute_humidity
```

The component will automatically discover and create absolute humidity sensors. Window recommendation sensors must be added manually using the services provided.

## Example Automations

### Window Opening Notification
```yaml
automation:
  - alias: "Notify when it's good to open bedroom windows"
    trigger:
      - platform: state
        entity_id: sensor.window_recommendation_bedroom
        to: "ok to open"
    action:
      - service: notify.mobile_app_your_phone
        data:
          message: "It's a good time to open the bedroom windows!"

  - alias: "Close windows when outdoor humidity is too high"
    trigger:
      - platform: state
        entity_id: sensor.window_recommendation_living_room
        to: "too wet"
    action:
      - service: notify.mobile_app_your_phone
        data:
          message: "Consider closing living room windows - outdoor humidity is higher than indoor."
```

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

### Absolute Humidity Sensors
Each absolute humidity sensor provides:
- **State**: Absolute humidity value in g/m³
- **source_humidity**: Source humidity sensor entity ID
- **source_temperature**: Source temperature sensor entity ID
- **device_class**: "humidity"
- **state_class**: "measurement"
- **unit_of_measurement**: "g/m³"

### Window Recommendation Sensors
Each window recommendation sensor provides:
- **State**: One of "ok to open", "too wet", or "too warm"
- **indoor_humidity**: Indoor humidity sensor entity ID
- **indoor_temperature**: Indoor temperature sensor entity ID
- **outdoor_humidity**: Outdoor humidity sensor entity ID
- **outdoor_temperature**: Outdoor temperature sensor entity ID
- **indoor_humidity_value**: Current indoor humidity value
- **indoor_temperature_value**: Current indoor temperature value
- **outdoor_humidity_value**: Current outdoor humidity value
- **outdoor_temperature_value**: Current outdoor temperature value

````
