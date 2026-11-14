#!/usr/bin/env bash
# stranger.sh TAG - a release of this repository, checked from an empty
# directory by someone who has nothing of it: no clone, no token, no login.
#
# The release is read from GitHub's public API and addresses with curl, and
# nothing here calls gh. Run it with an empty environment and an empty home,
# so that no token, no gh login and no Sigstore cache of the machine is in
# reach:
#
#   env -i HOME="$(mktemp -d)" PATH="$PATH" bash scripts/stranger.sh v1.2.0
#
# On PATH it needs cosign and slsa-verifier (scripts/install-tools.sh prints
# the directory it puts the pinned ones in), a python3 that has
# requirements.lock installed, curl and tar. `gh release download` is not a
# stranger's way in: gh finds its token whatever HOME says.
#
# For every pack of the release:
#   - cosign verifies it for one exact identity, pack.yml at refs/tags/TAG,
#     and slsa-verifier verifies its provenance for the tag;
#   - a copy with one byte appended is refused by both, and the pack itself
#     is refused under pack.yml at refs/heads/main;
#   - from the release's own source archive and nothing else of the
#     repository, trestle validates its documents, the gate builds them
#     again from the run and asks GitHub now for the run's record, and the
#     gate, given no flag, refuses the same pack with one space added to the
#     record the flagship signed;
#   - cosign verifies the flagship's signature on the run's record, and the
#     run's file has the sha256 the record names.
# The source archive must verify as release-assets.yml at the tag, with its
# provenance. What is compared is each tool's last line, in the words of the
# versions tools.lock pins.
#
# Exits 1 when anything is not as expected, when the release holds no pack,
# or when a token is in the environment.
set -uo pipefail
TAG="${1:?stranger.sh TAG}"
R="${GITHUB_REPOSITORY:-heyvaldemar/cloud-evidence-pack}"
ISS=https://token.actions.githubusercontent.com
FLAGSHIP=https://github.com/heyvaldemar/kubernetes-air-gapped-ai-agent/.github/workflows/cloud-results.yml@refs/heads/main
if [ -n "${GH_TOKEN:-}${GITHUB_TOKEN:-}" ]; then echo "a token is in the environment: this is not a stranger's run"; exit 1; fi
for tool in cosign slsa-verifier python3 curl tar; do
  command -v "$tool" >/dev/null || { echo "$tool is not on PATH"; exit 1; }
done
S="$(mktemp -d)"; cd "$S" || exit 1
fail=0

# The tool's last line, tried again only when Sigstore's trust root could not be fetched.
last() {
  local out i
  for i in 1 2 3; do
    out="$("$@" 2>&1 | tail -n 1)"
    case "$out" in *"tuf refresh"*|*"dial tcp"*|*"i/o timeout"*) sleep $((i * 5)) ;; *) break ;; esac
  done
  printf '%s\n' "${out:0:120}"
}
# expect WORDS LABEL cmd...: the command's last line must hold WORDS.
expect() {
  local words="$1" label="$2" out; shift 2
  out="$(last "$@")"
  if [[ "$out" == *"$words"* ]]; then echo "ok    $label: $out"; else echo "WRONG $label: $out"; fail=1; fi
}

echo "no token in the environment; home is $HOME"
assets="$(curl -fsSL -H 'Accept: application/vnd.github+json' "https://api.github.com/repos/$R/releases/tags/$TAG" \
  | python3 -c 'import json, sys; print("\n".join(a["browser_download_url"] for a in json.load(sys.stdin)["assets"]))')"
[ -n "$assets" ] || { echo "cannot read the release $TAG, or it has no assets"; exit 1; }
while read -r url; do curl -fsSL -O "$url" || { echo "cannot download $url"; exit 1; }; done <<<"$assets"
echo "release $TAG: $(find . -maxdepth 1 -type f | wc -l | tr -d ' ') assets, in $S"

# A pack is cloud-evidence-pack-<cloud>-<run id>.tar.gz and nothing else: the
# release's own source archive, cloud-evidence-pack-<tag>.tar.gz, is not one.
packs=()
for f in cloud-evidence-pack-*.tar.gz; do
  if [[ "$f" =~ ^cloud-evidence-pack-[a-z]+-[0-9]+\.tar\.gz$ ]]; then packs+=("$f"); fi
done
if [ "${#packs[@]}" -lt 1 ]; then echo "WRONG the release holds no pack"; exit 1; fi

id="https://github.com/$R/.github/workflows/pack.yml@refs/tags/$TAG"
provenance=cloud-evidence-packs.intoto.jsonl
for pack in "${packs[@]}"; do
  expect "Verified OK" "$pack signature" cosign verify-blob "$pack" --bundle "$pack.sigstore.json" --certificate-identity "$id" --certificate-oidc-issuer "$ISS"
  expect "PASSED" "$pack provenance" slsa-verifier verify-artifact "$pack" --provenance-path "$provenance" --source-uri "github.com/$R" --source-tag "$TAG"
  cp "$pack" changed.tar.gz && printf x >>changed.tar.gz
  expect "invalid signature" "$pack, one byte appended, cosign" cosign verify-blob changed.tar.gz --bundle "$pack.sigstore.json" --certificate-identity "$id" --certificate-oidc-issuer "$ISS"
  expect "FAILED" "$pack, one byte appended, slsa-verifier" slsa-verifier verify-artifact changed.tar.gz --provenance-path "$provenance" --source-uri "github.com/$R" --source-tag "$TAG"
  expect "no matching CertificateIdentity" "$pack under main's identity" cosign verify-blob "$pack" --bundle "$pack.sigstore.json" --certificate-identity "https://github.com/$R/.github/workflows/pack.yml@refs/heads/main" --certificate-oidc-issuer "$ISS"
done

src="cloud-evidence-pack-$TAG"
expect "Verified OK" "source archive signature" cosign verify-blob "$src.tar.gz" --bundle "$src.tar.gz.sigstore.json" --certificate-identity "https://github.com/$R/.github/workflows/release-assets.yml@refs/tags/$TAG" --certificate-oidc-issuer "$ISS"
expect "PASSED" "source archive provenance" slsa-verifier verify-artifact "$src.tar.gz" --provenance-path "$src.intoto.jsonl" --source-uri "github.com/$R" --source-tag "$TAG"

# The gate, from the release's own source and nothing else of the repository.
if ! { mkdir source && tar -xzf "$src.tar.gz" -C source --strip-components 1 && cd source; }; then
  echo "WRONG the source archive does not unpack"; exit 1
fi
bash scripts/catalogs.sh >/dev/null 2>&1 || { echo "WRONG catalogs"; fail=1; }
for pack in "${packs[@]}"; do
  name="${pack%.tar.gz}"
  rm -rf unpacked && mkdir unpacked && tar -xzf "../$pack" -C unpacked
  out="$(bash scripts/validate.sh unpacked/evidence 2>&1 | tail -n 1)"
  if [[ "$out" == *"3 documents valid"* ]]; then echo "ok    $name trestle: ${out:0:100}"; else echo "WRONG $name trestle: ${out:0:160}"; fail=1; fi
  # 1.0.0 verified the flagship's signature only when asked with --signed; from 1.0.1 the gate does it with no flag.
  if [ "$TAG" = v1.0.0 ]; then flags=(--signed --live); else flags=(--live); fi
  out="$(python3 scripts/gate.py unpacked/evidence "${flags[@]}" 2>&1 | tail -n 1)"
  if [[ "$out" == *"controls satisfied"*"signature on the record verifies"*"record and digest agree"* ]]; then
    echo "ok    $name gate (${flags[*]}): ${out:0:170}"
  else
    echo "WRONG $name gate: ${out:0:200}"; fail=1
  fi
  if [ "$TAG" != v1.0.0 ]; then
    # The same pack with one space added to the record the flagship signed:
    # the gate, given no flag at all, must refuse it, and for the signature.
    rm -rf edited && cp -R unpacked edited && printf ' ' >>edited/evidence/run/record.json
    out="$(python3 scripts/gate.py edited/evidence 2>&1 | tail -n 1)"
    python3 scripts/gate.py edited/evidence >/dev/null 2>&1; rc=$?
    if [ "$rc" -ne 0 ] && [[ "$out" == *"signature on the run's record does not verify"* ]]; then
      echo "ok    $name, record edited, gate with no flag: exit $rc, ${out:0:90}"
    else
      echo "WRONG $name, record edited, gate with no flag: exit $rc, ${out:0:160}"; fail=1
    fi
  fi
  record=unpacked/evidence/run/record.json
  expect "Verified OK" "$name, the flagship's record" cosign verify-blob "$record" --bundle "$record.sigstore.json" --certificate-identity "$FLAGSHIP" --certificate-oidc-issuer "$ISS"
  same="$(python3 - "$record" unpacked/evidence/run/*.zip <<'PY'
import hashlib, json, sys
want = json.load(open(sys.argv[1]))["artifact"]["sha256"]
files = sys.argv[2:]
got = hashlib.sha256(open(files[0], "rb").read()).hexdigest() if len(files) == 1 else ""
print(got[:16] if got == want else "")
PY
)"
  if [ -n "$same" ]; then echo "ok    $name file sha256 is the record's: $same"; else echo "WRONG $name file sha256"; fail=1; fi
done
echo "== ${#packs[@]} packs; $([ "$fail" = 0 ] && echo 'every check as expected' || echo 'SOMETHING WAS WRONG')"
exit "$fail"
