# Local-network access

Marketing Studio can serve its responsive interface and all three studios to a
phone or tablet on the same trusted local network. Everything runs on the host
computer; nothing needs installing on the phone.

## Connect

1. Connect both devices to the same trusted network.
2. Run `marketing-studio start --all --lan` to start it in the background, or
   `marketing-studio serve --lan` to keep it in this terminal. If Marketing Studio
   is already running, use `marketing-studio restart --all --lan` instead.
3. Follow the private phone link printed in that terminal. After shared setup,
   the authenticated home page also offers **Continue on your phone** and **Copy link**.
4. Open a studio from that home page. Its network address is supplied automatically.

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

This is full access to the existing studio UI, including settings, files, and
explicit assistant jobs. It is not a read-only sharing link or a multi-user login.
**HTTP is unencrypted. Use a trusted network and keep the links private.** Do not
port-forward or expose these listeners to the internet. No TLS certificate,
remote tunnel, account, or cloud service is provisioned. Stop Marketing Studio to
close its bridges and owned processes; independent studio launchers remain local.
Restarting generates new session links. Existing project files stay on the host.

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

## Verification

`tests/test_network.py` uses disposable settings and loopback-only bridge fixtures
to check authentication, exact Host/Origin checks, duplicate headers, request size
limits, fixed targets, key rotation, unavailable children, CLI redaction, reuse,
and shutdown. Native launch acceptance also opens and authenticates all three
real studio HTTP servers through the bridge using synthetic workspaces and no
provider jobs. Responsive visual checks cover narrow forms and home pages; physical
phone connectivity still depends on the network and host firewall.
