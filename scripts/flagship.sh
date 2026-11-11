#!/usr/bin/env bash
# flagship.sh - fetch the release of the flagship that flagship.lock pins,
# verify it as a stranger would, and unpack it into .cache/flagship.
#
# Three checks, each of which refuses the archive on its own: the sha256
# pinned in flagship.lock; cosign verify-blob against the release's Sigstore
# bundle, with the exact identity of the flagship's release workflow on that
# tag; slsa-verifier against the release's provenance, for that tag. Nothing
# from the flagship is read before all three pass.
#
# A release already verified and unpacked is kept: .cache/flagship/verified
# names what passed, and it is believed only while it is the line
# flagship.lock holds and the archive beside it still has the pinned sha256.
# A tool that fails says why in its own words, so a network fault is not
# read as a signature that does not verify.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/.cache/flagship"
say() { printf '== %s\n' "$*"; }
sha256() { if command -v sha256sum >/dev/null; then sha256sum "$1"; else shasum -a 256 "$1"; fi | cut -d' ' -f1; }
read -r REPO TAG SHA < <(grep -vE '^\s*(#|$)' "$ROOT/flagship.lock" | head -n 1)
NAME="${REPO#*/}-$TAG"
BASE="https://github.com/$REPO/releases/download/$TAG"

if [ -d "$OUT/src" ] && [ "$(cat "$OUT/verified" 2>/dev/null)" = "$REPO $TAG $SHA" ] \
   && [ -s "$OUT/release/$NAME.tar.gz" ] && [ "$(sha256 "$OUT/release/$NAME.tar.gz")" = "$SHA" ]; then
  say "$REPO $TAG: already verified and unpacked in .cache/flagship/src"
  exit 0
fi

rm -f "$OUT/verified"
mkdir -p "$OUT/release"
for f in "$NAME.tar.gz" "$NAME.tar.gz.sigstore.json" "$NAME.intoto.jsonl"; do
  [ -s "$OUT/release/$f" ] || curl -fsSL --retry 3 -o "$OUT/release/$f" "$BASE/$f"
done
cd "$OUT/release"
got="$(sha256 "$NAME.tar.gz")"
[ "$got" = "$SHA" ] || { echo "$NAME.tar.gz is $got; flagship.lock pins $SHA" >&2; exit 1; }
# Sigstore's trust root is fetched from its mirror each time. When the mirror
# cannot be reached, that is tried again; a signature that does not verify is
# never tried again.
verified=""
for try in 1 2 3; do
  if out="$(cosign verify-blob "$NAME.tar.gz" --bundle "$NAME.tar.gz.sigstore.json" \
      --certificate-identity "https://github.com/$REPO/.github/workflows/release-assets.yml@refs/tags/$TAG" \
      --certificate-oidc-issuer https://token.actions.githubusercontent.com 2>&1)"; then
    verified=yes; break
  fi
  grep -qE 'tuf refresh failed|error getting live trusted root|dial tcp|i/o timeout' <<<"$out" || break
  echo "Sigstore's trust root could not be fetched (try $try of 3)" >&2
  sleep $((try * 5))
done
if [ -z "$verified" ]; then
  echo "cosign does not verify $NAME.tar.gz as signed by $REPO's release workflow on $TAG: $(tail -n 1 <<<"$out")" >&2
  exit 1
fi
if ! out="$(slsa-verifier verify-artifact "$NAME.tar.gz" --provenance-path "$NAME.intoto.jsonl" \
    --source-uri "github.com/$REPO" --source-tag "$TAG" 2>&1)"; then
  echo "slsa-verifier does not verify $NAME.tar.gz's provenance for $REPO at $TAG: $(tail -n 1 <<<"$out")" >&2
  exit 1
fi
rm -rf "$OUT/src" && mkdir -p "$OUT/src"
tar -xzf "$NAME.tar.gz" -C "$OUT/src" --strip-components 1
echo "$REPO $TAG $SHA" >"$OUT/verified"
say "$REPO $TAG: sha256 pinned, signature and provenance verified, unpacked into .cache/flagship/src"
