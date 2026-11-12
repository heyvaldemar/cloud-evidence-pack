#!/usr/bin/env bash
# run.sh - one scheduled cloud run of the flagship made into a pack and
# judged, as CI does it. The steps are the scripts in scripts/; this is the
# order they run in. The pack lands in .cache/run/<name>/evidence.
#
#   RUN=<run id>     read that run from the flagship's signed branch
#                    (scripts/fetch.py), with no token
#   RUN_DIR=<dir>    or a run already read: a committed copy under
#                    tests/fixtures/runs
#   PLANT=<plant>    break it on purpose (scripts/plant.py names them all);
#                    the gate must catch it, and for that plant's reason
#   LIVE=1           the gate also asks GitHub now for the run's record and
#                    the artifact's digest
#   UNSIGNED=1       the gate leaves cosign out. Without it the gate has
#                    cosign verify the flagship's signature on the run's
#                    record, as it does for anyone who runs it on a pack
#
# No cluster and no cloud account: the run already happened. Needs Python
# 3.11 or later with requirements.lock installed, and curl, cosign and
# slsa-verifier (scripts/install-tools.sh): for NIST's catalog and the
# flagship's release the first time, and cosign each time the gate verifies
# the flagship's signature, with the network for Sigstore's trust root.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
PLANT="${PLANT:-}"
if [ -n "${RUN:-}" ]; then name="run-$RUN"; else name="$(basename "${RUN_DIR:?set RUN to a run id, or RUN_DIR to a run already read}")"; fi
STATE="$ROOT/.cache/run/$name${PLANT:+-${PLANT//:/-}}"
rm -rf "$STATE" && mkdir -p "$STATE"

bash scripts/flagship.sh
bash scripts/catalogs.sh
python3 scripts/component.py --check
if [ -n "${RUN:-}" ]; then
  python3 scripts/fetch.py run "$RUN" "$STATE/fetched"
else
  cp -R "$RUN_DIR" "$STATE/fetched"
fi

case "$PLANT" in
  "")
    python3 scripts/pack.py "$STATE/fetched" "$STATE"
    bash scripts/validate.sh "$STATE/evidence"
    python3 scripts/gate.py "$STATE/evidence" ${LIVE:+--live} ${UNSIGNED:+--unsigned}
    ;;
  missing:*|failed:*|uncontrolled:*|renamed:*)
    # The run did something else: the pack is built from it, and the gate
    # must call exactly the controls that rest on it not satisfied.
    python3 scripts/plant.py "$STATE/fetched" "$PLANT"
    python3 scripts/pack.py "$STATE/fetched" "$STATE"
    bash scripts/validate.sh "$STATE/evidence"
    python3 scripts/gate.py "$STATE/evidence" --plant "$PLANT"
    ;;
  forged-record)
    # The record and the run beside it edited alike: the pack builds, every
    # rule that reads them agrees, and only cosign can refuse it.
    python3 scripts/plant.py "$STATE/fetched" "$PLANT"
    python3 scripts/pack.py "$STATE/fetched" "$STATE"
    bash scripts/validate.sh "$STATE/evidence"
    python3 scripts/gate.py "$STATE/evidence" --plant "$PLANT"
    # And the gate as a reader runs it, given the pack and no flag at all,
    # must refuse it too, and for the signature.
    rc=0; env -u E2E_RESULTS python3 scripts/gate.py "$STATE/evidence" >"$STATE/gate-no-flags.log" 2>&1 || rc=$?
    if [ "$rc" -eq 0 ]; then
      echo "the gate, given the pack and no flag, passed a record that was edited" >&2; exit 1
    fi
    if ! grep -qF "signature on the run's record does not verify" "$STATE/gate-no-flags.log"; then
      echo "the gate, given no flag, refused the edited record for another reason (exit $rc): $(tail -n 1 "$STATE/gate-no-flags.log")" >&2; exit 1
    fi
    ;;
  forged-findings)
    # A run with a violation that got in, and a pack edited afterwards to say
    # every control is satisfied. trestle still reads it; the gate must not.
    first="$(python3 scripts/plant.py first "$STATE/fetched")"
    python3 scripts/plant.py "$STATE/fetched" "failed:$first"
    python3 scripts/pack.py "$STATE/fetched" "$STATE"
    python3 scripts/plant.py "$STATE/evidence" forged-findings
    bash scripts/validate.sh "$STATE/evidence"
    python3 scripts/gate.py "$STATE/evidence" --plant "$PLANT"
    ;;
  *)
    # The file is not that run's. Twice: the builder must refuse to make a
    # pack of it, and the gate must refuse a pack whose run/ was changed
    # after it was built.
    cp -R "$STATE/fetched" "$STATE/planted"
    python3 scripts/plant.py "$STATE/planted" "$PLANT"
    rc=0; python3 scripts/pack.py "$STATE/planted" "$STATE/refused" || rc=$?
    if [ "$rc" -ne 2 ] || [ -e "$STATE/refused/evidence" ]; then
      echo "the builder made a pack of a run planted with $PLANT (exit $rc)" >&2; exit 1
    fi
    python3 scripts/pack.py "$STATE/fetched" "$STATE"
    python3 scripts/plant.py "$STATE/evidence/run" "$PLANT"
    python3 scripts/gate.py "$STATE/evidence" --plant "$PLANT"
    ;;
esac
