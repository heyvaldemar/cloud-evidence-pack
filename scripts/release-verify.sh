#!/usr/bin/env bash
# release-verify.sh DIR TAG - what a release holds, checked as a stranger
# would check it. DIR is the release's assets, downloaded again.
#
# A pack is an archive named cloud-evidence-pack-<cloud>-<run id>.tar.gz and
# nothing else. The release also holds this repository's own source archive,
# cloud-evidence-pack-<tag>.tar.gz, which release-assets.yml signs as itself:
# it is not a pack, and it is left alone. Run 43137012297 took it for one and
# failed on its identity after the three packs of v1.0.0 had verified.
#
# Every pack must:
#   - verify with cosign against its bundle, for one exact identity: this
#     repository's pack.yml at refs/tags/TAG;
#   - verify with slsa-verifier against cloud-evidence-packs.intoto.jsonl,
#     for this repository at TAG;
#   - and a copy with one byte appended must be refused by both.
# A release with no pack fails. Exits 1 when anything does.
#
# GITHUB_REPOSITORY names the repository (owner/name). Needs cosign and
# slsa-verifier on PATH, and the network for Sigstore's trust root and log.
set -uo pipefail
DIR="${1:?release-verify.sh DIR TAG}"
TAG="${2:?release-verify.sh DIR TAG}"
REPO="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY names the repository}"
cd "$DIR" || exit 2
sig=(--certificate-identity "https://github.com/$REPO/.github/workflows/pack.yml@refs/tags/$TAG"
     --certificate-oidc-issuer https://token.actions.githubusercontent.com)
provenance=cloud-evidence-packs.intoto.jsonl
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# The tool's own last line; tried again only when Sigstore's trust root could not be fetched.
said=""
sigstore() {
  local try out rc
  for try in 1 2 3; do
    out="$("$@" 2>&1)"; rc=$?
    said="$(tail -n 1 <<<"$out")"
    [ "$rc" -eq 0 ] && return 0
    grep -qE 'tuf refresh failed|error getting live trusted root|dial tcp|i/o timeout' <<<"$said" || return 1
    sleep $((try * 5))
  done
  return 1
}

packs=0; failed=0
for f in *.tar.gz; do
  [ -e "$f" ] || continue
  if ! [[ "$f" =~ ^cloud-evidence-pack-[a-z]+-[0-9]+\.tar\.gz$ ]]; then
    echo "not a pack, left alone: $f"
    continue
  fi
  packs=$((packs + 1))
  if ! sigstore cosign verify-blob "$f" --bundle "$f.sigstore.json" "${sig[@]}"; then
    echo "FAIL $f: cosign does not verify it as pack.yml at $TAG: ${said:0:160}"; failed=1; continue
  fi
  if ! sigstore slsa-verifier verify-artifact "$f" --provenance-path "$provenance" --source-uri "github.com/$REPO" --source-tag "$TAG"; then
    echo "FAIL $f: slsa-verifier does not verify its provenance for $TAG: ${said:0:160}"; failed=1; continue
  fi
  cp "$f" "$tmp/changed.tar.gz" && printf 'x' >>"$tmp/changed.tar.gz"
  if sigstore cosign verify-blob "$tmp/changed.tar.gz" --bundle "$f.sigstore.json" "${sig[@]}"; then
    echo "FAIL $f: cosign accepted it with one byte appended"; failed=1; continue
  fi
  if sigstore slsa-verifier verify-artifact "$tmp/changed.tar.gz" --provenance-path "$provenance" --source-uri "github.com/$REPO" --source-tag "$TAG"; then
    echo "FAIL $f: slsa-verifier accepted it with one byte appended"; failed=1; continue
  fi
  echo "ok   $f: signed as pack.yml at $TAG, provenance for the tag, a changed copy refused by both"
done
if [ "$packs" -lt 1 ]; then echo "FAIL the release holds no pack"; failed=1; fi
echo "== $packs pack(s) in the release; $([ "$failed" = 0 ] && echo "each verifies, and a changed copy of each does not" || echo "not all of them verify")"
exit "$failed"
