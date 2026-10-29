"""Editable visual explanations with explicit information-bearing diagrams."""

from copy import deepcopy

from . import brand, evidence, visuals
from .contracts import PRESETS, Invalid, digest
from .scene import wrapped
from .validation import require, validate_project


def tint(ink, canvas, fraction=0.07):
    return "#" + "".join(
        f"{round(int(ink[i : i + 2], 16) * fraction + int(canvas[i : i + 2], 16) * (1 - fraction)):02x}"
        for i in (1, 3, 5)
    )


def element_id(value):
    """Model IDs are bounded individually; composed IDs must stay bounded too."""
    return value if len(value) <= 64 else "v_" + digest(value)[:24]


def plan(project, *, body_size=None):
    require(
        project["brand"] is not None,
        "Select a pinned brand before composing the infographic.",
    )
    story = next(
        (s for s in project["stories"] if s["id"] == project["selected_story"]), None
    )
    require(
        story is not None and not story.get("omissions"),
        "Choose a story with all required ideas first.",
    )
    size = PRESETS[project["brief"]["preset"]]
    width, height, digital = size["width"], size["height"], size["unit"] == "px"
    body, foot = brand.type_floors(project["brand"], digital)
    if body_size is None:
        count = len(
            (
                " ".join(
                    [
                        story["headline"],
                        story["takeaway"],
                        *(b["title"] + " " + b["text"] for b in story["blocks"]),
                    ]
                )
            ).split()
        )
        preferred = (
            (40 if count < 80 else 32) if digital else (16 if count < 80 else 14)
        )
        failure = None
        for chosen in dict.fromkeys(
            (max(body, preferred), max(body, 32 if digital else 14), body)
        ):
            try:
                return plan(project, body_size=chosen)
            except Invalid as problem:
                failure = problem
        raise failure
    body = max(body, body_size)
    font, colors = project["brand"]["font"], project["brand"]["colors"]
    ink, accent, canvas = (
        colors["inkPrimary"],
        colors["headingPrimary"],
        colors["canvasPrimary"],
    )
    surface = tint(accent, canvas)
    margin, gap = width * 0.05, body * 0.85
    usable = width - margin * 2
    elements, regions, reading = [], [], []
    facts = {f["id"]: f for f in project["facts"]}

    def words(
        ident,
        value,
        x,
        y,
        w,
        font_size=body,
        *,
        color=ink,
        role="body",
        block=None,
        refs=(),
        background=canvas,
        weight=400,
        min_lines=1,
    ):
        ident = element_id(ident)
        lines = wrapped(value, w, font_size)
        h = max(min_lines, len(lines)) * font_size * 1.4
        elements.append(
            {
                "id": ident,
                "kind": "text",
                "text": value,
                "lines": lines,
                "font": font,
                "font_size": font_size,
                "bounds": [x, y, w, h],
                "color": color,
                "role": role,
                "block_id": block,
                "fact_ids": list(refs),
                "background": background,
                "weight": weight,
            }
        )
        reading.append(ident)
        return h

    def shape(ident, x, y, w, h, *, color=surface, glyph=None, refs=(), block=None):
        ident = element_id(ident)
        node = {
            "id": ident,
            "kind": "shape",
            "bounds": [x, y, w, h],
            "color": color,
            "radius": body * 0.45,
            "fact_ids": list(refs),
            "block_id": block,
        }
        if glyph:
            node.update(glyph=glyph, alt="Illustrative " + glyph + " symbol")
        elements.append(node)
        return node

    def link(
        ident,
        start,
        end,
        *,
        arrow=False,
        refs=(),
        block=None,
        meaning="Grouped components; no measured flow.",
    ):
        ident = element_id(ident)
        # Include arrowheads in their measurable reservation, including reverse/diagonal links.
        pad = body * 0.4
        x, y = max(0, min(start[0], end[0]) - pad), max(0, min(start[1], end[1]) - pad)
        w, h = max(start[0], end[0]) - x + pad, max(start[1], end[1]) - y + pad
        elements.append(
            {
                "id": ident,
                "kind": "connector",
                "bounds": [x, y, w, h],
                "points": [list(start), list(end)],
                "color": accent,
                "stroke_width": max(1, body * 0.08),
                "arrow": arrow,
                "arrow_size": body * 0.3,
                "fact_ids": list(refs),
                "block_id": block,
                "meaning": meaning,
            }
        )
        reading.append(ident)

    # A typographic header and accent rule; the explanatory graphics own the page below.
    y = margin
    y += (
        words(
            "headline",
            story["headline"],
            margin,
            y,
            usable,
            body * 2,
            color=accent,
            role="heading",
            weight=700,
        )
        + gap * 0.5
    )
    y += (
        words("takeaway", story["takeaway"], margin, y, usable, body * 1.1, weight=600)
        + gap
    )
    shape("page_rule", margin, y, usable, body * 0.16, color=accent)
    y += gap
    footer = "Supplied sources: " + "; ".join(
        s.get("name", "Source") for s in project["sources"]
    )
    if story.get("qualifications"):
        footer += ". " + " ".join(story["qualifications"])
    footer_h = len(wrapped(footer, usable, foot)) * foot * 1.4
    bottom = height - margin - footer_h - gap
    blocks = story["blocks"]

    def block_metrics(block, w):
        inside = w - body * 1.5
        heading_h = (
            max(2, len(wrapped(block["title"], inside - body * 2, body * 1.15)))
            * body
            * 1.15
            * 1.4
        )
        caption_h = len(wrapped(block["text"], inside, body)) * body * 1.4
        numeric = evidence.quantitative(
            block, [facts[key] for key in block["fact_ids"]]
        )
        meta = {"heading": heading_h, "caption": caption_h, "numeric": numeric}
        if numeric:
            used = [facts[key] for key in block["fact_ids"]]
            evidence.comparable(used)
            context = "; ".join(used[0][key] for key in evidence.CONTEXT)
            context_h = len(wrapped(context, inside, foot)) * foot * 1.4
            # Measured rows need exact values, readable labels and a zero baseline.
            chart_h = sum(
                len(wrapped(f["statement"], inside, body)) * body * 1.4
                + (
                    len(
                        wrapped(
                            f.get("literal", str(f["value"])) + " " + f["unit"],
                            inside,
                            body * 1.65,
                        )
                    )
                    * body
                    * 1.65
                    * 1.4
                    + body * 0.15
                    if block["kind"] == "numbers"
                    else body * 2
                )
                for f in used
            )
            if block["kind"] == "parts":
                chart_h += body * 1.1
            meta.update(chart_h=chart_h, context=context, context_h=context_h)
            visual_h = chart_h + context_h + gap * 0.5
        else:
            nodes = deepcopy(visuals.nodes(block, facts))
            if block["kind"] == "timeline":
                for node in nodes:
                    periods = list(
                        dict.fromkeys(facts[key]["period"] for key in node["fact_ids"])
                    )
                    node["caption"] = " · ".join(periods) + (
                        " · " + node["caption"] if node.get("caption") else ""
                    )
            require(
                1 <= len(nodes) <= 4,
                "Prioritize at most four visual items per section before composing.",
            )
            cols = (
                min(len(nodes), 3)
                if inside >= body * 27
                else min(len(nodes), 2)
                if inside >= body * 18
                else 1
            )
            nw = (inside - gap * (cols - 1)) / cols
            rows = []
            for i in range(0, len(nodes), cols):
                heights = []
                for node in nodes[i : i + cols]:
                    label_h = (
                        max(2, len(wrapped(node["label"], nw - body, body)))
                        * body
                        * 1.4
                    )
                    caption = node.get("caption", "")
                    detail_h = (
                        len(wrapped(caption, nw - body, body)) * body * 1.4
                        if caption
                        else 0
                    )
                    heights.append(body * 3.1 + label_h + detail_h)
                rows.append(max(heights))
            visual_h = sum(rows) + gap * (len(rows) - 1)
            for edge in (block.get("visual") or {}).get("links", []):
                if edge.get("label"):
                    visual_h += (
                        len(wrapped(edge["label"], inside, body)) * body * 1.4
                        + gap * 0.3
                    )
            meta.update(nodes=nodes, node_cols=cols, node_width=nw, node_rows=rows)
        if block["illustration"]:
            visual_h += body * 4 + gap
        meta["minimum"] = body * 1.5 + heading_h + caption_h + visual_h + gap * 2
        return meta

    candidates = []
    sequential = all(b["kind"] in ("process", "timeline") for b in blocks)
    for cols in [2, 1] if len(blocks) >= 3 and not sequential else [1, 2]:
        if cols == 2 and len(blocks) < 2:
            continue
        bw = (usable - gap * (cols - 1)) / cols
        try:
            metrics = [
                dict(
                    block_metrics(
                        b,
                        usable
                        if cols == 2 and len(blocks) % 2 and i == len(blocks) - 1
                        else bw,
                    ),
                    width=usable
                    if cols == 2 and len(blocks) % 2 and i == len(blocks) - 1
                    else bw,
                )
                for i, b in enumerate(blocks)
            ]
            rows = [
                max(m["minimum"] for m in metrics[i : i + cols])
                for i in range(0, len(blocks), cols)
            ]
        except Invalid:
            continue
        if sum(rows) + gap * (len(rows) - 1) <= bottom - y:
            candidates.append((cols, bw, metrics, rows))
            break
    require(
        bool(candidates),
        "The visual story is too dense for a readable infographic. Shorten captions or combine ideas; text was not shrunk or discarded.",
    )
    cols, column_width, metrics, rows = candidates[0]
    extra = (bottom - y - sum(rows) - gap * (len(rows) - 1)) / len(rows)
    row_tops = []
    cursor = y
    for rh in rows:
        row_tops.append(cursor)
        cursor += rh + extra + gap
    for index, (block, meta) in enumerate(zip(blocks, metrics)):
        bw = meta["width"]
        bid = block["id"]
        x = margin + (index % cols) * (column_width + gap)
        top = row_tops[index // cols]
        bh = rows[index // cols] + extra
        spare = max(0, bh - meta["minimum"])
        pad = body * 0.75
        inside = bw - pad * 2
        shape(bid + "_panel", x, top, bw, bh, block=bid)
        shape(
            bid + "_symbol",
            x + pad,
            top + pad,
            body * 1.5,
            body * 1.5,
            color=accent,
            glyph=visuals.icon_for(block["title"] + " " + block["text"]),
            refs=block["fact_ids"],
            block=bid,
        )
        cursor = top + pad
        cursor += (
            words(
                bid + "_heading",
                block["title"],
                x + pad + body * 2,
                cursor,
                inside - body * 2,
                body * 1.15,
                color=accent,
                role="heading",
                refs=block["fact_ids"],
                block=bid,
                background=surface,
                weight=700,
                min_lines=2,
            )
            + gap * 0.5
        )
        cursor += (
            words(
                bid + "_text",
                block["text"],
                x + pad,
                cursor,
                inside,
                refs=block["fact_ids"],
                block=bid,
                background=surface,
            )
            + gap
        )
        if meta["numeric"]:
            used = [facts[key] for key in block["fact_ids"]]
            values = [f["value"] for f in used]
            require(
                block["kind"] == "numbers" or all(v >= 0 for v in values),
                "Use number callouts for signed values.",
            )
            chart_height = meta["chart_h"]
            value_scale = 1.65
            if block["kind"] == "numbers":
                for scale in (3.2, 2.4, 1.65):
                    desired = sum(
                        len(wrapped(f["statement"], inside, body)) * body * 1.4
                        + len(
                            wrapped(
                                f.get("literal", str(f["value"])) + " " + f["unit"],
                                inside,
                                body * scale,
                            )
                        )
                        * body
                        * scale
                        * 1.4
                        + body * 0.15
                        for f in used
                    )
                    if desired <= chart_height + spare * (
                        0.4 if block["illustration"] else 1
                    ):
                        chart_height, value_scale = desired, scale
                        break
            elements.append(
                {
                    "id": element_id(bid + "_chart"),
                    "kind": "chart",
                    "bounds": [x + pad, cursor, inside, chart_height],
                    "values": values,
                    "fact_ids": block["fact_ids"],
                    "unit": used[0]["unit"],
                    "display_values": [f.get("literal", str(f["value"])) for f in used],
                    "labels": [f["statement"] for f in used],
                    "baseline": 0,
                    "form": block["kind"],
                    "color": accent,
                    "font": font,
                    "font_size": body,
                    "block_id": bid,
                    "visual": True,
                    "value_scale": value_scale,
                }
            )
            reading.append(element_id(bid + "_chart"))
            cursor += chart_height + gap * 0.5
            cursor += words(
                bid + "_context",
                meta["context"],
                x + pad,
                cursor,
                inside,
                foot,
                refs=block["fact_ids"],
                block=bid,
                background=surface,
                role="source",
            )
        else:
            nodes = meta["nodes"]
            nc = meta["node_cols"]
            nw = meta["node_width"]
            positions = {}
            node_extra = (
                spare * (0.4 if block["illustration"] else 1) / len(meta["node_rows"])
            )
            node_rows = [h + node_extra for h in meta["node_rows"]]
            node_top = cursor
            # Draw supported relationships behind the object panels, not over labels.
            slots = []
            for i, node in enumerate(nodes):
                if i and i % nc == 0:
                    node_top += node_rows[i // nc - 1] + gap
                column = (
                    nc - 1 - i % nc
                    if block["kind"] in ("process", "timeline") and (i // nc) % 2
                    else i % nc
                )
                nx = x + pad + column * (nw + gap)
                nh = node_rows[i // nc]
                positions[node["id"]] = (nx, node_top, nw, nh)
                slots.append((node, nx, node_top, nh))
            links = (block.get("visual") or {}).get("links", [])
            if not links and block["kind"] in ("process", "timeline"):
                links = [
                    {
                        "from": a["id"],
                        "to": b["id"],
                        "label": "",
                        "fact_ids": list(dict.fromkeys(a["fact_ids"] + b["fact_ids"])),
                    }
                    for a, b in zip(nodes, nodes[1:])
                ]
            # Component maps show membership with a shared rail, not invented causal arrows.
            if block["kind"] == "parts" and not links and len(nodes) > 1:
                if nc == 2 and len(nodes) > 2:
                    hub = (x + bw / 2, cursor + node_rows[0] + gap / 2)
                    for i, (_, nx, ny, nh) in enumerate(slots):
                        edge = (
                            nx + nw if nx < hub[0] else nx,
                            ny + nh if ny < hub[1] else ny,
                        )
                        link(
                            bid + "_member_" + str(i),
                            hub,
                            edge,
                            refs=nodes[i]["fact_ids"],
                            block=bid,
                        )
                    shape(
                        bid + "_hub",
                        hub[0] - body * 0.3,
                        hub[1] - body * 0.3,
                        body * 0.6,
                        body * 0.6,
                        color=accent,
                        block=bid,
                    )
                else:
                    rail_y = cursor - body * 0.25
                    centers = [(nx + nw / 2, ny) for _, nx, ny, _ in slots]
                    link(
                        bid + "_membership",
                        (centers[0][0], rail_y),
                        (centers[-1][0], rail_y),
                        refs=block["fact_ids"],
                        block=bid,
                    )
                    for i, point in enumerate(centers):
                        link(
                            bid + "_member_" + str(i),
                            (point[0], rail_y),
                            point,
                            refs=nodes[i]["fact_ids"],
                            block=bid,
                        )
            for i, edge in enumerate(links):
                a, b = positions[edge["from"]], positions[edge["to"]]
                if abs(a[1] - b[1]) < 0.01:
                    start = (a[0] + (a[2] if b[0] > a[0] else 0), a[1] + body)
                    end = (b[0] + (0 if b[0] > a[0] else b[2]), b[1] + body)
                else:
                    start = (a[0] + a[2] / 2, a[1] + a[3])
                    end = (b[0] + b[2] / 2, b[1])
                link(
                    bid + "_link_" + str(i),
                    start,
                    end,
                    arrow=True,
                    refs=edge["fact_ids"],
                    block=bid,
                    meaning=edge.get("label")
                    or "Supplied " + block["kind"] + " relationship",
                )
            for i, (node, nx, ny, nh) in enumerate(slots):
                nodeid = bid + "_node_" + node["id"]
                refs = node["fact_ids"]
                shape(
                    nodeid + "_panel",
                    nx,
                    ny,
                    nw,
                    nh,
                    color=canvas,
                    refs=refs,
                    block=bid,
                )
                icon = min(body * 3.5, body * 1.9 + node_extra * 0.4, nw - body)
                label_h = (
                    max(2, len(wrapped(node["label"], nw - body, body))) * body * 1.4
                )
                detail_h = (
                    len(wrapped(node["caption"], nw - body, body)) * body * 1.4
                    if node.get("caption")
                    else 0
                )
                icon_y = ny + max(
                    body * 0.3, (nh - icon - body * 0.3 - label_h - detail_h) / 2
                )
                shape(
                    nodeid + "_icon",
                    nx + (nw - icon) / 2,
                    icon_y,
                    icon,
                    icon,
                    color=accent,
                    glyph=node["icon"],
                    refs=refs,
                    block=bid,
                )
                text_y = icon_y + icon + body * 0.3
                text_y += words(
                    nodeid + "_label",
                    node["label"],
                    nx + body * 0.5,
                    text_y,
                    nw - body,
                    refs=refs,
                    block=bid,
                    weight=650,
                    min_lines=2,
                )
                if node.get("caption"):
                    words(
                        nodeid + "_caption",
                        node["caption"],
                        nx + body * 0.5,
                        text_y,
                        nw - body,
                        refs=refs,
                        block=bid,
                    )
            cursor = node_top + node_rows[-1]
            for i, edge in enumerate(links):
                if edge.get("label"):
                    cursor += gap * 0.3
                    cursor += words(
                        bid + "_relationship_" + str(i),
                        edge["label"],
                        x + pad,
                        cursor,
                        inside,
                        refs=edge["fact_ids"],
                        block=bid,
                        background=surface,
                    )
        if block["illustration"]:
            cursor += gap
            ah = top + bh - pad - cursor
            require(
                ah >= body * 3, "Reserve enough space for the explanatory illustration."
            )
            regions.append(
                {
                    "id": element_id(bid + "_art"),
                    "block_id": bid,
                    "bounds": [x + pad, cursor, inside, ah],
                    "role": block["illustration_role"],
                    "fit": "contain",
                    "asset_id": None,
                }
            )
            reading.append(element_id(bid + "_art"))
        require(
            cursor <= top + bh - pad + 0.01,
            "The diagram needs shorter labels or fewer visual items.",
        )
    words(
        "sources",
        footer,
        margin,
        height - margin - footer_h,
        usable,
        foot,
        role="source",
    )
    result = {
        "id": "scene_"
        + digest(
            {
                "story": story,
                "brand": project["brand"]["sha256"],
                "preset": project["brief"]["preset"],
                "visual_version": 1,
            }
        )[:20],
        **{key: size[key] for key in ("width", "height", "unit")},
        "elements": elements,
        "art_regions": regions,
        "reading_order": reading,
        "arrangement": "infographic",
        "background": canvas,
        "visual_version": 1,
    }
    candidate = deepcopy(project)
    candidate.update(
        scene=result, image_briefs=[], attempts=[], checks=[], approval=None
    )
    validate_project(candidate)
    return result
