#!/usr/bin/env bash
# Builds <Addon>-v<Version>-forever.zip, ready to upload to CurseForge.
#   Addon name: "package-as" in .pkgmeta (falls back to the only .toc in the repo root)
#   Version:    "## Version:" in <Addon>.toc
#   Contents:   an <Addon>/ folder holding the .toc and every file the .toc lists, nothing else
# Usage: tools/package.sh [output-dir]   (default: dist). Prints the path of the zip.
set -euo pipefail
cd "$(dirname "$0")/.."

name=""
if [ -f .pkgmeta ]; then
  name=$(sed -n 's/^package-as:[[:space:]]*//p' .pkgmeta | tr -d '\r' | head -1)
fi
if [ -z "$name" ]; then
  tocs=(*.toc)
  [ ${#tocs[@]} -eq 1 ] || { echo "Set package-as in .pkgmeta: found ${#tocs[@]} .toc files" >&2; exit 1; }
  name="${tocs[0]%.toc}"
fi
toc="$name.toc"
[ -f "$toc" ] || { echo "Missing $toc" >&2; exit 1; }

version=$(sed -n 's/^##[[:space:]]*Version:[[:space:]]*//p' "$toc" | tr -d '\r' | head -1)
[ -n "$version" ] || { echo "No '## Version:' line in $toc" >&2; exit 1; }
version="${version#v}"

out="${1:-dist}"
mkdir -p "$out"
out=$(cd "$out" && pwd)
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
mkdir -p "$stage/$name"
cp "$toc" "$stage/$name/"

while IFS= read -r line || [ -n "$line" ]; do
  line="${line%$'\r'}"
  line="${line#"${line%%[![:space:]]*}"}"   # trim leading spaces
  line="${line%"${line##*[![:space:]]}"}"   # trim trailing spaces
  [ -z "$line" ] && continue
  case "$line" in \#*) continue ;; esac
  file="${line//\\//}"                       # .toc paths may use backslashes
  [ -f "$file" ] || { echo "$toc lists $file, but it does not exist" >&2; exit 1; }
  mkdir -p "$stage/$name/$(dirname "$file")"
  cp "$file" "$stage/$name/$file"
done < "$toc"

zipname="$name-v$version-forever.zip"
rm -f "$out/$zipname"
(cd "$stage" && zip -qrX "$out/$zipname" "$name")
echo "$out/$zipname"
