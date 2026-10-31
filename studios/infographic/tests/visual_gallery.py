"""Render synthetic examples through the production compositor, without providers."""

import argparse
import json
import os
from pathlib import Path
import tempfile
from unittest import mock

from test_visual_pages import project
from runner import evidence, render, scene, sources, stories, svg
from runner.workspace import Store


def overview(store):
    p = project(store)
    original = p["facts"]
    raw = b"Sample completed 128 checks. Period: 2026-01-01. Denominator: per sample. Conditions: synthetic workload. Uncertainty: not reported."
    p = sources.capture(
        store, p["id"], raw, expected_revision=store.read(p["id"])["revision"]
    )
    fact = {
        "id": "f_metric",
        "statement": "Checks completed",
        "value": 128,
        "unit": "checks",
        "period": "2026-01-01",
        "denominator": "per sample",
        "conditions": "synthetic workload",
        "uncertainty": "not reported",
        "status": "supplied",
        "evidence": [
            {
                "source_id": p["sources"][-1]["id"],
                "quote": "Sample completed 128 checks",
            }
        ],
    }
    facts = evidence.locate(store, p, original + [fact])
    p = evidence.adopt(store, p["id"], facts, expected_revision=p["revision"])
    p["brief"]["preset"] = "digital"
    base = project_story(p)
    p["stories"] = stories.verify(p, [base])
    p["selected_story"] = "overview"
    return p


def project_story(p):
    blocks = []
    for i, (title, labels, icons, kind) in enumerate(
        [
            (
                "Collect and analyse",
                ["Collect events", "Correlate events"],
                ["server", "network"],
                "process",
            ),
            (
                "Review before response",
                ["Review findings", "Contain threats"],
                ["users", "shield"],
                "process",
            ),
        ]
    ):
        ids = ["f" + str(i * 2 + j) for j in range(2)]
        nodes = [
            {
                "id": "n" + str(j),
                "label": label,
                "caption": "",
                "icon": icon,
                "fact_ids": [key],
            }
            for j, (label, icon, key) in enumerate(zip(labels, icons, ids))
        ]
        blocks.append(
            {
                "id": "b" + str(i),
                "kind": kind,
                "quantitative": False,
                "title": title,
                "text": "Follow the supplied sequence."
                if i == 0
                else "Keep approval visible before action.",
                "fact_ids": ids,
                "required_ids": [],
                "illustration": False,
                "illustration_role": "",
                "visual": {
                    "nodes": nodes,
                    "links": [{"from": "n0", "to": "n1", "label": "", "fact_ids": ids}],
                },
            }
        )
    blocks.append(
        {
            "id": "metric",
            "kind": "numbers",
            "quantitative": True,
            "title": "Example workload",
            "text": "A supplied test count, with its scope preserved.",
            "fact_ids": ["f_metric"],
            "required_ids": [],
            "illustration": False,
            "illustration_role": "",
            "visual": None,
        }
    )
    return {
        "id": "overview",
        "headline": "From events to approved action",
        "takeaway": "Make the response path clear at a glance.",
        "rationale": "A visual flow and source-exact callout.",
        "qualifications": [],
        "omissions": [],
        "blocks": blocks,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--renderer", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="infographic-visual-gallery-") as folder:
        root = Path(folder).resolve()
        home = root / "home"
        home.mkdir()
        with mock.patch.dict(
            os.environ,
            {
                "HOME": str(home),
                "PATH": os.environ.get("PATH", ""),
                "INFOGRAPHIC_STUDIO_DATA": str(root / "data"),
                "STUDIOS_CONFIG": str(root / "settings.json"),
                "STUDIOS_LIBRARY": str(root / "library"),
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_CONFIG_NOSYSTEM": "1",
            },
            clear=True,
        ):
            store = Store.setup(root / "work")
            for name in ("process", "parts", "comparison", "overview"):
                p = overview(store) if name == "overview" else project(store, name)
                p["scene"] = scene.plan(p, arrangement="infographic")
                render.render(
                    svg.compose(store, p, draft=True),
                    preset=p["brief"]["preset"],
                    fonts=[p["brand"]["font"]],
                    executable=args.renderer,
                    destination=args.output / name,
                )
    print(json.dumps({"rendered": 4, "providers_called": False}))


if __name__ == "__main__":
    main()
