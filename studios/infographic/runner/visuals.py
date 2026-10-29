"""Small evidence-linked visual vocabulary, independent of image providers."""

ICONS = (
    "layers",
    "server",
    "cloud",
    "database",
    "shield",
    "lock",
    "document",
    "code",
    "users",
    "network",
    "cycle",
    "check",
    "chart",
)


def validate(block):
    from .validation import records, references, require, text

    visual = block.get("visual")
    if visual is None:
        return []  # Saved proposals remain readable; rebuild supplies a native diagram.
    require(
        isinstance(visual, dict) and set(visual) == {"nodes", "links"},
        "A visual explanation needs nodes and explicitly supported links.",
    )
    nodes = records(visual["nodes"], "Visual nodes")
    require(1 <= len(nodes) <= 4, "Use one to four concise visual nodes per block.")
    words, covered = [], set()
    for node in nodes.values():
        require(
            set(node) == {"id", "label", "caption", "icon", "fact_ids"}
            and text(node["label"], limit=150)
            and len(node["label"].split()) <= 8
            and text(node["caption"], empty=True, limit=300)
            and len(node["caption"].split()) <= 16
            and node["icon"] in ICONS,
            "Use short visual labels, captions and supported pictograms.",
        )
        references(node["fact_ids"], block["fact_ids"], "Visual node facts")
        require(bool(node["fact_ids"]), "Every visual node needs supplied evidence.")
        covered.update(node["fact_ids"])
        words.extend((node["label"], node["caption"]))
    require(
        isinstance(visual["links"], list) and len(visual["links"]) <= 6,
        "Keep the diagram to at most six supported relationships.",
    )
    for link in visual["links"]:
        require(
            isinstance(link, dict)
            and set(link) == {"from", "to", "label", "fact_ids"}
            and isinstance(link["from"], str)
            and isinstance(link["to"], str)
            and link["from"] in nodes
            and link["to"] in nodes
            and link["from"] != link["to"]
            and text(link["label"], empty=True, limit=100)
            and len(link["label"].split()) <= 6,
            "Connect existing distinct visual nodes with concise supported relationships.",
        )
        references(link["fact_ids"], block["fact_ids"], "Visual relationship facts")
        require(bool(link["fact_ids"]), "A relationship needs source evidence.")
        covered.update(link["fact_ids"])
        words.append(link["label"])
    require(
        set(block["fact_ids"]) <= covered,
        "Represent each selected fact in the visual explanation.",
    )
    return words


def icon_for(text):
    wording = text.casefold()
    for words, icon in (
        (("secur", "protect", "threat"), "shield"),
        (("database", "storage", "data service"), "database"),
        (("restart", "cycle", "refresh"), "cycle"),
        (("cloud",), "cloud"),
        (("server", "instance", "runtime"), "server"),
        (("code", "open source", "software"), "code"),
        (("user", "team", "people"), "users"),
        (("document", "report", "audit"), "document"),
        (("network", "connect", "router", "queue"), "network"),
    ):
        if any(word in wording for word in words):
            return icon
    return "layers"


def nodes(block, facts):
    if block.get("visual"):
        return block["visual"]["nodes"]
    return [
        {
            "id": "n_" + str(i),
            "label": facts[key]["statement"],
            "caption": "",
            "icon": icon_for(facts[key]["statement"] + " " + block["title"]),
            "fact_ids": [key],
        }
        for i, key in enumerate(dict.fromkeys(block["fact_ids"]))
    ]
