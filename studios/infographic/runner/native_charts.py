"""Readable source-exact numeric marks for visual infographic layouts."""

import xml.etree.ElementTree as ET
from .scene import wrapped


def draw(parent, element, colors):
    x, y, width, _ = element["bounds"]
    size = element["font_size"]
    cursor = y
    values = element["values"]
    form = element["form"]
    maximum = (sum(values) if form == "parts" else max(values)) or 1
    offset = 0

    def words(value, top, font_size, color):
        lines = wrapped(value, width, font_size)
        node = ET.SubElement(
            parent,
            "text",
            {
                "x": str(x),
                "y": str(top + font_size),
                "font-family": element["font"],
                "font-size": str(font_size),
                "fill": color,
                "aria-label": value,
            },
        )
        for i, line in enumerate(lines):
            ET.SubElement(
                node, "tspan", {"x": str(x), "y": str(top + font_size * (1 + i * 1.4))}
            ).text = line
        return len(lines) * font_size * 1.4

    if form == "parts":
        palette = [
            colors.get(key, element["color"])
            for key in (
                "headingPrimary",
                "inkDeep",
                "accentAqua",
                "accentPurple",
                "accentAzure",
            )
        ]
        for i, value in enumerate(values):
            length = width * value / maximum
            ET.SubElement(
                parent,
                "rect",
                {
                    "x": str(x + offset),
                    "y": str(cursor),
                    "width": str(length),
                    "height": str(size * 0.7),
                    "fill": palette[i % len(palette)],
                },
            )
            offset += length
        cursor += size * 1.1
    for label, literal, value in zip(
        element["labels"], element["display_values"], values
    ):
        cursor += words(label, cursor, size, colors["inkPrimary"])
        if form == "numbers":
            cursor += (
                words(
                    literal + " " + element["unit"],
                    cursor,
                    size * element.get("value_scale", 1.65),
                    element["color"],
                )
                + size * 0.15
            )
        else:
            cursor += words(
                literal + " " + element["unit"], cursor, size, element["color"]
            )
            if form != "parts":
                ET.SubElement(
                    parent,
                    "rect",
                    {
                        "x": str(x),
                        "y": str(cursor),
                        "width": str(width * value / maximum),
                        "height": str(size * 0.45),
                        "fill": element["color"],
                    },
                )
            cursor += size * 0.6
