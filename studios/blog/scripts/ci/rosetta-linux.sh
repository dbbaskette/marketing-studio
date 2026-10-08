#!/usr/bin/env bash
# Compatibility check for workflows already on the trusted base.
# The external runner provisions this environment before accepting a job.
set -euo pipefail
[[ -x /mnt/rosetta/rosetta && -r /proc/sys/fs/binfmt_misc/rosetta ]] || {
  echo 'The external CI runner must prepare the Linux x86 environment.' >&2
  exit 1
}
