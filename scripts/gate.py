#!/usr/bin/env python3
"""gate.py EVIDENCE_DIR [--live] [--unsigned] [--plant PLANT] - the gate, read from the pack itself.

A pack's findings are not taken on trust. The gate:

1. builds the documents again from the pack's own run/ and the committed
   mapping (scripts/pack.py), which checks again whose file that is, and
   fails if a byte of assessment-plan.json, assessment-results.json,
   verdict.json, summary.md or mapping.yaml differs from what it built;
2. reads the pack's assessment plan and results with compliance-trestle's
   models, and fails unless every control the mapping names for the run's
   cloud has exactly one finding, each "satisfied", and no finding is for
   anything else;
3. has cosign verify the record of the run the pack carries,
   run/record.json, against its Sigstore bundle, for one exact identity:
   the flagship's cloud-results.yml at refs/heads/main;
4. fails on any line of the run's results that did not pass, including one
   no control rests on.

Exits 0 when none of these, 1 when a control or a line fails or a document
differs, 2 when the pack cannot be read, its run/ is not a scheduled run's
own file, or the signature does not verify: no evidence is a failure, never
a pass.

The signature is asked for whenever the gate is given a pack, with no flag.
A record and a run edited alike agree with every other rule here, and only
the signature can tell (the forged-record plant), so a gate that left it to
a flag would pass a forgery to anyone who forgot the flag. It needs cosign
on the PATH and the network, for Sigstore's trust root. --signed, which
asked for this in 1.0.0, is still taken and changes nothing.

--unsigned leaves cosign out, and the last line says so. It is for the
tests of the rules below the signature, which change the record on purpose,
and never how a pack is judged.

With --live it also asks GitHub now for the run's record and the
artifact's digest, and exits 2 unless both are what the pack holds. It
needs no token, the network, and the artifact not yet expired.

With --plant, the run or the pack was broken on purpose (scripts/plant.py),
and the gate must catch it for the planted reason. This judges the plant,
not a pack, and asks cosign only where the plant is about the signature.
It exits 0 only if:

  missing:, failed:, uncontrolled:, renamed:
      exactly the controls resting on the broken lines are not satisfied,
      every other one is satisfied, and the documents are what the run gives;
  forged-findings
      the documents are not what the run gives;
  the plants on whose file it is
      run/ is refused, for that plant's one reason and no other;
  forged-record
      the record and the run beside it were edited alike, so every rule
      that reads them agrees, and cosign must refuse the record.

A plant the gate lets through, or catches for some other reason, exits 1.

With E2E_RESULTS set it writes what it decided there, check by check, for
scripts/status.py: one check per mapped control and one for the run's
lines, or for a plant one check, whether it was caught.
"""
import argparse
import json
import os
import pathlib
import sys

from trestle.oscal.assessment_plan import AssessmentPlan
from trestle.oscal.assessment_results import AssessmentResults

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch  # noqa: E402
import pack  # noqa: E402
import plant as plants  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPPING = os.path.join(ROOT, "mapping", "controls.yaml")


class Unreadable(Exception):
    pass


def read(evidence):
    """{control: [(state, why)]} from the pack's assessment results, both documents parsed by trestle."""
    docs = {}
    for name, model in (("assessment-plan.json", AssessmentPlan), ("assessment-results.json", AssessmentResults)):
        path = pathlib.Path(evidence) / name
        try:
            docs[name] = model.oscal_read(path)
        except Exception as e:
            raise Unreadable(f"cannot read {path}: {e}")
        if docs[name] is None:
            raise Unreadable(f"cannot read {path}")
    found = {}
    for result in docs["assessment-results.json"].results:
        for f in result.findings or []:
            control = next((p.value for p in f.props or [] if p.name == "control" and str(p.ns) == pack.OUR_NS), None)
            state = f.target.status.state
            found.setdefault(control, []).append((getattr(state, "value", str(state)), f.description))
    return found


def rebuilt(mapping, evidence):
    """(verdict, differing files): what the pack's own run/ gives, and which of its documents are not that."""
    files = pack.render(mapping, os.path.join(evidence, "run"))
    files["mapping.yaml"] = pack.read_text(MAPPING)
    differ = []
    for name, text in files.items():
        try:
            same = pack.read_text(os.path.join(evidence, name)) == text
        except OSError:
            same = False
        if not same:
            differ.append(name)
    return json.loads(files["verdict.json"]), differ


def judge(mapping, verdict, found, differ):
    """Every failure the gate sees, as (kind, what, why)."""
    failures = [("documents", name, "not what the pack's own run/ and the mapping give") for name in differ]
    mapped = [c["control"] for c in mapping["controls"] if verdict["cloud"] in c["clouds"]]
    for control in mapped:
        states = found.get(control, [])
        if not states:
            failures.append(("control", control, "no finding in the assessment results"))
        elif len(states) > 1:
            failures.append(("control", control, f"{len(states)} findings in the assessment results; there must be one"))
        elif states[0][0] != "satisfied":
            failures.append(("control", control, f"{states[0][0]}: {states[0][1]}"))
    for control in sorted(set(found) - set(mapped), key=str):
        failures.append(("control", str(control), "a finding for a control the mapping does not name on this cloud"))
    for line in verdict["failed_lines"]:
        failures.append(("line", line, "did not pass in the run"))
    return failures


def signature(mapping, evidence):
    """Why cosign does not verify the pack's record of the run as the flagship's; None when it does."""
    record = os.path.join(evidence, "run", "record.json")
    return fetch.verify(record, record + ".sigstore.json", fetch.signer(mapping))


def live(mapping, verdict):
    """Why GitHub's answer now is not what the pack holds; nothing when it is."""
    repo, run, artifact = mapping["flagship"]["repository"], verdict["run"], verdict["artifact"]
    big = 50 * 1024 * 1024
    now = json.loads(fetch.get(f"{fetch.API}/repos/{repo}/actions/runs/{run['id']}", token=True, limit=big))
    now["repository"] = (now.get("repository") or {}).get("full_name")
    now["head_repository"] = (now.get("head_repository") or {}).get("full_name")
    reasons = [f"GitHub says the run's {k} is {now.get(k)}, the pack says {run.get(k)}"
               for k in ("repository", "head_repository", "path", "event", "head_branch", "head_sha", "status",
                         "conclusion", "run_attempt") if now.get(k) != run.get(k)]
    held = json.loads(fetch.get(f"{fetch.API}/repos/{repo}/actions/artifacts/{artifact['id']}", token=True, limit=big))
    if held.get("expired"):
        reasons.append(f"GitHub no longer holds artifact {artifact['id']}: its digest cannot be asked")
    elif held.get("digest") != artifact["digest"]:
        reasons.append(f"GitHub reports {held.get('digest')} for artifact {artifact['id']}, "
                       f"the pack says {artifact['digest']}")
    return reasons


def emit(checks, measured=()):
    path = os.environ.get("E2E_RESULTS")
    if path:
        with open(path, "w") as f:
            json.dump({"checks": checks, "measured": list(measured)}, f, indent=2)
            f.write("\n")


def state(ok):
    return "PASS" if ok else "FAIL"


def planted(mapping, evidence, plant):
    """(caught, why) for a pack broken on purpose."""
    try:
        verdict, differ = rebuilt(mapping, evidence)
    except pack.Refused as e:
        words, reasons = plants.PROVENANCE.get(plant), str(e).split("; ")
        if words and len(reasons) == 1 and words in reasons[0]:
            return True, f"caught: run/ is refused, and only because {reasons[0]}"
        return False, f"NOT caught for its own reason: run/ is refused because {e}"
    if plant in plants.PROVENANCE:
        return False, "NOT caught: run/ was taken as a scheduled run's own file"
    if plant == "forged-record":
        why = signature(mapping, evidence)
        if why is None:
            return False, "NOT caught: cosign verified a record that was edited"
        if any(w in why for w in ("tuf refresh failed", "error getting live trusted root", "dial tcp", "i/o timeout",
                                  "cannot be run")):
            return False, f"could not be judged: {why}"
        return True, "caught: every rule that reads the record agrees with it, and cosign refuses it"
    if plant == "forged-findings":
        if "assessment-results.json" in differ:
            return True, "caught: the assessment results are not what the pack's own run/ gives"
        return False, "NOT caught: the edited findings were taken as the run's"
    _, must = plants.broken(mapping, verdict["cloud"], plant)
    failed = {what for kind, what, _ in judge(mapping, verdict, read(evidence), differ) if kind == "control"}
    if differ:
        return False, f"NOT caught for its own reason: the documents differ from what run/ gives ({', '.join(differ)})"
    if failed != must:
        return False, (f"NOT caught for its own reason: not satisfied are {sorted(failed) or 'none'}, "
                       f"and the plant breaks {sorted(must)}")
    if plant.startswith("failed:") and not verdict["failed_lines"]:
        return False, "NOT caught: the failed line was not counted"
    return True, f"caught: not satisfied are exactly the controls resting on what it broke ({', '.join(sorted(must))})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("evidence")
    ap.add_argument("--plant")
    ap.add_argument("--live", action="store_true")
    how = ap.add_mutually_exclusive_group()
    how.add_argument("--unsigned", action="store_true")
    how.add_argument("--signed", action="store_true")  # 1.0.0 asked for the signature so; it is asked for anyway
    args = ap.parse_args()
    # Always the committed mapping, never the copy inside the pack.
    mapping = pack.load_mapping(MAPPING)
    if args.plant:
        try:
            caught, why = planted(mapping, args.evidence, args.plant)
        except Unreadable as e:
            caught, why = False, f"NOT caught for its own reason: {e}"
        print(f"== plant {args.plant} {why}")
        emit([{"state": state(caught), "name": f"plant {args.plant}: {why}"}])
        sys.exit(0 if caught else 1)
    try:
        verdict, differ = rebuilt(mapping, args.evidence)
        found = read(args.evidence)
        refused = None if args.unsigned else signature(mapping, args.evidence)
        if refused:
            raise Unreadable(f"the flagship's signature on the run's record does not verify: {refused}")
        gone = live(mapping, verdict) if args.live else []
        if gone:
            raise Unreadable("; ".join(gone))
    except (pack.Refused, Unreadable, SystemExit) as e:
        print(f"gate: {e}", file=sys.stderr)
        emit([{"state": "FAIL", "name": f"the evidence: {e}"}])
        sys.exit(2)
    failures = judge(mapping, verdict, found, differ)
    for kind, what, why in failures:
        print(f"FAIL {kind} {what}: {why}")
    mapped = [c for c in mapping["controls"] if verdict["cloud"] in c["clouds"]]
    bad = {what for kind, what, _ in failures if kind == "control"}
    print(f"== {verdict['cloud']} run {verdict['run']['id']}: {len(mapped) - len(bad & {c['control'] for c in mapped})} "
          f"of {len(mapped)} controls satisfied, {len(verdict['failed_lines'])} of {verdict['lines']} lines failed"
          + (", the flagship's signature on the record was NOT asked for (--unsigned)" if args.unsigned
             else ", the flagship's signature on the record verifies")
          + (", GitHub's record and digest agree" if args.live else ""))
    why = {what: reason for kind, what, reason in failures if kind == "control"}
    emit([{"state": state(c["control"] not in why), "name": f"{c['name']}: {why.get(c['control'], 'satisfied')}"}
          for c in mapped]
         + [{"state": state(not verdict["failed_lines"] and not differ),
             "name": f"{verdict['lines']} lines in the run's results, {len(verdict['failed_lines'])} failed; "
                     + ("the documents are what the run gives" if not differ else f"documents differ: {differ}")}],
         [f"controls satisfied: {len(mapped) - len(why)} of {len(mapped)}"])
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
