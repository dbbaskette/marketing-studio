"""Prepare a controlled teaching comparison and score independently reviewed decks."""

import argparse
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZipFile

CASES = {
    "canary": {
        "topic": "Making a go, hold or cancel decision during a canary deployment on Tanzu Platform for Cloud Foundry.",
        "audience": "Application developers who use cf push and have never run a canary deployment.",
        "purpose": "Teach a 20-minute live workshop. Given a paused canary and competing health signals, learners should justify a safe next action. Include a worked release decision and a different one for learners to try.",
    },
    "git": {
        "topic": "Check exactly which edits will be committed with Git.",
        "audience": "Developers who have committed files but are new to partial staging.",
        "purpose": "Teach a 20-minute hands-on CLI lesson. Learners inspect staged and unstaged edits independently, predict the next commit, and verify their prediction in a disposable repository.",
    },
}
RUBRIC = (
    "Technical accuracy and scope",
    "Decision or command with evidence",
    "Worked example",
    "Independent attempt and feedback",
    "Facilitator readiness",
)
TRANSFER = {
    "canary": (
        "A paused hypothetical rollout shows 100 shared-route successes and no "
        "revision-tagged requests. The exercise policy requires 20 matched canary "
        "requests before continuing. Choose the next action, cite the observation "
        "that supports it and name evidence that would change it.",
        "Hold and obtain revision-attributed observations. The aggregate cannot show "
        "the canary met the exercise policy. Explain when to continue or cancel.",
    ),
    "git": (
        "In a fresh copy of the lab, stage a change to the banner, then change the same "
        "line again without staging. Predict the committed banner. Run the commands "
        "that support your answer. What would change your prediction?",
        "The staged value enters an ordinary git commit. Show git diff --cached and "
        "git diff, explain each comparison and verify with git show HEAD:banner.txt.",
    ),
}


def store(path, value):
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_sources(folder):
    """Capture the two comparisons against real Git in an isolated, synthetic lab."""
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory)

        def git(*args):
            return subprocess.check_output(
                [
                    "git",
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.invalid",
                    "-c",
                    "commit.gpgSign=false",
                    "-c",
                    "core.hooksPath=/dev/null",
                    *args,
                ],
                cwd=repo,
                text=True,
                env={
                    "PATH": os.defpath,
                    "GIT_CONFIG_GLOBAL": "/dev/null",
                    "GIT_CONFIG_NOSYSTEM": "1",
                    "LC_ALL": "C",
                    "GIT_DIR": str(repo / ".git"),
                    "GIT_WORK_TREE": str(repo),
                    "GIT_INDEX_FILE": str(repo / ".git/index"),
                },
            )

        git("init", "-q")
        file = repo / "banner.txt"
        file.write_text("blue\n")
        git("add", "banner.txt")
        git("commit", "-qm", "initial")
        file.write_text("green\n")
        git("add", "banner.txt")
        file.write_text("amber\n")
        (folder / "lab.txt").write_text(
            "Synthetic local lab. Use a fresh repository and set a disposable local Git "
            "user.name and user.email. Initialize and commit banner.txt containing blue. "
            "Replace blue with green, run git add banner.txt, then replace green with amber. "
            "To restart, repeat in a new directory.\n"
        )
        cached, working = git("diff", "--cached"), git("diff")
        git("commit", "-qm", "test prediction")
        result = git("show", "HEAD:banner.txt")
        if result != "green\n":
            raise ValueError(
                "The isolated Git lab did not produce the expected staged value."
            )
        (folder / "observations.txt").write_text(
            f"{git('--version')}$ git diff --cached\n{cached}\n$ git diff\n{working}"
            f'\n$ git commit -qm "test prediction"\n$ git show HEAD:banner.txt\n{result}'
        )


def prepare(args):
    folder = args.output
    if args.case == "canary" and len(args.source) != 2:
        raise ValueError(
            "Supply the saved deployment and health-check text snapshots, in that order."
        )
    if args.case == "git" and args.source:
        raise ValueError("The Git case generates its two sources locally.")
    folder.mkdir(parents=True, exist_ok=False)
    sources = folder / "sources"
    sources.mkdir()
    if args.case == "canary":
        for original, name in zip(args.source, ("deployments.txt", "health.txt")):
            shutil.copyfile(original, sources / name)
    else:
        git_sources(sources)
    intake = {
        **CASES[args.case],
        "agent": "codex",
        "delivery": "live",
        "levels": ["201"],
        "time_limit": "20 minutes",
        "materials": [],
        "deck_target": "pptx",
        "research_from": {"documents": True, "web": False, "sites": []},
        "model": args.model,
        "effort": args.effort,
        "brand": {"brand": args.brand, "variant": "light"},
        "slide_text_review": False,
    }
    store(folder / "intake.json", intake)
    store(
        folder / "controls.json",
        {
            "case": args.case,
            "model": args.model,
            "effort": args.effort,
            "brand": args.brand,
            "intake": fingerprint(folder / "intake.json"),
            "sources": {f.name: fingerprint(f) for f in sorted(sources.iterdir())},
        },
    )


def blind(args):
    inputs = []
    for run in (args.baseline, args.candidate):
        control = json.loads((run / "controls.json").read_text())
        intake = json.loads((run / "intake.json").read_text())
        if (
            control["case"] not in CASES
            or fingerprint(run / "intake.json") != control["intake"]
        ):
            raise ValueError(f"Intake does not match the prepared case in {run}.")
        if (
            any(control[k] != intake[k] for k in ("model", "effort"))
            or control["brand"] != intake["brand"]["brand"]
        ):
            raise ValueError(f"Model or brand differs from the intake in {run}.")
        actual = {
            f.name: fingerprint(f) for f in (run / "sources").iterdir() if f.is_file()
        }
        if len(actual) != 2 or actual != control["sources"]:
            raise ValueError(
                f"Research inputs differ from the prepared controls in {run}."
            )
        control["outline"] = json.loads((run / "approved-outline.json").read_text())
        deck = run / "deck.pptx"
        with ZipFile(deck) as archive:
            if "ppt/presentation.xml" not in archive.namelist():
                raise ValueError(f"Expected a PowerPoint deck in {run}.")
        inputs.append((control, deck))
    if inputs[0][0] != inputs[1][0]:
        raise ValueError(
            "The two runs must have identical sources, approved outline, intake and model settings."
        )
    case = inputs[0][0]["case"]
    labels = ["A", "B"]
    secrets.SystemRandom().shuffle(labels)
    folder = args.output
    folder.mkdir(parents=True, exist_ok=False)
    review = folder / "review"
    review.mkdir()
    for label, (_, deck) in zip(labels, inputs):
        shutil.copyfile(deck, review / f"{label}.pptx")
    store(folder / "key.json", {"baseline": labels[0], "candidate": labels[1]})
    store(
        review / "scores.json",
        {
            label: {criterion: {"score": None, "evidence": ""} for criterion in RUBRIC}
            for label in ("A", "B")
        },
    )
    question, key = TRANSFER[case]
    (review / "transfer.txt").write_text(question + "\n")
    (folder / "facilitator-key.txt").write_text(key + "\n")


def compare(args):
    scores = json.loads((args.output / "review/scores.json").read_text())
    key = json.loads((args.output / "key.json").read_text())
    results = {}
    for version, label in key.items():
        rows = scores[label]
        for criterion in RUBRIC:
            row = rows[criterion]
            if (
                type(row["score"]) != int
                or row["score"] not in (0, 1, 2)
                or not row["evidence"].strip()
            ):
                raise ValueError(
                    f"{label}: score {criterion} 0–2 and cite slide/notes evidence."
                )
        results[version] = sum(rows[c]["score"] for c in RUBRIC)
    return {
        **results,
        "change": results["candidate"] - results["baseline"],
        "dimensions": {
            c: {v: scores[label][c] for v, label in key.items()} for c in RUBRIC
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    new = commands.add_parser("prepare")
    new.add_argument("case", choices=CASES)
    new.add_argument("--source", action="append", type=Path, default=[])
    for field in ("model", "effort", "brand"):
        new.add_argument("--" + field, required=True)
    pair = commands.add_parser("blind")
    for field in ("baseline", "candidate"):
        pair.add_argument(field, type=Path)
    for sub in (new, pair, commands.add_parser("compare")):
        sub.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args)
    elif args.command == "blind":
        blind(args)
    else:
        print(json.dumps(compare(args), indent=2))


if __name__ == "__main__":
    main()
