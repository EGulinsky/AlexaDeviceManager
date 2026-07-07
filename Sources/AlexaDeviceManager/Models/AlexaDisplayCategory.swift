import Foundation

/// Human-readable labels for Amazon's official Alexa smart home device
/// categories (`displayCategories.primary.value`). These values are
/// assigned by Amazon itself for every endpoint - regardless of which skill
/// connected the device. List is based on the documented Alexa Smart Home
/// "display categories". Unknown/new categories fall back to "_" -> space +
/// capitalized.
enum AlexaDisplayCategory {
    private static let labels: [String: String] = [
        "ALEXA_VOICE_ENABLED": "Alexa Voice Enabled",
        "LIGHT": "Light",
        "SWITCH": "Switch",
        "SMARTPLUG": "Smart Plug",
        "SMARTLOCK": "Smart Lock",
        "THERMOSTAT": "Thermostat",
        "TEMPERATURE_SENSOR": "Temperature Sensor",
        "CONTACT_SENSOR": "Contact Sensor",
        "MOTION_SENSOR": "Motion Sensor",
        "CAMERA": "Camera",
        "DOORBELL": "Doorbell",
        "DOOR": "Door",
        "GARAGE_DOOR": "Garage Door",
        "WINDOW": "Window",
        "BLIND": "Blind",
        "EXTERIOR_BLIND": "Exterior Blind",
        "INTERIOR_BLIND": "Interior Blind",
        "CURTAIN": "Curtain",
        "AWNING": "Awning",
        "FAN": "Fan",
        "AIR_CONDITIONER": "Air Conditioner",
        "AIR_FRESHENER": "Air Freshener",
        "AIR_PURIFIER": "Air Purifier",
        "AIR_QUALITY_MONITOR": "Air Quality Monitor",
        "HEATER": "Heater",
        "WATER_HEATER": "Water Heater",
        "VACUUM_CLEANER": "Vacuum Cleaner",
        "WASHER": "Washer",
        "DRYER": "Dryer",
        "DISHWASHER": "Dishwasher",
        "OVEN": "Oven",
        "MICROWAVE": "Microwave",
        "KETTLE": "Kettle",
        "SLOW_COOKER": "Slow Cooker",
        "COFFEE_MAKER": "Coffee Maker",
        "SPEAKER": "Speaker",
        "TV": "TV",
        "SCREEN": "Screen",
        "STREAMING_DEVICE": "Streaming Device",
        "GAME_CONSOLE": "Game Console",
        "MUSIC_SYSTEM": "Music System",
        "HEADPHONES": "Headphones",
        "NETWORK_HARDWARE": "Network Hardware",
        "WIFI_ROUTER": "Wi-Fi Router",
        "ROUTER": "Router",
        "HUB": "Hub / Bridge",
        "SECURITY_PANEL": "Security Panel",
        "SECURITY_SYSTEM": "Security System",
        "SCENE_TRIGGER": "Scene",
        "ACTIVITY_TRIGGER": "Activity",
        "OTHER": "Other",
        "MOBILE_PHONE": "Smartphone",
        "TABLET": "Tablet",
        "LAPTOP": "Laptop",
        "PRINTER": "Printer",
        "WEARABLE": "Wearable",
        "VEHICLE": "Vehicle",
        "AUTOMOBILE": "Car"
    ]

    static func label(for category: String) -> String {
        if let known = labels[category.uppercased()] {
            return known
        }
        return category.replacingOccurrences(of: "_", with: " ").capitalized
    }

    /// SF Symbol names matching each category - purely client-side, no icon
    /// field was found in the API (see the alexa_graphql_schema memory).
    private static let symbols: [String: String] = [
        "ALEXA_VOICE_ENABLED": "homepod.fill",
        "LIGHT": "lightbulb.fill",
        "SWITCH": "switch.2",
        "SMARTPLUG": "poweroutlet.type.f.fill",
        "SMARTLOCK": "lock.fill",
        "THERMOSTAT": "thermometer.medium",
        "TEMPERATURE_SENSOR": "thermometer",
        "CONTACT_SENSOR": "sensor.fill",
        "MOTION_SENSOR": "figure.walk.motion",
        "CAMERA": "camera.fill",
        "DOORBELL": "bell.fill",
        "DOOR": "door.left.hand.closed",
        "GARAGE_DOOR": "door.garage.closed",
        "WINDOW": "window.casement",
        "BLIND": "blinds.horizontal.closed",
        "EXTERIOR_BLIND": "blinds.horizontal.closed",
        "INTERIOR_BLIND": "blinds.horizontal.closed",
        "CURTAIN": "curtains.closed",
        "AWNING": "sunroof",
        "FAN": "fan.fill",
        "AIR_CONDITIONER": "snowflake",
        "AIR_FRESHENER": "wind",
        "AIR_PURIFIER": "wind",
        "AIR_QUALITY_MONITOR": "aqi.medium",
        "HEATER": "flame.fill",
        "WATER_HEATER": "drop.fill",
        "VACUUM_CLEANER": "robotic.vacuum.fill",
        "WASHER": "washer.fill",
        "DRYER": "dryer.fill",
        "DISHWASHER": "dishwasher.fill",
        "OVEN": "oven.fill",
        "MICROWAVE": "microwave.fill",
        "KETTLE": "kettle.fill",
        "SLOW_COOKER": "cooktop.fill",
        "COFFEE_MAKER": "cup.and.saucer.fill",
        "SPEAKER": "hifispeaker.fill",
        "TV": "tv.fill",
        "SCREEN": "display",
        "STREAMING_DEVICE": "appletv.fill",
        "GAME_CONSOLE": "gamecontroller.fill",
        "MUSIC_SYSTEM": "music.note",
        "HEADPHONES": "headphones",
        "NETWORK_HARDWARE": "network",
        "WIFI_ROUTER": "wifi.router.fill",
        "ROUTER": "wifi.router.fill",
        "HUB": "square.stack.3d.up.fill",
        "SECURITY_PANEL": "shield.lefthalf.filled",
        "SECURITY_SYSTEM": "shield.fill",
        "SCENE_TRIGGER": "theatermasks.fill",
        "ACTIVITY_TRIGGER": "bolt.fill",
        "OTHER": "cube.fill",
        "MOBILE_PHONE": "iphone",
        "TABLET": "ipad",
        "LAPTOP": "laptopcomputer",
        "PRINTER": "printer.fill",
        "WEARABLE": "applewatch",
        "VEHICLE": "car.fill",
        "AUTOMOBILE": "car.fill"
    ]

    static func symbolName(for category: String) -> String {
        symbols[category.uppercased()] ?? "cube"
    }
}
