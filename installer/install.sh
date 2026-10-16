#!/bin/bash
# Bootstrap before Python is available; application code remains standard-library Python.
set -euo pipefail
installer_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
prerequisites=ask
assistants=ask
companions=ask
target=both
action=install
noninteractive=0
inspect=0
help=0
alternate_home=0
args=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --prerequisites|--assistants)
      option="$1"; shift
      [ "$#" -gt 0 ] || { echo "Missing value for $option" >&2; exit 2; }
      case "$1" in ask|install|skip|check) ;; *) echo "Invalid $option value: $1" >&2; exit 2;; esac
      if [ "$option" = --prerequisites ]; then prerequisites="$1"; else
        [ "$1" != check ] || { echo "Use --assistants ask, install, or skip." >&2; exit 2; }
        assistants="$1"
      fi
      ;;
    --companions|--target|--home|--source)
      option="$1"; args+=("$1"); shift
      [ "$#" -gt 0 ] || { echo "Missing value for $option" >&2; exit 2; }
      case "$option" in
        --companions) companions="$1"; case "$1" in ask|install|skip) ;; *) exit 2;; esac ;;
        --target) target="$1"; case "$1" in codex|claude|both) ;; *) exit 2;; esac ;;
        --home)
          if [ "$1" != "$HOME" ]; then
            # Alternate homes are for offline packaging/tests, never host provisioning.
            alternate_home=1
          fi ;;
      esac
      args+=("$1") ;;
    --yes) noninteractive=1; args+=("$1") ;;
    --help|-h) help=1; inspect=1; args+=("$1") ;;
    --dry-run) inspect=1; args+=("$1") ;;
    check|rollback|uninstall) action="$1"; args+=("$1") ;;
    install|--json|--studios|blog|presentation|training) args+=("$1") ;;
    *) echo "Unknown setup argument: $1. Run bash installer/install.sh --help." >&2; exit 2 ;;
  esac
  shift
done
find_python() {
  python=''
  for candidate in python3 python3.14 python3.13 python3.12 python3.11 \
      /opt/homebrew/bin/python3 /usr/local/bin/python3 \
      /Library/Frameworks/Python.framework/Versions/Current/bin/python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3,11))' >/dev/null 2>&1; then
      python="$(command -v "$candidate")"; return 0
    fi
  done
  return 1
}
node_minimum=20
node_ready() { command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1 && node -e 'process.exit(Number(process.versions.node.split(".")[0]) < Number(process.argv[1]))' "$node_minimum" >/dev/null 2>&1; }
confirm() {
  if [ "$noninteractive" = 1 ]; then return 0; fi
  if [ ! -t 0 ]; then echo "$1 Add --yes to agree without prompts, or --prerequisites skip for offline setup." >&2; return 1; fi
  local reply
  read -r -p "$1 [Y/n]: " reply
  case "$reply" in ''|y|Y|yes|YES) return 0;; *) return 1;; esac
}
find_python || true
if [ "$alternate_home" = 1 ]; then prerequisites=skip; assistants=skip; fi
if [ "$inspect" = 1 ]; then
  if [ "$help" = 1 ]; then
    printf '%s\n' 'Marketing Studio setup' '' \
      'Checks and offers to install Python 3.11+, Git, Node.js 20+, selected assistant CLIs,' \
      'the selected studios, and their pinned research/slide tools.' '' \
      '  bash installer/install.sh [install|check|rollback|uninstall] [options]' \
      '  --studios blog presentation training    Choose one or more studios' \
      '  --target codex|claude|both              Assistant integration (default: both)' \
      '  --companions ask|install|skip           Shared research/slide tools' \
      '  --assistants ask|install|skip           Missing assistant CLIs (Claude Code needs Node 22+)' \
      '  --prerequisites ask|install|check|skip  System tools (default: ask)' \
      '  --yes                                 Agree to installation without prompts' \
      '  --dry-run                             Plan only; no downloads or changes' \
      '  --home PATH --source PATH --json       Advanced/offline use'
    exit 0
  fi
  prerequisites=skip; assistants=skip
fi
if [ "$action" != install ]; then prerequisites=skip; assistants=skip; fi
if [ "$prerequisites" != skip ]; then
  missing_assistants=()
  if [ "$target" != claude ] && ! command -v codex >/dev/null 2>&1; then missing_assistants+=(codex); fi
  if [ "$target" != codex ] && ! command -v claude >/dev/null 2>&1; then missing_assistants+=(claude); fi
  if [ "$prerequisites" = check ]; then
    assistants=skip
  elif [ "$assistants" = ask ] && [ "${#missing_assistants[@]}" -gt 0 ]; then
    if confirm "Install the missing assistant CLI(s): ${missing_assistants[*]}? Sign-in happens separately."; then assistants=install; else assistants=skip; fi
  fi
  if [ "$assistants" = install ]; then
    case " ${missing_assistants[*]:-} " in *' claude '*) node_minimum=22;; esac
  fi
  if [ "$companions" = ask ] && [ "$prerequisites" != check ]; then
    if confirm 'Install the pinned shared research and slide tools?'; then companions=install; else companions=skip; fi
    args+=(--companions "$companions")
  fi
  missing=()
  [ -n "$python" ] || missing+=(python3)
  git --version >/dev/null 2>&1 || missing+=(git)
  if [ "$companions" != skip ] || { [ "$assistants" = install ] && [ "${#missing_assistants[@]}" -gt 0 ]; }; then
    node_ready || missing+=(node)
  fi
  if [ "${#missing[@]}" -gt 0 ]; then
    printf 'Missing prerequisites: %s\n' "${missing[*]}" >&2
    if [ "$prerequisites" = check ]; then exit 1; fi
    if [ "$prerequisites" = ask ]; then confirm 'Install these prerequisites using your system package manager?' || exit 1; fi
    brew_command="$(command -v brew || true)"
    if [ "$(uname -s)" = Darwin ] && [ -z "$brew_command" ]; then
      confirm 'Install Homebrew from https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh? This may request your administrator password.' || exit 1
      bootstrap_file="$(mktemp "${TMPDIR:-/tmp}/marketing-homebrew.XXXXXX")"
      trap 'rm -f "$bootstrap_file"' EXIT
      curl --fail --show-error --silent --location https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh -o "$bootstrap_file"
      if [ "$noninteractive" = 1 ]; then NONINTERACTIVE=1 /bin/bash "$bootstrap_file"; else /bin/bash "$bootstrap_file"; fi
      rm -f "$bootstrap_file"
      trap - EXIT
      brew_command="$(command -v brew || true)"
      [ -n "$brew_command" ] || { echo 'Homebrew setup did not finish. Reopen setup after resolving its reported error.' >&2; exit 1; }
    fi
    if [ -n "$brew_command" ]; then
      HOMEBREW_NO_AUTO_UPDATE=1 "$brew_command" install "${missing[@]}" >&2
    else
      as_root() {
        if [ "$(id -u)" = 0 ]; then "$@"; else sudo "$@"; fi
      }
      packages=()
      for package in "${missing[@]}"; do
        if [ "$package" = node ]; then packages+=(nodejs npm); else packages+=("$package"); fi
      done
      if command -v apt-get >/dev/null 2>&1; then
        as_root apt-get update >&2
        as_root apt-get install -y "${packages[@]}" >&2
      elif command -v dnf >/dev/null 2>&1; then
        as_root dnf install -y "${packages[@]}" >&2
      else
        echo 'No supported package manager found. Install Python 3.11+, Git, and Node.js 20+, then run setup again.' >&2; exit 1
      fi
    fi
    hash -r
    find_python || { echo 'Your package repository did not provide Python 3.11+. Install a supported Python version, then rerun setup.' >&2; exit 1; }
    git --version >/dev/null 2>&1 || { echo 'Git installation did not finish.' >&2; exit 1; }
    if [ "$companions" != skip ] || [ "$assistants" = install ]; then
      node_ready || { echo "Your package repository did not provide Node.js $node_minimum+ and npm. Install a current Node.js LTS release, then rerun setup." >&2; exit 1; }
    fi
  fi
  if [ "$assistants" = install ] && [ "${#missing_assistants[@]}" -gt 0 ]; then
    for assistant in "${missing_assistants[@]}"; do
      case "$assistant" in codex) package=@openai/codex;; claude) package=@anthropic-ai/claude-code;; esac
      npm install --global --prefix "$HOME/.local" "$package" >&2
      hash -r
      "$assistant" --version >&2
      printf 'Installed %s. Run `%s` in your terminal to sign in before starting assistant work.\n' "$assistant" "$assistant" >&2
    done
  fi
fi
[ -n "$python" ] || { echo 'Python 3.11+ is unavailable. Rerun setup with --prerequisites install.' >&2; exit 1; }
if [ "${#args[@]}" -gt 0 ]; then
  exec "$python" "$installer_dir/install.py" "${args[@]}"
fi
exec "$python" "$installer_dir/install.py"
