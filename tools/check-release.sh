#!/usr/bin/env bash
# Fails unless releases/ holds exactly one zip and it is what tools/package.sh builds right now
# (same file name for the .toc version, same files inside). Fix: bash tools/release.sh, then commit releases/.
set -euo pipefail
cd "$(dirname "$0")/.."
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
built=$(bash tools/package.sh "$tmp/build" | tail -1)
zipname=$(basename "$built")
shopt -s nullglob
have=(releases/*.zip)
[ ${#have[@]} -eq 1 ] || { echo "releases/ must hold exactly one zip (found ${#have[@]}). Run: bash tools/release.sh" >&2; exit 1; }
[ "$(basename "${have[0]}")" = "$zipname" ] || { echo "releases/ has $(basename "${have[0]}") but the .toc version builds $zipname. Run: bash tools/release.sh" >&2; exit 1; }
mkdir -p "$tmp/fresh" "$tmp/stored"
unzip -q "$built" -d "$tmp/fresh"
unzip -q "${have[0]}" -d "$tmp/stored"
diff -r "$tmp/fresh" "$tmp/stored" >/dev/null || { echo "releases/$zipname is out of date: its files differ from a fresh build. Run: bash tools/release.sh" >&2; exit 1; }
echo "releases/$zipname is current"
