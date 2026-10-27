"""The `desk` command: serve the page until interrupted."""
import json
import signal
import sys
import webbrowser  # noqa: F401  (tests patch it through this module)

from studio_core.server import NOT_A_PERSON, announce, has_a_screen, interrupt, port, show  # noqa: F401


def serve(args, root):
    """Print one line of JSON, then serve. Never returns: it exits when stopped."""
    import desk  # only when asked for, so no other command loads the server
    server = desk.Desk(args.port)
    signal.signal(signal.SIGTERM, interrupt)
    try:
        print(json.dumps(announce(server, sys.stdout.isatty())), flush=True)
        server.serve()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
    raise SystemExit(0)


def register(commands):
    desk = commands.add_parser(
        'desk', help='open the page: every training on this computer, and where gates are '
                     'decided')
    desk.add_argument('--port', type=port, default=0,
                      help='the local port to serve on (default: one the system chooses)')
    desk.set_defaults(handler=serve)
