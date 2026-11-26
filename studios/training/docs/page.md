# The page

Training Studio has a page that runs in your browser, on your own computer. It shows what needs you, where every training stands, and whether this computer is ready.

## Two ways it is served

The same page is served two ways.

- **From a conversation**, with `training desk`, as below. It does not start or run a training. Settings holds notifications.
- **From the runner**, with `studio serve`, which "Open Training Studio" starts. There the page starts and runs trainings too: "New training", each run and its stops, your documents, the copies, the deck and working as a team, as [the runner](runner.md) describes. Settings holds more there: **Shared settings**, **Workspace**, **Preview files in your Google Drive** when there are any, **Notifications**, **When this page is closed**, **Updates** and **Brand skill**.

The rest of this page is about the page served from a conversation.

## Open it

Run this in a terminal of your own:

```bash
~/.local/share/training-studio/training desk
```

It prints one line with a link. Open the link exactly as it is printed: the part after `#` is a key, and the page does not work without it. The command runs until you press Ctrl-C, and the page stops working when it does. Each time you run it you get a new link. Add `--port 8765` to choose the port.

The installer writes `training`, for a linked checkout too, and it finds a Python new enough itself. Without the installer, run `python3 skills/training-studio/scripts/training.py desk` in a checkout of this repository, with Python 3.11 or newer.

You can also ask your assistant to open the page. It then opens in your browser by itself, and your assistant is never shown the key: when the command is not run in a terminal, it prints only the address and says so.

## Home

Home opens on what needs you.

- **Needs you** lists each training that is waiting for you, with one sentence saying what is waiting. The button in the toolbar takes you to the first of them.
- **In progress** shows the trainings that are being worked on, each with its row of stages.
- **Finished** shows the ones that are complete.

The count beside Home, and in the tab's title, is how many things need you. Turn on notifications in Settings and the browser tells you when something new does, while the page is open in a tab.

The same row of stages appears everywhere. A stage is done, in progress, yours to review, not started, left out, or could not be made, and each of those has its own shape as well as its own colour.

A training made on the desk is said the same way on Home, Trainings, Status and its desk: working on its own, needs your decision (an answer, documents, the teaching plan or a deck's slide text), needs attention (a review finding or a held material), drafts to mark ready, ready, or stopped. A finished writing job is never called finished: the training is Ready only once you have marked every material ready and its index is written. Status counts drafts **still to write** apart from drafts **to review and mark ready** and what **needs attention**. Its button opens the desk at the next thing to do, down to the deck slide a finding is on. Opening any screen starts no work.

## A training made in a conversation

A training made in a conversation with the helper is no longer continued, here or anywhere (GitHub issue #547). There is no gate to decide and no decision to record. It is listed as made in a conversation, and opened it is a saved record: what it is, why it is not continued, and its files to read in place. On the Training Studio page its one action is **Bring it in**, which copies it into your workspace and leaves its own folder as it is; the copy then opens on the desk where it has a plan, or is kept to read. A training whose record cannot be read is a read-only record, with **Start a new training**.

## Trainings, Status and Settings

- **Trainings** shows every training on this computer as a card. Open one to see its files, what is in the way, its checks, what was left out, which objectives its scenarios exercise, its research, the guidance it follows and the Training Studio version it started on.
- **Status** shows everything at once: each training's stage, where it stands, how long since it changed and how many things are in its way. **Check this computer** looks for what a training needs: Claude Code and Codex, each installed, signed in where that can be asked, and reachable from the network you are on; Node; the two companion skills; and, as extras, the Google Cloud CLI and pandoc. Anything missing comes with how to put it right. The check asks each tool for its version, asks Codex whether it is signed in, and opens a connection to each service. It never starts an assistant.
- **Settings** holds notifications. Served from the runner, it holds more; see [two ways it is served](#two-ways-it-is-served).

The page keeps itself up to date. You do not need to reload it.

## Is it private?

Yes. The page is local.

- The server listens on `127.0.0.1` only, so no other computer can reach it.
- The page loads nothing from the internet: no fonts, scripts or images from anywhere else.
- Every request for data must carry the key from your link. A decision must also come from the page itself, as JSON. Anything else is refused.
- It can read and change only the trainings in this computer's list, and within a training only the files Training Studio manages.
- Whatever is in a file, a note or a title is shown as text. Nothing in it is ever run or treated as a web page.
- The only time anything leaves your computer is when you press **Check this computer**, which opens a connection to each assistant's service to see whether your network lets it through. It sends nothing.

## What it does not do

- **It does not start or run a training.** Your assistant does that, in a conversation. The same page served from the runner does both; see [the runner](runner.md).
- **It shows the trainings this computer knows about.** A training is known once it has been created here, or once your assistant has read its status here.
- **It runs only while its command runs.**

A training whose record cannot be read is still listed, with the reason, so one broken folder never hides the others.

## Less glass, less motion

The page is drawn like a Mac app: translucent glass for the sidebar, the toolbar and the controls, solid paper for anything you read. If your system asks for reduced transparency, more contrast or reduced motion, the page uses solid surfaces and stops moving. It also does so in a browser that cannot blur what is behind glass.

## For the curious

`training.py desk [--port N]` prints one line of JSON and then serves until it is interrupted. In a terminal the line is `{"url": "..."}`. Anywhere else it is `{"address": "...", "opened": true, "note": "..."}`, with no key in it.

| Request | Returns |
| --- | --- |
| `GET /` | The page. Its other files are `app.js`, `markdown.js` and `style.css` |
| `GET /api/trainings` | Every known training: where it is, what it is waiting for, its row of stages, and how many need you |
| `GET /api/training?path=P` | One training: what `status` and `check` report, and the same in plain words |
| `GET /api/file?path=P&artifact=A` | The text of one file, or its name and size if it is not text |
| `GET /api/computer` | The last check of this computer, if there was one |
| `POST /api/computer` | Checks this computer now |

Every `/api/` request needs the key, in a header named `X-Training-Studio-Token`. A `POST` also needs an `Origin` header naming the page's own address and a JSON body. The page's files live with the scripts, in `skills/training-studio/scripts/desk/`. The design is in the [milestone 1 specification](archive/superpowers/specs/2026-10-13-milestone-1-page-approval.md).
