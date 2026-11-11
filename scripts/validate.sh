#!/usr/bin/env bash
# validate.sh [check...] - the static checks. None needs a cluster, a cloud
# account or the network once .cache is filled:
#
#   component  mapping/controls.yaml names no control, row of the flagship's
#              page, check or planted pod that is not there, every control
#              has a refusal and something that had to succeed on each of its
#              clouds, and oscal/component-definition.json is what the
#              mapping gives (scripts/component.py --check)
#   fixtures   the committed copies of real runs under tests/fixtures/runs
#              are scheduled runs' own files, by the digest GitHub reported;
#              and every "shown failing" run the mapping cites did fail on
#              the line it is cited for (tests/fixtures/violations)
#   images     every container image this repository names is by digest
#   trestle    compliance-trestle validates the component definition and the
#              plan and results of a pack built from each committed run
#   gate       the tests of the builder and the gate (tests/test_pack.py)
#   mutations  each rule of the builder and the gate switched off in turn,
#              and the test named for it fails (scripts/mutate.py)
#   plants     every plant scripts/plant.py knows, on every committed run:
#              each caught, and for its own reason (tests/e2e/plants.sh)
#
# validate.sh EVIDENCE_DIR - compliance-trestle's validator over one pack's
# documents. tests/e2e/run.sh calls it so, and so does anyone checking a
# pack (README, "Check it yourself").
#
# With no arguments every static check runs. The flagship's release and
# NIST's catalog must be in .cache first (scripts/flagship.sh,
# scripts/catalogs.sh), and Python with requirements.lock on PATH.
# tests/static/plants.tsv shows each check the violation it exists for
# (tests/static/plant_violations.py). The check_* functions are called by
# name from the loop at the bottom.
# shellcheck disable=SC2329
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# trestle_validate DIR...: the component definition, and each DIR's
# assessment plan and results, in a trestle workspace made for the purpose.
# Any document trestle refuses fails it, and so does a DIR without both.
trestle_validate() {
  local ws d n rc
  ws="$(mktemp -d)" || return 1
  (
    cd "$ws" || exit 1
    trestle init >/dev/null || exit 1
    mkdir -p component-definitions/flagship
    cp "$ROOT/oscal/component-definition.json" component-definitions/flagship/component-definition.json || exit 1
    for d in "$@"; do
      n="$(basename "$(dirname "$d")")"
      # trestle's own directory names: assessment-plans, assessment-results.
      for doc in assessment-plan:assessment-plans assessment-results:assessment-results; do
        [ -e "$d/${doc%%:*}.json" ] || { echo "no ${doc%%:*}.json in $d"; exit 1; }
        mkdir -p "${doc##*:}/$n" && cp "$d/${doc%%:*}.json" "${doc##*:}/$n/${doc%%:*}.json" || exit 1
      done
    done
    trestle validate -a >validate.log 2>&1 || { cat validate.log >&2; exit 1; }
    valid="$(grep -c '^VALID' validate.log)"
    # Counted, not assumed: a document trestle never looked at is not valid.
    [ "$valid" -eq $((1 + 2 * $#)) ] || { cat validate.log >&2; echo "trestle validated $valid documents, not $((1 + 2 * $#))" >&2; exit 1; }
    echo "== trestle validate: $valid documents valid" \
      "(the component definition, and the plan and results of $# pack(s))"
  )
  rc=$?
  rm -rf "$ws"
  return "$rc"
}

check_component() { python3 scripts/component.py --check; }

check_fixtures() {
  python3 - <<'PY'
import os, re, sys
sys.path.insert(0, "scripts")
import pack

mapping, bad = pack.load_mapping(), []
runs = sorted(os.listdir("tests/fixtures/runs"))
for name in runs:
    r = pack.read_run(os.path.join("tests/fixtures/runs", name))
    cloud, reasons = pack.provenance(mapping, r)
    if reasons:
        bad.append(f"tests/fixtures/runs/{name}: {'; '.join(reasons)}")
    elif name != f"{cloud}-{r['run']['id']}":
        bad.append(f"tests/fixtures/runs/{name} holds {cloud} run {r['run']['id']}")
covered = {pack.cloud_of(mapping, pack.read_run(os.path.join("tests/fixtures/runs", n))["run"]) for n in runs}
for cloud in sorted(set(mapping["clouds"]) - covered):
    bad.append(f"no committed run for {cloud}: its lines are never tried against the mapping")
cited = 0
for check, spec in mapping["checks"].items():
    for cloud, shown in spec.get("shown_failing", {}).items():
        cited += 1
        d = f"tests/fixtures/violations/{cloud}-{shown['run']}"
        if not os.path.isdir(d):
            bad.append(f"{check} on {cloud}: run {shown['run']} is cited as the day it failed, and no copy of it is in {d}")
            continue
        r = pack.read_run(d)
        if pack.cloud_of(mapping, r["run"]) != cloud or r["run"]["id"] != shown["run"]:
            bad.append(f"{d} is not {cloud} run {shown['run']}")
        if r["artifact"] is None or r["artifact"].get("digest") != "sha256:" + pack.sha256(r["archive"] or b""):
            bad.append(f"{d}: the file is not the one GitHub reported for the run")
            continue
        _, _, checks, _ = pack.results_of(r["archive"])
        if not any(re.fullmatch(shown["line"], c["name"]) and c["passed"] is False for c in checks):
            bad.append(f"{check} on {cloud}: run {shown['run']} has no failed line matching {shown['line']!r}")
        if any(re.fullmatch(spec["line"], c["name"]) for c in checks):
            bad.append(f"{check} on {cloud}: run {shown['run']} has the passing line too")
print("\n".join(bad) if bad else
      f"{len(runs)} committed runs are scheduled runs' own files, on {len(covered)} clouds; "
      f"{cited} cited failures are in the runs they are cited from")
sys.exit(1 if bad else 0)
PY
}

check_images() {
  python3 - <<'PY'
import glob, re, sys
bad = []
for path in sorted(glob.glob(".github/workflows/*.yml")):
    for n, line in enumerate(open(path), 1):
        m = re.match(r"\s*-?\s*image:\s*(\S+)", line)
        if m and "@sha256:" not in m.group(1):
            bad.append(f"{path}:{n}: {m.group(1)}")
for n, line in enumerate(open("ci-images.pins"), 1):
    m = re.match(r"^([A-Z0-9_]+_IMAGE)=(\S*)$", line)
    if m and "@sha256:" not in m.group(2):
        bad.append(f"ci-images.pins:{n}: {m.group(1)}={m.group(2)}")
print("images without a digest:\n" + "\n".join(bad) if bad else "every container image is referenced by digest")
sys.exit(1 if bad else 0)
PY
}

check_trestle() {
  local tmp rc d packs=()
  tmp="$(mktemp -d)" || return 1
  for d in tests/fixtures/runs/*/; do
    python3 scripts/pack.py "$d" "$tmp/$(basename "$d")" >/dev/null || { rm -rf "$tmp"; return 1; }
    packs+=("$tmp/$(basename "$d")/evidence")
  done
  trestle_validate "${packs[@]}"
  rc=$?
  rm -rf "$tmp"
  return "$rc"
}

check_gate() {
  python3 -m unittest discover -s tests 2>&1 | tail -3
  return "${PIPESTATUS[0]}"
}

check_mutations() {
  python3 scripts/mutate.py 2>&1 | grep -E '^(MISSED|PLANT DOES NOT APPLY|==|the unchanged)'
  return "${PIPESTATUS[0]}"
}

check_plants() {
  bash tests/e2e/plants.sh 2>&1 | grep -E '^(MISSED|==)'
  return "${PIPESTATUS[0]}"
}

# One argument that names no check and is a directory: a pack's evidence.
if [ $# -eq 1 ] && ! declare -F "check_$1" >/dev/null && [ -d "$1" ]; then
  dir="$(cd "$1" && pwd)"
  cd "$ROOT" || exit 1
  trestle_validate "$dir"
  exit $?
fi

cd "$ROOT" || exit 1
if [ ! -d .cache/flagship/src ] || [ ! -d .cache/catalogs ]; then
  echo "the flagship's release and NIST's catalog are not in .cache: run scripts/flagship.sh and scripts/catalogs.sh first" >&2
  exit 2
fi
checks=("$@")
[ ${#checks[@]} -eq 0 ] && checks=(component fixtures images trestle gate mutations plants)
failed=0
for c in "${checks[@]}"; do
  if ! declare -F "check_$c" >/dev/null; then echo "-- $c: no such check"; failed=1; continue; fi
  if "check_$c"; then echo "-- $c: ok"; else echo "-- $c: FAILED"; failed=1; fi
done
exit "$failed"
