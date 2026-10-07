#!/usr/bin/env bash
# Builds the release zip with tools/package.sh and stores it in releases/, the one place to download it from.
#   releases/ holds only the CURRENT zip, <Addon>-v<Version>-forever.zip (older ones are removed; git history keeps them).
# Usage: bash tools/release.sh    Prints the path. Commit releases/ together with the code change it belongs to.
set -euo pipefail
cd "$(dirname "$0")/.."
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
built=$(bash tools/package.sh "$tmp" | tail -1)
zipname=$(basename "$built")
addon="${zipname%%-v*}"
mkdir -p releases
rm -f "releases/$addon"-v*-forever.zip
cp "$built" "releases/$zipname"
echo "releases/$zipname"
