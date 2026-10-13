#!/usr/bin/env bash
# Publish the version in skills/blog-studio/VERSION as a GitHub Release.
#
#   bash scripts/release.sh             # check, build, tag and publish
#   bash scripts/release.sh --dry-run   # check and build, then say what would be published
#
# Run it from a clean checkout of the current origin/main, after the change to VERSION and
# its CHANGELOG section have merged. It refuses when the tag already exists. Releases are a
# script rather than a workflow because the runner service that checks pull requests serves
# this repository only while its one approved workflow is the only active one.
set -euo pipefail
cd "$(dirname "$0")/.."

dry_run=no
python_bin=$(command -v python3)
while (( $# )); do
  case "$1" in
    --dry-run) dry_run=yes ;;
    --python) python_bin=${2:?--python needs an interpreter path}; shift ;;
    *) echo "Usage: bash scripts/release.sh [--dry-run] [--python /path/to/python3]" >&2; exit 2 ;;
  esac
  shift
done

repo=${BLOG_STUDIO_REPO:-dbbaskette/blog-studio}
version=$(tr -d '[:space:]' < skills/blog-studio/VERSION)
if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "skills/blog-studio/VERSION must be a release number such as 2.0.0." >&2
  exit 1
fi
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Commit or remove local changes first; a release is built from a clean checkout." >&2
  exit 1
fi
git fetch --quiet --tags origin main
if [[ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]]; then
  echo "Check out the current origin/main first; a release is built from what is merged." >&2
  exit 1
fi
if git ls-remote --exit-code --tags origin "refs/tags/v$version" >/dev/null 2>&1; then
  echo "v$version is already released. Change skills/blog-studio/VERSION and merge that first." >&2
  exit 1
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
BLOG_STUDIO_REQUIRE_LINT=1 bash scripts/ci/check.sh "$python_bin" "$work/checks"
"$python_bin" scripts/build.py --output "$work/build" >/dev/null

# Release notes are this version's section of CHANGELOG.md.
awk -v heading="## $version" \
  'index($0, heading) == 1 {found = 1; next} /^## / {found = 0} found' CHANGELOG.md > "$work/notes.md"
[[ -s "$work/notes.md" ]] || echo "Blog Studio $version" > "$work/notes.md"

if [[ "$dry_run" == yes ]]; then
  echo "Dry run: v$version would be published to $repo from $(git rev-parse --short HEAD) with:"
  ls -1 "$work/build"
  exit 0
fi
gh release create "v$version" "$work"/build/*.zip "$work"/build/*.zip.sha256 \
  --repo "$repo" --target "$(git rev-parse HEAD)" \
  --title "Blog Studio $version" --notes-file "$work/notes.md"
echo "Published v$version."
