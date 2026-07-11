from __future__ import annotations
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtCore import QSize, Qt

_ICON_SIZE = 16

_SVGS: dict[str, str] = {
    "group": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#666"><path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/></svg>""",
    "lightbulb": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#e6a817"><path d="M9 21c0 .55.45 1 1 1h4c.55 0 1-.45 1-1v-1H9v1zm3-19C9.24 2 7 4.24 7 7c0 2.05 1.23 3.81 3 4.58V13c0 .55.45 1 1 1h2c.55 0 1-.45 1-1v-1.42c1.77-.77 3-2.53 3-4.58 0-2.76-2.24-5-5-5z"/></svg>""",
    "power-plug": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#666"><path d="M16 7V3h-2v4h-4V3H8v4C7 7 6 8 6 9v5.5c0 1.38.93 2.54 2.22 2.88L10 19.11V21c0 .55.45 1 1 1h2c.55 0 1-.45 1-1v-1.89l1.78-1.73c1.29-.34 2.22-1.5 2.22-2.88V9c0-1-1-2-2-2z"/></svg>""",
    "lock": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#c0392b"><path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1s3.1 1.39 3.1 3.1v2z"/></svg>""",
    "thermometer": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#e67e22"><path d="M15 13V5c0-1.66-1.34-3-3-3S9 3.34 9 5v8c-1.21.91-2 2.21-2 3.67C7 18.45 8.55 20 10.33 20c1.12 0 2.1-.6 2.67-1.5.57.9 1.55 1.5 2.67 1.5 1.78 0 3.33-1.55 3.33-3.33 0-1.46-.79-2.76-2-3.67z"/></svg>""",
    "camera-web": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#666"><path d="M12 18c-3.31 0-6-2.69-6-6s2.69-6 6-6 6 2.69 6 6-2.69 6-6 6zm0-10c-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4-1.79-4-4-4z"/><path d="M9 2L7.17 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2h-3.17L15 2H9z"/></svg>""",
    "fan": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#666"><path d="M12.5 2C9.85 2 7.45 3.18 6.05 5.12c-.45.63.05 1.51.88 1.51.33 0 .64-.17.82-.46 1.09-1.68 2.88-2.69 4.87-2.7 2.06 0 3.9 1.08 4.93 2.71.33.52 1.04.67 1.56.34.52-.33.67-1.04.34-1.56C17.5 3.14 15.2 2 12.5 2zM10.5 7.12c-.97.09-1.86.53-2.53 1.17-.36.34-.08.96.42.96.25 0 .48-.1.66-.28.29-.29.67-.47 1.07-.47.84 0 1.48.7 1.4 1.52-.05.4-.25.76-.55 1.01L5.3 14.23c-.58.48-.3 1.41.45 1.41.32 0 .63-.13.84-.36l3.87-4.08c.2-.2.47-.32.75-.32.59 0 1.06.47 1.06 1.06v.01c0 .59-.47 1.06-1.06 1.06h-4.6c-.76 0-1.37.62-1.37 1.38 0 .47.24.9.62 1.14 1.03.67 2.24 1.03 3.49.93.26-.02.52 0 .77.05.99.21 1.79.86 2.2 1.72l-3.05 5.2c-.34.59.11 1.34.78 1.34.28 0 .54-.14.69-.38l3.12-5.34c.3-.52.97-.7 1.5-.4.19.11.33.29.4.49.21.58.66 1.05 1.24 1.26.93.33 1.96-.17 2.29-1.1.21-.58.16-1.2-.12-1.73-.14-.26-.33-.49-.56-.67l4.97-4.26c.58-.48.3-1.41-.45-1.41-.32 0-.63.13-.84.36L16 12.52c-.17.19-.4.3-.66.3-.5 0-.9-.4-.9-.9 0-.48.38-.87.85-.9l4.67-.26c.76-.04 1.36-.68 1.32-1.44-.03-.68-.55-1.23-1.22-1.24-1.05-.01-2.1.14-3.08.44-.28.08-.57.13-.87.13-1.06 0-2.01-.5-2.61-1.33-.22-.3-.38-.64-.44-1-.06-.34-.1-.68-.08-1.03.02-.45-.35-.82-.8-.82z"/></svg>""",
    "speaker": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#666"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/></svg>""",
    "television": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#666"><path d="M21 3H3c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h5v2h8v-2h5c1.1 0 1.99-.9 1.99-2L23 5c0-1.1-.9-2-2-2zm0 14H3V5h18v12z"/></svg>""",
    "motion-sensor": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#666"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z"/><circle cx="12" cy="12" r="2"/></svg>""",
    "robot-vacuum": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#666"><path d="M12 2C8.69 2 6 4.69 6 8v2c-1.1 0-2 .9-2 2v4c0 1.1.9 2 2 2h1v2c0 1.1.9 2 2 2h6c1.1 0 2-.9 2-2v-2h1c1.1 0 2-.9 2-2v-4c0-1.1-.9-2-2-2V8c0-3.31-2.69-6-6-6zm0 2c2.21 0 4 1.79 4 4v2H8V8c0-2.21 1.79-4 4-4zm0 8c1.1 0 2 .9 2 2s-.9 2-2 2-2-.9-2-2 .9-2 2-2z"/></svg>""",
    "garage": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#666"><path d="M19 6.41L12 2 5 6.41V19h2v-7h10v7h2V6.41zM13 10H9V8h4v2zm2 0h-1V8h1v2z"/></svg>""",
    "door": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#8B4513"><path d="M18 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-5 11c-.55 0-1-.45-1-1s.45-1 1-1 1 .45 1 1-.45 1-1 1zm4 7H7V4h10v16z"/></svg>""",
    "blinds": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#666"><path d="M20 19V3H4v16H2v2h20v-2h-2zM18 5v6H6V5h12zm0 8v2H6v-2h12zM6 19v-2h12v2H6z"/></svg>""",
    "air-filter": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#3498db"><path d="M21 7h-1V6h-2v1h-1c-.55 0-1 .45-1 1v1c0 .55.45 1 1 1h1v1h2v-1h1c.55 0 1-.45 1-1V8c0-.55-.45-1-1-1zM10 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2v-6h-2v6H4V6h6V4z"/></svg>""",
    "bell-ring": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#666"><path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.89 2 2 2zm6-6v-5c0-3.07-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z"/></svg>""",
    "water": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#3498db"><path d="M12 2c-5.33 4.55-8 8.48-8 11.8 0 4.98 3.8 8.2 8 8.2s8-3.22 8-8.2c0-3.32-2.67-7.25-8-11.8z"/></svg>""",
    "alarm-light": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#e74c3c"><path d="M12 1l-4 8h8l-4-8zm0 14c-1.1 0-2 .9-2 2h4c0-1.1-.9-2-2-2zm-5 4h10v2H7v-2z"/></svg>""",
    "chip": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#666"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V5h14v14z"/><path d="M7 7h10v10H7z"/></svg>""",
    "run": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#27ae60"><path d="M13.5 5.5c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zM9.5 15l-3.87 4H3l3.5-4.5 1.5-3-2-4L9 6l3 4 4-1 3 7h-2l-2.5-5-1.5 2.5L13.5 18H20v2H11l-1.5-5z"/></svg>""",
    "smoke-detector": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#e74c3c"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-7 15c-3.31 0-6-2.69-6-6s2.69-6 6-6 6 2.69 6 6-2.69 6-6 6z"/><circle cx="12" cy="12" r="4"/></svg>""",
    "calendar": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#666"><path d="M19 3h-1V1h-2v2H8V1H6v2H5c-1.11 0-1.99.9-1.99 2L3 19c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V8h14v11z"/><path d="M7 10h5v5H7z"/></svg>""",
    "alert": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#e74c3c"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>""",
    "questionmark-circle": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#999"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H8c0-2.21 1.79-4 4-4s4 1.79 4 4c0 .88-.36 1.68-.93 2.25z"/></svg>""",
    "overview": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#666"><path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z"/></svg>""",
    "shape": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#666"><path d="M18 4l2 4h-3l2-4h-1zm-2 8l3-5 3 5h-6zm-2-2l-5 10h10L14 10zM4 10h4v10H4V10z"/></svg>""",
    "puzzle": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#8e44ad"><path d="M20 10V8c0-1.1-.9-2-2-2h-2c0-1.66-1.34-3-3-3S10 4.34 10 6H8c-1.1 0-2 .9-2 2v2c-1.66 0-3 1.34-3 3s1.34 3 3 3v2c0 1.1.9 2 2 2h2c0 1.66 1.34 3 3 3s3-1.34 3-3h2c1.1 0 2-.9 2-2v-2c1.66 0 3-1.34 3-3s-1.34-3-3-3z"/></svg>""",
    "script-text": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#666"><path d="M5 3c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2H5zm12 14H7v-2h10v2zm0-4H7v-2h10v2zm0-4H7V7h10v2z"/></svg>""",
    "brightness-5": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#f39c12"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg>""",
    "dots-square": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#666"><path d="M5 3h14c1.1 0 2 .9 2 2v14c0 1.1-.9 2-2 2H5c-1.1 0-2-.9-2-2V5c0-1.1.9-2 2-2zm2 8h2v2H7v-2zm4 0h2v2h-2v-2zm4 0h2v2h-2v-2z"/></svg>""",
}

_CACHE: dict[str, QIcon] = {}


def get_icon(symbol_name: str) -> QIcon:
    name = symbol_name or "questionmark-circle"
    if name not in _CACHE:
        svg = _SVGS.get(name)
        if svg is None:
            svg = _SVGS["questionmark-circle"]
        pm = QPixmap(_ICON_SIZE, _ICON_SIZE)
        pm.fill(Qt.transparent)
        pm.loadFromData(svg.encode("utf-8"))
        _CACHE[name] = QIcon(pm)
    return _CACHE[name]
