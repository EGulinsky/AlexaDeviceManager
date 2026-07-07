import Foundation

/// Human-readable labels for Home Assistant domains (the part before the
/// "#" in applianceId suffixes like `cover#living_room_left`, see NOTES.md
/// #2). Covers the common HA domains that can appear as Alexa devices via
/// the smart home skill link. Unknown domains fall back to the capitalized
/// raw value.
enum HomeAssistantDomain {
    private static let labels: [String: String] = [
        "light": "Light",
        "switch": "Plug / Switch",
        "cover": "Blind / Shutter",
        "climate": "Climate / Thermostat",
        "media_player": "Media Player",
        "sensor": "Sensor",
        "binary_sensor": "Sensor (binary)",
        "fan": "Fan",
        "lock": "Lock",
        "vacuum": "Vacuum Cleaner",
        "camera": "Camera",
        "alarm_control_panel": "Alarm System",
        "humidifier": "Humidifier",
        "water_heater": "Water Heater",
        "valve": "Valve",
        "siren": "Siren",
        "scene": "Scene",
        "script": "Script",
        "input_boolean": "Switch (Helper)",
        "input_number": "Number (Helper)",
        "input_select": "Selector (Helper)",
        "group": "Group",
        "person": "Person",
        "device_tracker": "Location Tracker",
        "zone": "Zone / Area"
    ]

    static func label(for domain: String) -> String {
        labels[domain.lowercased()] ?? domain.capitalized
    }

    private static let symbols: [String: String] = [
        "light": "lightbulb.fill",
        "switch": "poweroutlet.type.f.fill",
        "cover": "blinds.horizontal.closed",
        "climate": "thermometer.medium",
        "media_player": "hifispeaker.fill",
        "sensor": "sensor.fill",
        "binary_sensor": "sensor.fill",
        "fan": "fan.fill",
        "lock": "lock.fill",
        "vacuum": "robotic.vacuum.fill",
        "camera": "camera.fill",
        "alarm_control_panel": "shield.fill",
        "humidifier": "drop.fill",
        "water_heater": "drop.fill",
        "valve": "spigot.fill",
        "siren": "speaker.wave.3.fill",
        "scene": "theatermasks.fill",
        "script": "list.bullet.rectangle",
        "input_boolean": "switch.2",
        "input_number": "number",
        "input_select": "list.bullet",
        "group": "square.stack.3d.up.fill",
        "person": "person.fill",
        "device_tracker": "location.fill",
        "zone": "map.fill"
    ]

    static func symbolName(for domain: String) -> String {
        symbols[domain.lowercased()] ?? "cube"
    }
}
