_ALEXA_DISPLAY_CATEGORIES: dict[str, tuple[str, str]] = {
    "LIGHT": ("Light", "lightbulb"),
    "SWITCH": ("Switch", "power-plug"),
    "SMARTLOCK": ("Smart Lock", "lock"),
    "THERMOSTAT": ("Thermostat", "thermometer"),
    "CAMERA": ("Camera", "camera-web"),
    "DOORBELL": ("Doorbell", "bell-ring"),
    "SMARTPLUG": ("Smart Plug", "power-plug"),
    "SCENE_TRIGGER": ("Scene Trigger", "script-text"),
    "ACTIVITY_TRIGGER": ("Activity Trigger", "run"),
    "SMARTDEVICE": ("Smart Device", "chip"),
    "OUTDOOR_LIGHT": ("Outdoor Light", "lightbulb-outline"),
    "DIMMER": ("Dimmer", "brightness-5"),
    "FAN": ("Fan", "fan"),
    "AIR_QUALITY_MONITOR": ("Air Quality Monitor", "air-filter"),
    "HUMIDIFIER": ("Humidifier", "water"),
    "DEHUMIDIFIER": ("Dehumidifier", "water-off"),
    "AIR_PURIFIER": ("Air Purifier", "air-filter"),
    "HEATER": ("Heater", "radiator"),
    "SPEAKER": ("Speaker", "speaker"),
    "TV": ("TV", "television"),
    "STREAMING_DEVICE": ("Streaming Device", "cast"),
    "BLUETOOTH_SPEAKER": ("Bluetooth Speaker", "speaker-bluetooth"),
    "COMPUTER": ("Computer", "laptop"),
    "PHONE": ("Phone", "cellphone"),
    "TABLET": ("Tablet", "tablet"),
    "ROUTER": ("Router", "router-wireless"),
    "NETWORK_HARDWARE": ("Network Hardware", "router-wireless"),
    "DOOR": ("Door", "door"),
    "WINDOW": ("Window", "window-open"),
    "GARAGE_DOOR": ("Garage Door", "garage"),
    "LOCK": ("Lock", "lock"),
    "SHADE": ("Shade", "blinds"),
    "BLIND": ("Blind", "blinds"),
    "SENSOR": ("Sensor", "motion-sensor"),
    "CONTACT_SENSOR": ("Contact Sensor", "door"),
    "MOTION_SENSOR": ("Motion Sensor", "motion-sensor"),
    "TEMP_SENSOR": ("Temperature Sensor", "thermometer"),
    "WATER_LEAK_SENSOR": ("Water Leak Sensor", "water"),
    "SMOKE_DETECTOR": ("Smoke Detector", "smoke-detector"),
    "CO_DETECTOR": ("CO Detector", "smoke-detector"),
    "ALARM": ("Alarm", "alarm-light"),
    "SIREN": ("Siren", "alarm-light"),
    "OTHER": ("Other", "dots-square"),
}


_HOME_ASSISTANT_DOMAINS: dict[str, tuple[str, str]] = {
    "alarm_control_panel": ("Alarm", "alarm-light"),
    "alert": ("Alert", "alert"),
    "automation": ("Automation", "run"),
    "binary_sensor": ("Binary Sensor", "motion-sensor"),
    "button": ("Button", "gesture-tap"),
    "calendar": ("Calendar", "calendar"),
    "camera": ("Camera", "camera-web"),
    "climate": ("Climate", "thermometer"),
    "cover": ("Cover", "blinds"),
    "device_tracker": ("Device Tracker", "map-marker"),
    "fan": ("Fan", "fan"),
    "humidifier": ("Humidifier", "water"),
    "image_processing": ("Image Processing", "image-area"),
    "light": ("Light", "lightbulb"),
    "lock": ("Lock", "lock"),
    "media_player": ("Media Player", "speaker"),
    "notify": ("Notify", "bell"),
    "number": ("Number", "numeric"),
    "remote": ("Remote", "remote"),
    "scene": ("Scene", "palette"),
    "sensor": ("Sensor", "motion-sensor"),
    "siren": ("Siren", "alarm-light"),
    "switch": ("Switch", "power-plug"),
    "text": ("Text", "form-textbox"),
    "update": ("Update", "update"),
    "vacuum": ("Vacuum", "robot-vacuum"),
    "valve": ("Valve", "pipe-valve"),
    "water_heater": ("Water Heater", "water"),
    "zone": ("Zone", "map-marker-radius"),
}


def alexa_display_category_label(category: str) -> str:
    entry = _ALEXA_DISPLAY_CATEGORIES.get(category)
    return entry[0] if entry else category


def alexa_display_category_symbol(category: str) -> str:
    entry = _ALEXA_DISPLAY_CATEGORIES.get(category)
    return entry[1] if entry else "questionmark-circle"


def home_assistant_domain_label(domain: str) -> str:
    entry = _HOME_ASSISTANT_DOMAINS.get(domain)
    return entry[0] if entry else domain


def home_assistant_domain_symbol(domain: str) -> str:
    entry = _HOME_ASSISTANT_DOMAINS.get(domain)
    return entry[1] if entry else "questionmark-circle"
