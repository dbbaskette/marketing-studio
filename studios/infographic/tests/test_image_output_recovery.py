"""Native image artifacts bind to the exact recorded worker thread, with no replay."""

import json
import os
from unittest import mock

from helpers import Isolated, project
from graphics_fixtures import png
from runner.contracts import Invalid, basis
from runner.images.codex import Codex, saved_output
from runner.images.base import result
from runner.image_jobs import Jobs
from runner.workspace import Store

THREAD = "01234567-1234-7123-8123-0123456789ab"


class NativeOutputTests(Isolated):
    def setUp(self):
        super().setUp()
        self.codex_home = self.temp / "codex"
        os.environ["CODEX_HOME"] = str(self.codex_home)
        self.root = self.codex_home / "generated_images"
        self.folder = self.temp / "worker"
        self.folder.mkdir()
        self.events = "\n".join(
            json.dumps(e)
            for e in [
                {"type": "thread.started", "thread_id": THREAD},
                {
                    "type": "item.completed",
                    "item": {
                        "type": "agent_message",
                        "text": "/elsewhere/never-adopt.png",
                    },
                },
                {
                    "type": "turn.completed",
                    "usage": {"input_tokens": 10, "output_tokens": 20},
                },
            ]
        )

    def native_output(self, folder=None):
        folder = folder or self.folder
        (folder / "events.jsonl").write_text(self.events)
        output = self.root / THREAD
        output.mkdir(parents=True, exist_ok=True)
        (output / "image.png").write_bytes(png())
        return output

    def test_completed_worker_collects_native_thread_output_and_does_not_iterate(self):
        def run(command, prompt, folder, seconds, stop):
            self.assertIn("exactly one image-generation request", prompt)
            self.native_output(folder)
            return {"state": "complete", "returncode": 0, "events": self.events}

        adapter = Codex(self.folder, run=run)
        answer = adapter.generate(
            attempt_id="request1", brief={"prompt": "An explanatory schematic."}
        )
        self.assertEqual(answer["state"], "complete")
        self.assertEqual(
            (self.folder / answer["assets"][0]["file"]).read_bytes(), png()
        )

    def test_local_recovery_never_executes_and_rejects_unfinished_or_linked_threads(
        self,
    ):
        output = self.native_output()
        run = mock.Mock(side_effect=AssertionError("Recovery cannot submit a request"))
        answer = Codex(self.folder, run=run).recover(attempt_id="request1")
        self.assertEqual(answer["state"], "complete")
        run.assert_not_called()
        (self.folder / "events.jsonl").write_text(
            json.dumps({"type": "thread.started", "thread_id": THREAD})
        )
        with self.assertRaises(Invalid):
            saved_output(self.folder)
        (self.folder / "events.jsonl").write_text(self.events)
        (output / "image.png").unlink()
        output.rmdir()
        output.symlink_to(self.folder, target_is_directory=True)
        with self.assertRaises(Invalid):
            saved_output(self.folder)

    def test_recover_requires_same_basis_and_preserves_the_failed_result(self):
        store = Store.setup(self.workspace, data=self.data)
        initial = store.create("Recover a synthetic request")
        p = project()
        p.update(id=initial["id"], owner=store.owner, revision=1)
        p["image_briefs"][0]["basis"] = basis(p)
        with store.locked():
            store.commit_locked(initial, p)
        adapter = mock.Mock()
        adapter.configuration = {}
        adapter.return_value.generate.return_value = result(
            "codex",
            "generate",
            "request1",
            state="failed",
            reason="image-tool-unavailable",
        )
        jobs = Jobs(store, {"codex": adapter})
        jobs.intent(
            p["id"],
            expected_revision=1,
            brief_id="image1",
            provider="codex",
            request_id="request1",
        )
        jobs.execute(p["id"], "request1")
        folder = store._project(p["id"]) / "jobs/request1"
        self.native_output(folder)
        current = store.read(p["id"])
        self.assertTrue(jobs.recovery(p["id"])[0]["local_artwork_available"])
        with mock.patch(
            "runner.images.codex.execute", side_effect=AssertionError("No worker")
        ):
            answer = jobs.recover(
                p["id"], "request1", expected_revision=current["revision"]
            )
        self.assertTrue(answer["adopted"])
        self.assertEqual(store.read(p["id"])["attempts"][0]["state"], "complete")
        self.assertEqual(
            json.loads((folder / "result.json").read_text())["state"], "failed"
        )
        self.assertEqual(
            json.loads((folder / "recovered-result.json").read_text())["state"],
            "complete",
        )
        self.assertEqual(adapter.return_value.generate.call_count, 1)
        with self.assertRaises(Invalid):
            jobs.recover(p["id"], "request1", expected_revision=current["revision"])
