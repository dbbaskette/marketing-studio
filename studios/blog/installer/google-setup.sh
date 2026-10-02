#!/bin/sh
# Optional Google setup from a downloaded shell script; never creates a project.
set -eu
setup_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
setup_install=no
setup_action=check
case "${1:---check}" in
  --check) ;;
  --login) setup_action=login ;;
  --install-cli) setup_install=yes ;;
  --help|-h)
    printf '%s\n' 'Usage: sh google-setup.sh [--check|--install-cli|--login]' \
      'Install CLI first, then run --login to open Google consent. No Cloud project or OAuth client creation.'
    exit 0 ;;
  *) printf '%s\n' 'Choose --check, --install-cli, or --login.' >&2; exit 2 ;;
esac
if [ "$#" -gt 1 ]; then printf '%s\n' 'Pass one setup action.' >&2; exit 2; fi
if [ "$setup_install" = yes ]; then
  setup_brew="$(command -v brew || true)"
  if [ -z "$setup_brew" ] && [ -x /opt/homebrew/bin/brew ]; then setup_brew=/opt/homebrew/bin/brew; fi
  if [ -z "$setup_brew" ] && [ -x /usr/local/bin/brew ]; then setup_brew=/usr/local/bin/brew; fi
  if [ -z "$setup_brew" ]; then
    printf '%s\n' 'Use your organization-approved Google Cloud CLI installer, or install approved Homebrew first.' \
      'https://cloud.google.com/sdk/docs/install' >&2
    exit 1
  fi
  "$setup_brew" install --cask gcloud-cli
  printf '%s\n' 'Google Cloud CLI installed. Run this script with --login to sign in.'
  exit 0
fi
for setup_python in python3 python3.14 python3.13 python3.12 python3.11 \
 /opt/homebrew/bin/python3 /opt/homebrew/bin/python3.13 /usr/local/bin/python3; do
  if command -v "$setup_python" >/dev/null 2>&1 && "$setup_python" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' >/dev/null 2>&1; then
    if [ "$setup_action" = login ]; then
      printf '%s\n' 'Sign in with the Google account approved for your work. Google will request Drive access.' \
        'This updates the active gcloud account. No Cloud project, billing, or sharing settings are changed.'
    fi
    exec "$setup_python" "$setup_dir/../bootstrap/blog-studio/scripts/google_drive.py" "$setup_action"
  fi
done
printf '%s\n' 'Python 3.11 or later is required. Run Blog Studio setup first.' >&2
exit 1
