"""Infographics carry explanations in editable graphics, without a live provider."""

from copy import deepcopy
import os
import unittest

from helpers import Isolated
from runner import brand, evidence, scene, sources, stories, svg, render, checks
from runner.contracts import Invalid, PRESETS
from runner.workspace import Store
from test_composition import contract

TEST_RENDERER = os.environ.get("INFOGRAPHIC_STUDIO_TEST_RENDERER")


def project(store, kind="process", preset="digital", art=False):
    p = store.create("Explain detection and response")
    raw = "2026-01-01: endpoints collect events. 2026-01-02: analysis correlates events. 2026-01-03: responders review findings. 2026-01-04: approved actions contain threats."
    p = sources.capture(store, p["id"], raw.encode(), expected_revision=p["revision"])
    quotes = [
        "endpoints collect events",
        "analysis correlates events",
        "responders review findings",
        "approved actions contain threats",
    ]
    labels = [
        "Collect events",
        "Correlate events",
        "Review findings",
        "Contain threats",
    ]
    facts = [
        {
            "id": "f" + str(i),
            "statement": label,
            "value": quote,
            "unit": "",
            "status": "supplied",
            "period": "2026-01-0" + str(i + 1),
            "evidence": [{"source_id": p["sources"][0]["id"], "quote": quote}],
        }
        for i, (label, quote) in enumerate(zip(labels, quotes))
    ]
    p = evidence.adopt(
        store,
        p["id"],
        evidence.locate(store, p, facts),
        expected_revision=p["revision"],
    )
    p = brand.adopt(store, p["id"], contract(), expected_revision=p["revision"])
    p["brief"]["preset"] = preset
    nodes = [
        {
            "id": "n" + str(i),
            "label": label,
            "caption": "",
            "icon": icon,
            "fact_ids": ["f" + str(i)],
        }
        for i, (label, icon) in enumerate(
            zip(labels, ["server", "network", "users", "shield"])
        )
    ]
    links = (
        [
            {
                "from": a["id"],
                "to": b["id"],
                "label": "",
                "fact_ids": a["fact_ids"] + b["fact_ids"],
            }
            for a, b in zip(nodes, nodes[1:])
        ]
        if kind in ("process", "timeline")
        else []
    )
    proposal = {
        "id": "s1",
        "headline": "From events to action",
        "takeaway": "Keep the whole response path visible.",
        "rationale": "A source-backed visual explanation.",
        "qualifications": [],
        "omissions": [],
        "blocks": [
            {
                "id": "b1",
                "kind": kind,
                "quantitative": False,
                "title": "Detection and response",
                "text": "Collection, analysis, review and approved action.",
                "fact_ids": [f["id"] for f in facts],
                "required_ids": [],
                "illustration": art,
                "illustration_role": "Illustrate the endpoint subjects." if art else "",
                "visual": {"nodes": nodes, "links": links},
            }
        ],
    }
    p["stories"] = stories.verify(p, [proposal])
    p["selected_story"] = "s1"
    return p


class VisualPageTests(Isolated):
    def setUp(self):
        super().setUp()
        self.store = Store.setup(self.workspace, data=self.data)

    def test_qualitative_forms_have_real_graphics_and_editable_evidence_linked_labels(
        self,
    ):
        for kind in ("process", "timeline", "parts", "comparison", "concept"):
            p = project(self.store, kind)
            p["scene"] = scene.plan(p, arrangement="infographic")
            elements = p["scene"]["elements"]
            self.assertEqual(p["scene"]["arrangement"], "infographic")
            self.assertGreaterEqual(sum(bool(e.get("glyph")) for e in elements), 4)
            self.assertFalse(any(e["kind"] == "chart" for e in elements))
            self.assertEqual(
                {key for e in elements for key in e.get("fact_ids", [])},
                {"f0", "f1", "f2", "f3"},
            )
            if kind in ("process", "timeline", "parts"):
                self.assertTrue(any(e["kind"] == "connector" for e in elements))
            if kind in ("comparison", "concept"):
                self.assertFalse(
                    any(e.get("arrow") for e in elements),
                    "Unspecified comparisons cannot imply causality",
                )
            encoded = svg.compose(self.store, p)
            self.assertIn("Collect events", encoded)
            self.assertIn("<path", encoded)
            self.assertNotIn("<image", encoded)

    def test_visual_links_and_labels_cannot_escape_captured_fact_scope(self):
        p = project(self.store)
        for change in (
            "unknown-fact",
            "unknown-icon",
            "unbounded-label",
            "unknown-node",
        ):
            proposed = deepcopy(p["stories"])
            visual = proposed[0]["blocks"][0]["visual"]
            if change == "unknown-fact":
                visual["nodes"][0]["fact_ids"] = ["not_supplied"]
            if change == "unknown-icon":
                visual["nodes"][0]["icon"] = "remote_product_logo"
            if change == "unbounded-label":
                visual["nodes"][0]["label"] = "too many words " * 10
            if change == "unknown-node":
                visual["links"][0]["to"] = "not_a_node"
            with self.subTest(change=change), self.assertRaises(Invalid):
                stories.verify(p, proposed)

    def test_locked_words_in_visual_labels_are_preserved_in_the_actual_page(self):
        p = project(self.store)
        p["brief"]["locked_words"] = ["Collect events"]
        p["stories"] = stories.verify(p, p["stories"])
        p["scene"] = scene.plan(p, arrangement="infographic")
        self.assertIn("Collect events", svg.accessible_text(p))
        self.assertFalse(
            any(
                "Locked" in f
                for c in checks.evaluate(self.store, p)
                for f in c["findings"]
            )
        )

    def test_saved_proposals_without_visual_spec_get_native_diagrams_on_explicit_rebuild(
        self,
    ):
        p = project(self.store, "parts")
        del p["stories"][0]["blocks"][0]["visual"]
        before = deepcopy(p)
        visual = scene.plan(p, arrangement="infographic")
        self.assertEqual(p, before)
        self.assertGreaterEqual(
            sum(bool(e.get("glyph")) for e in visual["elements"]), 4
        )

    def test_no_external_or_missing_clipping_paths_are_allowed(self):
        for value in (
            "url(https://example.invalid/image)",
            "url(#missing)",
            "url(file:///private/image)",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                render.safe_svg(
                    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="10" height="10" clip-path="'
                    + value
                    + '"/></svg>'
                )

    def test_optional_artwork_is_generated_for_its_own_region_and_stays_clear_of_diagrams(
        self,
    ):
        from runner import image_brief
        from runner.engine import Engine
        from runner.image_jobs import Jobs
        from runner.images.base import result, save_asset
        from graphics_fixtures import png

        p = project(self.store, art=True)
        p["scene"] = scene.plan(p, arrangement="infographic")
        region = p["scene"]["art_regions"][0]
        direction = {
            "style": "Flat service illustration.",
            "reading_order": "Follow the service subjects.",
            "acceptance": "The subjects are visible without native labels.",
            "reference_assets": [],
            "objects": [
                {
                    "id": "subjects",
                    "region_id": region["id"],
                    "count": 1,
                    "description": "Illustrative endpoint.",
                    "relationships": "Collects events.",
                    "preserve": "Native wording and diagrams stay outside this illustration.",
                }
            ],
        }
        p["image_briefs"] = [image_brief.make(p, direction)]
        brief = p["image_briefs"][0]
        self.assertEqual(brief["placement_region_id"], region["id"])
        self.assertIn("Do not create a mostly blank page", brief["prompt"])
        current = self.store.read(p["id"])
        p["revision"] = current["revision"] + 1
        with self.store.locked():
            self.store.commit_locked(current, p)

        class Adapter:
            configuration = {}

            def __init__(self, folder):
                self.folder = folder

            def generate(self, *, attempt_id, brief):
                return result(
                    "gemini",
                    "generate",
                    attempt_id,
                    state="complete",
                    assets=[save_asset(self.folder, png(), "image/png")],
                )

        jobs = Jobs(self.store, {"gemini": Adapter})
        jobs.intent(
            p["id"],
            expected_revision=p["revision"],
            brief_id=brief["id"],
            provider="gemini",
            request_id="image1",
        )
        jobs.execute(p["id"], "image1")
        current = self.store.read(p["id"])
        composed = Engine(self.store).compose_asset(
            p["id"], current["assets"][0]["id"], expected_revision=current["revision"]
        )
        layer = next(e for e in composed["scene"]["elements"] if e["kind"] == "artwork")
        self.assertEqual(layer["bounds"], region["bounds"])
        self.assertIn('clip-path="url(#art_clip_', svg.compose(self.store, composed))
        if TEST_RENDERER:
            render.render(
                svg.compose(self.store, composed),
                preset="digital",
                fonts=["Arial"],
                executable=TEST_RENDERER,
                destination=self.temp / "native-art-region",
            )

    @unittest.skipUnless(TEST_RENDERER, "Explicit installed renderer required")
    def test_visual_forms_render_with_real_bounds_at_all_three_presets(self):
        for preset in PRESETS:
            for kind in ("process", "timeline", "parts", "comparison", "concept"):
                with self.subTest(preset=preset, kind=kind):
                    p = project(self.store, kind, preset)
                    p["scene"] = scene.plan(p, arrangement="infographic")
                    output = self.temp / (preset + "-" + kind)
                    result = render.render(
                        svg.compose(self.store, p),
                        preset=preset,
                        fonts=[p["brand"]["font"]],
                        executable=TEST_RENDERER,
                        destination=output,
                    )
                    self.assertEqual(result["pdf_pages"], 1)
                    self.assertGreater(result["measured_elements"], 10)
