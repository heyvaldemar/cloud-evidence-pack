#!/usr/bin/env bash
# tests/static/release-verify.sh - scripts/release-verify.sh on directories
# made from one real pack of v1.0.0 (tests/fixtures/release), its Sigstore
# bundle and the release's provenance. Run by static check "release".
#
#   A  the pack alone: verified
#   B  beside it, an archive that is not <cloud>-<run id>, as the release's
#      own source archive is: passed over, and the pack still verified
#   C  beside them, the pack under another run's name with a signature that
#      is not its own: the release fails, and names it
#   D  the same pack with the provenance of something else: the release fails
#   E  no pack at all, only the other archive: the release fails
#   F  the pack asked for under another tag: the release fails
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FIX="$ROOT/tests/fixtures/release"
PACK=cloud-evidence-pack-aks-42809539539.tar.gz
export GITHUB_REPOSITORY=heyvaldemar/cloud-evidence-pack
T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
failed=0
case_() { # case_ LETTER WHAT WANT_EXIT WORDS DIR [TAG]
  local out rc
  out="$(bash "$ROOT/scripts/release-verify.sh" "$5" "${6:-v1.0.0}" 2>&1)"; rc=$?
  if [ "$rc" = "$3" ] && grep -qF "$4" <<<"$out"; then echo "PASS  $1  $2"
  else echo "FAIL  $1  $2 (exit $rc): $(tail -n 2 <<<"$out" | tr '\n' ' ' | cut -c1-200)"; failed=1; fi
}
real() { mkdir -p "$1" && cp "$FIX/$PACK" "$FIX/$PACK.sigstore.json" "$FIX/cloud-evidence-packs.intoto.jsonl" "$1/"; }

real "$T/a"
case_ A "the pack alone is verified" 0 "== 1 pack(s) in the release; each verifies" "$T/a"

real "$T/b" && printf 'the source archive of the tag' >"$T/b/cloud-evidence-pack-v1.0.0.tar.gz"
case_ B "an archive that is not <cloud>-<run id> is passed over" 0 "not a pack, left alone: cloud-evidence-pack-v1.0.0.tar.gz" "$T/b"

real "$T/c" && printf 'the source archive of the tag' >"$T/c/cloud-evidence-pack-v1.0.0.tar.gz" \
  && cp "$FIX/$PACK" "$T/c/cloud-evidence-pack-gke-1.tar.gz" \
  && cp "$ROOT/tests/fixtures/runs/aks-42809539539/record.json.sigstore.json" "$T/c/cloud-evidence-pack-gke-1.tar.gz.sigstore.json"
case_ C "a pack with a signature that is not its own fails the release" 1 "FAIL cloud-evidence-pack-gke-1.tar.gz: cosign does not verify" "$T/c"

real "$T/d" && cp "$FIX/cloud-evidence-pack-v1.0.0.intoto.jsonl" "$T/d/cloud-evidence-packs.intoto.jsonl"
case_ D "a pack with the provenance of something else fails the release" 1 "slsa-verifier does not verify its provenance" "$T/d"

mkdir -p "$T/e" && printf 'the source archive of the tag' >"$T/e/cloud-evidence-pack-v1.0.0.tar.gz"
case_ E "a release with no pack fails" 1 "FAIL the release holds no pack" "$T/e"

real "$T/f"
case_ F "the pack under another tag fails" 1 "cosign does not verify it as pack.yml at v9.9.9" "$T/f" v9.9.9

[ "$failed" = 0 ] && echo "6 of 6 cases passed"
exit "$failed"
