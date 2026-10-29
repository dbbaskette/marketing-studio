"""Small original vector pictograms. Illustrative symbols, never product identities."""

import xml.etree.ElementTree as ET

PATHS = {
    "layers": "M3 7 12 3 21 7 12 11Z M3 12 12 16 21 12 M3 17 12 21 21 17",
    "server": "M4 3H20V10H4Z M4 14H20V21H4Z M7 6H8 M7 17H8 M12 6H17 M12 17H17",
    "cloud": "M6 18H18C23 18 23 10 18 10C18 3 7 2 6 10C0 10 1 18 6 18Z",
    "database": "M3 6C3 1 21 1 21 6C21 11 3 11 3 6Z M3 6V18C3 23 21 23 21 18V6 M3 12C3 17 21 17 21 12",
    "shield": "M12 2 21 6 19 16 12 22 5 16 3 6Z M8 12 11 15 17 9",
    "lock": "M5 10H19V21H5Z M8 10V6C8 1 16 1 16 6V10 M12 14V17",
    "document": "M5 2H15L20 7V22H5Z M14 2V8H20 M8 12H17 M8 16H17 M8 19H14",
    "code": "M8 5 2 12 8 19 M16 5 22 12 16 19 M14 3 10 21",
    "users": "M8 10A3 3 0 1 0 8 4A3 3 0 1 0 8 10 M16 10A3 3 0 1 0 16 4A3 3 0 1 0 16 10 M2 21V17C2 11 14 11 14 17V21 M16 13C20 13 22 15 22 18V21",
    "network": "M9 3H15V9H9Z M2 16H8V22H2Z M16 16H22V22H16Z M12 9V13H5V16 M12 13H19V16",
    "cycle": "M20 9A8 8 0 0 0 5 6L2 9 M2 3V9H8 M4 15A8 8 0 0 0 19 18L22 15 M16 15H22V21",
    "check": "M3 12 9 18 21 5",
    "chart": "M3 3V21H22 M7 16V11 M13 16V7 M19 16V4",
}


def draw(parent, ns, glyph, bounds, color):
    x, y, width, height = bounds
    # Pad strokes so the icon's actual painted shape stays inside its reservation.
    group = ET.SubElement(
        parent,
        "g",
        {
            "transform": f"translate({x + width * 0.08} {y + height * 0.08}) scale({width * 0.84 / 24} {height * 0.84 / 24})"
        },
    )
    ET.SubElement(
        group,
        "path",
        {"d": PATHS[glyph], "fill": "none", "stroke": color, "stroke-width": "1.6"},
    )
