#!/bin/bash
# Bootstrap before Python is available; application code remains standard-library Python.
set -euo pipefail
installer_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
# The local Presentation Studio bundle owns brand and extra-tool installation.
# Entering its nested suite installer must use that setup and its private Python.
if [ -f "$installer_dir/../../local-manifest.json" ] && [ -f "$installer_dir/../../install-local.py" ]; then
  exec /bin/sh "$installer_dir/../../install.sh" "$@"
fi
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
prerequisites=ask
assistants=skip
companions=ask
target=auto
action=install
noninteractive=0
inspect=0
help=0
alternate_home=0
selected_home="$HOME"
bundled=0
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
        --target) target="$1"; case "$1" in auto|codex|claude|both) ;; *) exit 2;; esac ;;
        --home)
          selected_home="$1"
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
    *) echo "Unknown setup argument: $1. Run bash install.sh --help." >&2; exit 2 ;;
  esac
  shift
done
find_python() {
  python=''
  if [ -f "$installer_dir/../distribution.json" ]; then
    local expected actual
    expected="$(cat "$installer_dir/../runtime/platform")"
    actual="$(uname -s)-$(uname -m)"
    case "$actual" in Darwin-arm64) actual=macos-arm64;; Darwin-x86_64) actual=macos-x64;; Linux-aarch64|Linux-arm64) actual=linux-arm64;; Linux-x86_64) actual=linux-x64;; esac
    [ "$actual" = "$expected" ] || { echo "This download is for $expected; this computer is $actual. Download the matching bundle." >&2; exit 1; }
    python="$installer_dir/../runtime/python/bin/python3"
    chmod u+x "$python" "$installer_dir/../runtime/node/bin/node"
    export PATH="$installer_dir/../runtime/python/bin:$installer_dir/../runtime/node/bin:$PATH"
    "$python" -c 'import sys; assert sys.version_info >= (3,11)' >/dev/null 2>&1 || { echo 'The private Python runtime could not start. Download a fresh bundle for this computer.' >&2; exit 1; }
    "$installer_dir/../runtime/node/bin/node" --version >/dev/null 2>&1 || { echo 'The private Node runtime could not start. Download a compatible bundle for this computer.' >&2; exit 1; }
    bundled=1
    return 0
  fi
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
node_ready() { command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1 && node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= Number(process.argv[1]) ? 0 : 1)' "$node_minimum" >/dev/null 2>&1; }
confirm() {
  if [ "$noninteractive" = 1 ]; then return 0; fi
  if [ ! -t 0 ]; then echo "$1 Add --yes to agree without prompts, or --prerequisites skip for offline setup." >&2; return 1; fi
  local reply
  read -r -p "$1 [Y/n]: " reply
  case "$reply" in ''|y|Y|yes|YES) return 0;; *) return 1;; esac
}
find_python || true
if [ "$target" = auto ]; then
  configured=''
  if [ -n "$python" ]; then
    configured="$("$python" -c 'import sys; sys.path.insert(0, sys.argv[1]); from studio_core.runtime import assistant_target; print(assistant_target(sys.argv[2]))' "$installer_dir/../core" "$selected_home" 2>/dev/null || true)"
  fi
  if [ "$configured" = codex ] || [ "$configured" = claude ]; then target="$configured"
  elif command -v codex >/dev/null 2>&1; then target=codex
  elif command -v claude >/dev/null 2>&1; then target=claude
  else target=codex; fi
  args+=(--target "$target")
fi
if [ "$bundled" = 1 ]; then
  if [ "$assistants" = install ]; then
    echo 'Bundled setup reuses your assistant. Install and sign into Codex or Claude Code separately, then rerun setup.' >&2; exit 2
  fi
  assistants=skip
  if [ "$companions" = ask ]; then companions=install; args+=(--companions install); fi
fi
if [ "$alternate_home" = 1 ]; then prerequisites=skip; assistants=skip; fi
if [ "$inspect" = 1 ]; then
  if [ "$help" = 1 ]; then
    printf '%s\n' 'Marketing Studio setup' '' \
      'Platform downloads include Python, Node, and prepared research/slide tools.' \
      'Setup reuses your selected assistant. Git is required; Google tools are optional.' '' \
      '  bash install.sh [install|check|rollback|uninstall] [options]' \
      '  --studios blog presentation training    Choose one or more studios' \
      '  --target auto|codex|claude|both         Assistant integration (default: detect one)' \
      '  --companions ask|install|skip           Shared research/slide tools' \
      '  --assistants ask|install|skip           Source installer only (default: skip)' \
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
    if confirm 'Install the shared research and slide tools?'; then companions=install; else companions=skip; fi
    args+=(--companions "$companions")
  fi
  missing=()
  [ -n "$python" ] || missing+=(python3)
  git --version >/dev/null 2>&1 || missing+=(git)
  if [ "$bundled" = 0 ] && { [ "$companions" != skip ] || { [ "$assistants" = install ] && [ "${#missing_assistants[@]}" -gt 0 ]; }; }; then
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
    if [ "$bundled" = 0 ] && { [ "$companions" != skip ] || [ "$assistants" = install ]; }; then
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
if [ "$action" = install ] && [ "$inspect" = 0 ] && ! command -v "$target" >/dev/null 2>&1 && [ "$target" != both ]; then
  printf '%s is not installed. Setup can finish; install and sign into your chosen assistant before starting work.\n' "$target" >&2
fi
[ -n "$python" ] || { echo 'Python 3.11+ is unavailable. Rerun setup with --prerequisites install.' >&2; exit 1; }
if [ "${#args[@]}" -gt 0 ]; then
  exec "$python" "$installer_dir/install.py" "${args[@]}"
fi
exec "$python" "$installer_dir/install.py"
