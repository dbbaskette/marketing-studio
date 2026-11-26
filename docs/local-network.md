# Local-network access

Marketing Studio can serve its responsive interface and all four studios to a
phone or tablet on the same trusted local network. Everything runs on the host
computer; nothing needs installing on the phone.

## Connect

1. Connect both devices to the same trusted network.
2. Run `marketing-studio start --all --lan` to start it in the background, or
   `marketing-studio serve --lan` to keep it in this terminal. If Marketing Studio
   is already running without phone access, use `marketing-studio restart --all --lan`
   instead. With phone access already enabled, `marketing-studio open --lan` reuses
   it, and `marketing-studio open --no-open` shows both private links in a terminal.
   Pipes and `--json` receive addresses without session keys.
3. Follow the private phone link printed in that terminal. After shared setup,
   the computer's own home page also offers **Continue on your phone**: scan its
   QR code with the phone's camera, or use **Copy link**.
4. Open a studio from the phone's home page. Its network address is supplied automatically.

The QR code is drawn on the computer by the page itself, from a small encoder in
`qr.js`: nothing is fetched or sent to make it. It holds the same private link, so
keep it out of sight of others. It is shown only on the computer's own (loopback)
home, never on the phone's and never in logs or JSON output. Its text alternative
names it for a screen reader.

The phone's home shows neither the private link nor the terminal note. It says
instead: "You are connected from another device. Work and the assistant stay on
the computer."

With phone access on, a studio opened on the computer still opens at its loopback
address, `127.0.0.1`. Only a studio opened from the phone goes through a network
bridge, which starts then. The bridge marks requests it carries to Marketing Studio,
so the home page knows which device asked. Each studio's **Marketing Studio** link
leads back to the home page on the same device.

Copy the whole link, including its fragment. A bare address loads the interface
but cannot read or change your work. Browsers retain the session key for that tab;
if a new tab asks to reconnect, reopen the private link. Copy support varies on
HTTP: if automatic copying is unavailable, the link is selected for manual copying.
Do assistant and Google sign-in on the host computer before using them from a phone.

To choose an interface explicitly, use the host's private IPv4 address:

```sh
marketing-studio serve --lan 192.168.1.20 --port 8765
```

The address is an example; use your own computer's address. `--port` selects the
Marketing Studio port. Each studio opened through Marketing Studio gets a separate
network port automatically. Address discovery follows the default network route;
with a VPN or several interfaces, choose the Wi-Fi address explicitly.

## Access boundary

Network access is an explicit, per-session CLI option. The default launch remains
loopback-only. The network bridge binds one private IPv4 interface; wildcard,
public, loopback, and hostname values are refused. Native studio servers stay on
loopback with their existing token and origin protections. Each bridge has one
fixed native destination and checks the network Host, session key, request origin,
method, and body size before forwarding. Studio launches are reused within the
session. No session links are saved in shared settings or ordinary logs; redirected
CLI JSON includes only an address. A private link is available in a personal terminal
or through an authenticated home API.

The link gives full access to the studios' work: its pages, files, settings that
name no folder, and explicit assistant jobs. Only the folders of the host computer
are kept to that computer (see [What a phone can change](#what-a-phone-can-change)).
It is not a read-only sharing link or a multi-user login.
**HTTP is unencrypted. Use a trusted network and keep the links private.** Do not
port-forward or expose these listeners to the internet. No TLS certificate,
remote tunnel, account, or cloud service is provisioned. Stop Marketing Studio to
close its bridges and owned processes; independent studio launchers remain local.
Restarting generates new session links. Existing project files stay on the host.

## What a phone can change

Everything the studios do is done from a phone as on the computer, except what names
a folder on the computer. The network bridge marks every request it carries
(`X-Marketing-Studio-Via: network`), and Marketing Studio, each studio's setup page and
the studios read that mark:

- **Set-up and folder settings are done on the computer.** In Shared settings a phone
  cannot change **Workspace folder** or **Installed skill folder**, nor a studio
  installation folder. Presentation Studio and Training Studio refuse their own set-up
  (moving or joining a workspace) from a phone with a sentence to do it on the computer.
  Training Studio's Settings says so in place of **Change the set-up**; Presentation
  Studio's Settings still offers the button, and pressing it from a phone is refused with
  that sentence. A form whose other settings changed is still saved from a phone, as
  long as each folder setting is sent back exactly as it is saved.
- **A repository is given only as a web address of another computer.** From a phone,
  **Brands folder or repository**, **Brand skill Git repository**, the team repository and
  the deck studios' **Brand skill** repository take only an `https://` or `ssh://` address,
  or the `user@host:path` form, on another computer. A folder, `file://`, `http://`, or an
  address of the computer the studios run on (`localhost`, a loopback address or its own
  name) is set only on that computer. In the deck studios, a brand skill repository that
  cannot be read is said without Git's own reason, which can name hosts and ports.
- **Installed brands are listed by name.** The Brand card and **Get brands** tell a phone
  each brand skill and its brands by name, with their variants, never a folder; the deck
  studios' Settings name no brand skill's folder to a phone. A skill folder a phone names
  is refused unread, except the one already saved, sent exactly as saved. Brands
  authoring stays on the computer.
- **No failure sentence names a folder.** Where the reason would name one, a phone is told
  "That could not be done here. See why on the computer the studios run on." The
  studios' own refusals and advice reach a phone as they are. The deck studios' upkeep
  report (each skill link, and where the brand skill is installed from) names no folder
  of the computer.
- **Bring in and folder sources stay on the computer.** Presentation Studio and Training
  Studio refuse **Bring in** from a phone before any folder is read. A studio's source
  picker refuses a folder on the computer; a Google Drive folder link and uploads are
  still taken.
- **A Gemini API key is given on the computer**, in Marketing Studio and in each studio's
  setup page.

A phone is still shown the folder values already saved on the computer: the shared
settings' Workspace folder, brands folder, installed skill folder and any repository
saved as a folder, each studio's installation and workspace folders on the home page,
where Git and the other tools were found, the Document Library's folder, and each deck's
or training's folder in the studios' lists. Showing them is the owner's separate decision;
`marketing_studio/page.py` and `core/studio_core/onboarding.py` list them route by route
(`PHONE_SHOWS`), and the walk tests keep those lists complete.

## If your phone cannot connect

- Keep the host awake and the Marketing Studio terminal running.
- If the host firewall asks, allow incoming connections for the Python runtime
  running Marketing Studio. Studio ports are assigned dynamically; a rule for only
  one port will not cover all studios. Do not disable the firewall globally.
- Guest Wi-Fi and access-point client isolation may block device-to-device access.
  Use a network that permits it.
- If the network address changes, stop and restart with `--lan`, then copy the new
  link. The bridge does not silently follow changing interfaces.
- If another studio is already running independently, use its existing local page
  or close it before launching through Marketing Studio. Existing workspaces are
  never moved to enable phone access.
- Long actions answer at once and carry on in the background, which the page
  follows: Infographic Studio's planning and page builds, and Blog Studio's sends to
  Google, Google Doc intake and library adds with links. The phone bridge waits up to
  four minutes for reading research sources, Presentation Studio's folder or
  spreadsheet for a new deck, and Infographic Studio's remote source previews. Other
  requests keep the 100-second limit. If a connection times out, work may still
  finish on the computer: reopen the saved work and check it before retrying. The
  bridge never resubmits a request.
- A file or picture refused as too large says how large a file the network link takes
  there. The bridge allows each studio address exactly what that studio's own server
  allows: for example a 12 MB request for a Training Studio or Presentation Studio
  source, 1 MB for a saved Training Studio section, 28 MB for a slide picture, 120 MB
  for a new deck's form, 24 MB for Infographic Studio's sources and actions, and
  15 MiB for Blog Studio. Pages send files base64-encoded, a third larger, so the
  sentence names three quarters of the limit: about 9 MB for a source.

## Verification

`tests/test_network.py` uses disposable settings and loopback-only bridge fixtures
to check authentication, exact Host/Origin checks, duplicate headers, request size
limits, fixed targets, key rotation, unavailable children, CLI redaction, reuse,
and shutdown. It keeps every bridge size limit equal to the studio's own limit, and
checks which link the computer and the phone are each given. `tests/test_qr_code.py`
reads each QR code back with a separate decoder. Native launch acceptance also opens and authenticates the studios'
real HTTP servers through the bridge using synthetic workspaces and no
provider jobs. Responsive visual checks cover narrow forms and home pages; physical
phone connectivity still depends on the network and host firewall.
