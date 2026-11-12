#!/usr/bin/env bash
# packs.sh OUT_DIR [HELD_DIR] - a pack for every scheduled cloud run that
# passed and has none yet, and the index of every scheduled run.
#
#   MODE=new       (the default) the scheduled runs of the last DAYS days (14)
#                  that passed and have no pack under HELD_DIR/<cloud>/<run id>
#   MODE=newest    for each cloud, the newest scheduled run that passed and
#                  that the flagship's branch holds a signed record of,
#                  whether or not a pack of it is held: what a release
#                  carries. A newer run that passed and is not on the branch
#                  is named, and passed over
#   MODE=fixtures  the committed copies under tests/fixtures/runs, with
#                  nothing read from GitHub: what a pull request can run
#
# Each run goes through tests/e2e/run.sh: read from the flagship's signed
# branch, built, validated by trestle, judged by the gate, which verifies the
# flagship's signature on the run's record and, for a run read now, asks
# GitHub again for the run's record and the artifact's digest. A pack that
# passes is packed into
#
#   OUT_DIR/<cloud>/<run id>/cloud-evidence-pack-<cloud>-<run id>.tar.gz
#
# a deterministic archive (sorted names, one owner, the run's own time), with
# its verdict.json and summary.md beside it. Signing is the workflow's step.
#
# Three outcomes are kept apart (scripts/index.py):
#   - a run that passed and whose pack is refused or fails the gate leaves
#     OUT_DIR/<cloud>/<run id>/refused.txt, and this script exits 1 at the end;
#   - a run that failed gets no pack, is listed, and fails nothing here: it
#     already failed where it ran;
#   - a cloud with no scheduled run to read is reported as missing, and
#     fails nothing.
#
# No cloud workflow is started from here, ever: the runs are only read.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 2
OUT="${1:?packs.sh OUT_DIR [HELD_DIR]}"
HELD="${2:-$OUT}"
MODE="${MODE:-new}"
DAYS="${DAYS:-14}"
mkdir -p "$OUT" "$ROOT/.cache/runs"
OUT="$(cd "$OUT" && pwd)"; HELD="$(mkdir -p "$HELD" && cd "$HELD" && pwd)"
failed=0

archive() { # archive EVIDENCE_PARENT DEST: evidence/ as a deterministic tar.gz
  python3 - "$1" "$2" <<'PY'
import datetime, gzip, json, os, sys, tarfile
parent, dest = sys.argv[1], sys.argv[2]
run = json.load(open(os.path.join(parent, "evidence", "run", "run.json")))
when = int(datetime.datetime.fromisoformat(run["updated_at"].replace("Z", "+00:00")).timestamp())


def plain(info):
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mtime = when
    info.mode = 0o755 if info.isdir() else 0o644
    return info


with open(dest, "wb") as f, gzip.GzipFile(filename="", mode="wb", fileobj=f, mtime=0) as gz, \
        tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
    names = ["evidence"]
    for base, dirs, files in os.walk(os.path.join(parent, "evidence")):
        names += [os.path.relpath(os.path.join(base, n), parent) for n in dirs + files]
    for name in sorted(names):
        tar.add(os.path.join(parent, name), arcname=name, recursive=False, filter=plain)
PY
}

one() { # one CLOUD RUN_ID [RUN_DIR]
  local cloud="$1" id="$2" dir="${3:-}" state log dest rc=0
  dest="$OUT/$cloud/$id"
  mkdir -p "$dest"
  log="$ROOT/.cache/runs/$cloud-$id.log"
  if [ -n "$dir" ]; then
    state="$ROOT/.cache/run/$(basename "$dir")"
    RUN_DIR="$dir" bash tests/e2e/run.sh >"$log" 2>&1 || rc=$?
  else
    state="$ROOT/.cache/run/run-$id"
    RUN="$id" LIVE=1 bash tests/e2e/run.sh >"$log" 2>&1 || rc=$?
  fi
  if [ "$rc" -ne 0 ]; then
    # The builder's or the gate's own last words, never the whole log.
    grep -E '^(pack: refused|gate:|FAIL |fetch:)' "$log" | tail -n 5 >"$dest/refused.txt"
    [ -s "$dest/refused.txt" ] || tail -n 3 "$log" >"$dest/refused.txt"
    echo "NO PACK  $cloud run $id (exit $rc): $(tr '\n' ' ' <"$dest/refused.txt" | cut -c1-300)"
    failed=1
    return
  fi
  cp "$state/evidence/verdict.json" "$state/evidence/summary.md" "$dest/"
  archive "$state" "$dest/cloud-evidence-pack-$cloud-$id.tar.gz"
  echo "pack     $(grep -E "^== .* controls satisfied" "$log" | tail -n 1 | sed "s/^== //")"
}

bash scripts/flagship.sh || exit 2
bash scripts/catalogs.sh >/dev/null || exit 2
mkdir -p "$ROOT/.cache/runs/lists"
kept=""
if [ "$MODE" != fixtures ]; then
  kept="$(python3 scripts/fetch.py kept | tr '\n' ' ')" || { echo "the flagship's branch of signed records cannot be read" >&2; exit 2; }
fi
for cloud in $(python3 -c 'import sys; sys.path.insert(0, "scripts"); import pack; print(" ".join(pack.load_mapping()["clouds"]))'); do
  if [ "$MODE" = fixtures ]; then
    echo "[]" >"$ROOT/.cache/runs/lists/$cloud.json"
    for dir in tests/fixtures/runs/"$cloud"-*/; do
      [ -d "$dir" ] || continue
      id="$(basename "$dir")"; one "$cloud" "${id#*-}" "${dir%/}"
    done
    continue
  fi
  if ! python3 scripts/fetch.py list "$cloud" >"$ROOT/.cache/runs/lists/$cloud.json"; then
    echo "the scheduled runs of $cloud cannot be listed" >&2; exit 2
  fi
  ids="$(MODE="$MODE" DAYS="$DAYS" KEPT="$kept" python3 - "$ROOT/.cache/runs/lists/$cloud.json" "$HELD/$cloud" <<'PY'
import datetime, json, os, sys
runs, held = json.load(open(sys.argv[1])), sys.argv[2]
passed = [r for r in sorted(runs, key=lambda r: r["created_at"], reverse=True)
          if r.get("status") == "completed" and r.get("conclusion") == "success"]
if os.environ["MODE"] == "newest":
    kept = set(os.environ["KEPT"].split())
    for r in passed:
        if str(r["id"]) in kept:
            break
        print(f"passed over: scheduled run {r['id']} of {r['created_at'][:10]} passed, and the flagship's branch "
              "holds no signed record of it", file=sys.stderr)
    passed = [r for r in passed if str(r["id"]) in kept][:1]
else:
    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=int(os.environ["DAYS"]))
    passed = [r for r in passed
              if datetime.datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) >= since
              and not os.path.exists(os.path.join(held, str(r["id"]), "verdict.json"))]
print(" ".join(str(r["id"]) for r in passed))
PY
)" || exit 2
  [ -n "$ids" ] || echo "nothing   $cloud: no scheduled run that passed is waiting for a pack"
  for id in $ids; do one "$cloud" "$id"; done
done

# The index reads what is held and what was just built, as one tree.
merged="$(mktemp -d)"
cp -R "$HELD/." "$merged/" 2>/dev/null || true
[ "$OUT" = "$HELD" ] || cp -R "$OUT/." "$merged/"
if [ "$MODE" != fixtures ]; then
  python3 scripts/index.py "$ROOT/.cache/runs/lists" "$merged" "$OUT" || { rm -rf "$merged"; exit 2; }
fi
rm -rf "$merged"
exit "$failed"
