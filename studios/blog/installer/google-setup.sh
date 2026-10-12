#!/bin/sh
# Optional Google setup from a downloaded shell script; never creates a project.
set -eu
setup_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
setup_install=no
setup_action=check
setup_account=
setup_activate=no

setup_usage() {
  printf '%s\n' 'Usage: sh google-setup.sh [--check [email] | --install-cli | --login [email] [--activate]]' \
    'Install the CLI first, then run --login you@example.com to open Google consent for that account.' \
    'A named account is added without changing the account gcloud already uses; add --activate to switch.' \
    'No Cloud project or OAuth client is created.'
}

setup_refuse() {
  printf '%s\n' "$1" >&2
  exit 2
}

case "${1:---check}" in
  --check) ;;
  --login) setup_action=login ;;
  --install-cli) setup_install=yes ;;
  --help|-h) setup_usage; exit 0 ;;
  *) setup_refuse 'Choose --check, --install-cli, or --login.' ;;
esac
if [ "$#" -gt 0 ]; then shift; fi

# What may follow: an email for --check and --login, and --activate for --login only.
for setup_word in "$@"; do
  case "$setup_word" in
    --activate)
      if [ "$setup_action" != login ] || [ "$setup_activate" = yes ]; then setup_refuse 'Use --activate once, with --login.'; fi
      setup_activate=yes ;;
    -*) setup_refuse 'Pass one setup action.' ;;
    *@*.*)
      if [ "$setup_install" = yes ] || [ -n "$setup_account" ]; then setup_refuse 'Pass one setup action and at most one email address.'; fi
      setup_account="$setup_word" ;;
    *) setup_refuse 'That does not look like an email address. Example: --login you@example.com' ;;
  esac
done

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
  printf '%s\n' 'Google Cloud CLI installed. Run this script with --login you@example.com to sign in.'
  exit 0
fi

for setup_python in python3 python3.14 python3.13 python3.12 python3.11 \
 /opt/homebrew/bin/python3 /opt/homebrew/bin/python3.13 /usr/local/bin/python3; do
  if command -v "$setup_python" >/dev/null 2>&1 && "$setup_python" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' >/dev/null 2>&1; then
    if [ "$setup_action" = login ]; then
      printf '%s\n' 'Sign in with the Google account approved for your work.' \
        'Google will ask for the access every gcloud sign-in requests (your Google Cloud resources) plus full Google Drive access.' \
        'No Cloud project, billing, or sharing settings are changed.'
      if [ "$setup_activate" = yes ]; then
        printf '%s\n' 'This sign-in becomes the active gcloud account, as requested.'
      elif [ -n "$setup_account" ]; then
        printf '%s\n' 'The account gcloud already uses stays active.'
      fi
    fi
    set -- "$setup_action"
    if [ "$setup_activate" = yes ]; then set -- "$@" --activate; fi
    if [ -n "$setup_account" ]; then set -- --account "$setup_account" "$@"; fi
    exec "$setup_python" "$setup_dir/../bootstrap/blog-studio/scripts/google_drive.py" "$@"
  fi
done
printf '%s\n' 'Python 3.11 or later is required. Run Blog Studio setup first.' >&2
exit 1
