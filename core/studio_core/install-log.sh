#!/bin/bash
# Run an installer with a private console transcript, before Python is available.
# Do not use xtrace: command arguments and environments can contain credentials.
set -u
entry="$1"
shift
selected_home="$HOME"
export STUDIO_INSTALL_LOG_WRAPPED=1
previous=''
for argument in "$@"; do
  case "$argument" in --help|-h|--dry-run) exec /bin/bash "$entry" "$@";; esac
  if [ "$previous" = --home ]; then selected_home="$argument"; fi
  previous="$argument"
done
log_dir="$selected_home/.local/state/marketing-studio/logs"
(umask 077; /bin/mkdir -p "$log_dir") || exit 1
log_file="$(umask 077; /usr/bin/mktemp "$log_dir/install-$(/bin/date -u +%Y%m%dT%H%M%SZ)-XXXXXX")" || exit 1
export STUDIO_INSTALL_LOG="$log_file"
export STUDIO_INSTALL_CONSOLE_LOGGED=1
printf 'Installation log: %s\n' "$log_file" >&2
printf '%s Installer started: %s\n' "$(/bin/date -u +%Y-%m-%dT%H:%M:%SZ)" "$entry" >> "$log_file"
# Keep stdin attached for prompts, stdout separate for --json, and wait for both
# copies before returning the original exit status. No shell startup files change.
pipes="$(/usr/bin/mktemp -d "${TMPDIR:-/tmp}/studio-install-log.XXXXXX")" || exit 1
trap '/bin/rm -f "$pipes/stdout" "$pipes/stderr"; /bin/rmdir "$pipes"' EXIT
/usr/bin/mkfifo "$pipes/stdout" "$pipes/stderr" || exit 1
/usr/bin/tee -a "$log_file" < "$pipes/stdout" &
stdout_pid=$!
/usr/bin/tee -a "$log_file" < "$pipes/stderr" >&2 &
stderr_pid=$!
/bin/bash "$entry" "$@" > "$pipes/stdout" 2> "$pipes/stderr"
result=$?
wait "$stdout_pid" || result=1
wait "$stderr_pid" || result=1
printf '%s Installer finished: exit %s\n' "$(/bin/date -u +%Y-%m-%dT%H:%M:%SZ)" "$result" >> "$log_file"
printf 'Installation log: %s (exit %s)\n' "$log_file" "$result" >&2
exit "$result"
