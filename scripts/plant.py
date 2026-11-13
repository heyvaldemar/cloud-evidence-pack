#!/usr/bin/env python3
"""plant.py DIR PLANT - break one run's files on purpose, so the gate can be shown it.

DIR holds a run as scripts/fetch.py wrote it: a fetched run, or the run/
inside a pack. Two families of plants.

The run did something else. The results inside the artifact are rewritten
and the artifact's record is made to agree, as if the run itself had written
them, so only the control's own rule can catch it:

  missing:<control>       every refusal line the control rests on is gone
  failed:<control>        one of its refusal lines says the violation got in
  uncontrolled:<control>  every line that had to succeed beside them is gone
  renamed:<check>         the flagship renamed one line the mapping names

The file is not that run's. The record or the file is changed and nothing is
made to agree:

  forged-results    one check inside the artifact flipped, the digest left as it was
  by-hand           the run was started by workflow_dispatch
  branch            the run was on another branch
  other-workflow    the run was the kind e2e's, not a cloud's
  other-repository  the run was a fork's
  red-run           the run failed
  other-run         the artifact belongs to another run
  no-artifact       the run kept no artifact
  unsigned          the record's signature is gone
  no-record         the record the flagship signed is gone
  record-mismatch   the run's record beside the signed one says something else

The record and the run were edited alike, so nothing that reads them can
tell, and only the signature can:

  forged-record     both say the run ended at another time

A pack edited after it was built. DIR is a pack's evidence directory:

  forged-findings   every finding that says not-satisfied is made to say
                    satisfied; the documents still parse

  plant.py all DIR     every plant that applies to the run in DIR, one a line:
                       its cloud's, for the controls that run is asked for
  plant.py first DIR   the first control the run in DIR is asked for
"""
import io
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pack  # noqa: E402

PROVENANCE = {
    "forged-results": "it is not the run's file",
    "by-hand": "not by the schedule",
    "branch": "a run on ",
    "other-workflow": "which is no cloud's workflow",
    "other-repository": "a run of ",
    "red-run": "not a run that passed",
    "other-run": "the artifact is run ",
    "no-artifact": "the run kept no artifact",
    "unsigned": "no record signed by the flagship",
    "no-record": "no record signed by the flagship",
    "record-mismatch": "not the one in the record the flagship signed",
}
CONTROL_PLANTS = ("missing", "failed", "uncontrolled")


def checks_on(mapping, cloud, control):
    return [g for g in control["checks"] if cloud in mapping["checks"][g]["clouds"]]


def broken(mapping, cloud, plant, run):
    """(the checks a plant breaks, the controls that must then be not satisfied) in one run of a cloud."""
    kind, _, what = plant.partition(":")
    controls = pack.asked(mapping, cloud, run)
    if kind in CONTROL_PLANTS:
        c = next((c for c in controls if c["control"] == what), None)
        if c is None:
            raise SystemExit(f"plant {plant}: {what} is not asked of {cloud} run {run['id']}")
        want = "control" if kind == "uncontrolled" else "refusal"
        groups = [g for g in checks_on(mapping, cloud, c) if mapping["checks"][g]["kind"] == want]
        groups = groups[:1] if kind == "failed" else groups
    elif kind == "renamed" and any(what in checks_on(mapping, cloud, c) for c in controls):
        groups = [what]
    else:
        raise SystemExit(f"unknown plant {plant} in {cloud} run {run['id']}")
    return groups, {c["control"] for c in controls if set(groups) & set(checks_on(mapping, cloud, c))}


def every(mapping, cloud, run):
    controls = pack.asked(mapping, cloud, run)
    used = dict.fromkeys(g for c in controls for g in checks_on(mapping, cloud, c))
    return ([f"{k}:{c['control']}" for c in controls for k in CONTROL_PLANTS] + [f"renamed:{g}" for g in used]
            + list(PROVENANCE) + ["forged-findings", "forged-record"])


def rewrite_results(directory, artifact, change, agree):
    """The artifact with its e2e-results.json changed; with agree, its record made to match the new file."""
    path = os.path.join(directory, artifact["name"] + ".zip")
    with open(path, "rb") as f:
        old = zipfile.ZipFile(io.BytesIO(f.read()))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as new:
        for name in old.namelist():
            body = old.read(name)
            if name.rsplit("/", 1)[-1] == "e2e-results.json":
                doc = json.loads(body)
                change(doc)
                body = (json.dumps(doc, indent=1) + "\n").encode()
            new.writestr(zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0)), body)
    with open(path, "wb") as f:
        f.write(out.getvalue())
    if agree:
        artifact["digest"], artifact["size_in_bytes"] = "sha256:" + pack.sha256(out.getvalue()), len(out.getvalue())
        # The signed record is made to agree too, as if the flagship had kept this file: the signature no longer
        # holds, and no rule below the signature can tell.
        record = os.path.join(directory, "record.json")
        if os.path.exists(record):
            doc = json.loads(pack.read_text(record))
            doc["artifact"]["sha256"], doc["artifact"]["size_in_bytes"] = pack.sha256(out.getvalue()), len(out.getvalue())
            with open(record, "w", encoding="utf-8") as f:
                json.dump(doc, f, indent=1, sort_keys=True)
                f.write("\n")


def forge(evidence):
    path = os.path.join(evidence, "assessment-results.json")
    text = pack.read_text(path)
    if '"state": "not-satisfied"' not in text:
        raise SystemExit("plant forged-findings: the pack has no finding short of satisfied to edit")
    for old, new in (('"state": "not-satisfied"', '"state": "satisfied"'), ('"reason": "fail"', '"reason": "pass"'),
                     (': not-satisfied"', ': satisfied"')):
        text = text.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def apply(mapping, directory, plant):
    if plant == "forged-findings":
        return forge(directory)
    r = pack.read_run(directory)
    run, artifact = r["run"], r["artifact"]
    cloud = pack.cloud_of(mapping, run)
    kind = plant.partition(":")[0]
    if kind in CONTROL_PLANTS + ("renamed",):
        groups, _ = broken(mapping, cloud, plant, run)
        _, _, checks, _ = pack.results_of(r["archive"])
        lines = [l for g in groups for l in pack.match(mapping["checks"][g], checks, r["plants"], cloud)[0]]
        names = [c["name"] for c in lines]
        if not names:
            raise SystemExit(f"plant {plant}: the run has none of the lines it breaks")

        def change(doc):
            if kind == "failed":
                next(c for c in doc["checks"] if c["name"] == names[0])["passed"] = False
            elif kind == "renamed":
                next(c for c in doc["checks"] if c["name"] == names[0])["name"] += ", as the next release words it"
            else:
                doc["checks"] = [c for c in doc["checks"] if c["name"] not in names]

        rewrite_results(directory, artifact, change, agree=True)
    elif plant == "forged-results":
        def flip(doc):
            doc["checks"][0]["passed"] = not doc["checks"][0]["passed"]
        rewrite_results(directory, artifact, flip, agree=False)
    elif plant == "by-hand":
        run["event"] = "workflow_dispatch"
    elif plant == "branch":
        run["head_branch"] = "gpu-capacity"
    elif plant == "other-workflow":
        run["path"] = ".github/workflows/e2e.yml"
    elif plant == "other-repository":
        run["repository"] = run["head_repository"] = "someone/kubernetes-air-gapped-ai-agent"
    elif plant == "red-run":
        run["conclusion"] = "failure"
    elif plant == "other-run":
        artifact["run_id"] = run["id"] + 1
    elif plant == "no-artifact":
        os.remove(os.path.join(directory, artifact["name"] + ".zip"))
        os.remove(os.path.join(directory, "artifact.json"))
        artifact = None
    elif plant == "unsigned":
        os.remove(os.path.join(directory, "record.json.sigstore.json"))
    elif plant == "no-record":
        os.remove(os.path.join(directory, "record.json"))
    elif plant in ("record-mismatch", "forged-record"):
        run["updated_at"] = run["updated_at"][:-3] + ("59Z" if not run["updated_at"].endswith("59Z") else "58Z")
    else:
        raise SystemExit(f"unknown plant {plant}")
    for name, doc in (("run.json", run), ("artifact.json", artifact)):
        if doc is not None:
            with open(os.path.join(directory, name), "w") as f:
                json.dump(doc, f, indent=1, sort_keys=True)
                f.write("\n")
    # A run that is not a scheduled run's is planted in the record too, as a record that says so would read:
    # the rule on the run must catch it alone. Only record-mismatch leaves the record as it was.
    record = os.path.join(directory, "record.json")
    if plant in ("by-hand", "branch", "other-workflow", "other-repository", "red-run", "forged-record") \
            and os.path.exists(record):
        doc = json.loads(pack.read_text(record))
        doc["run"] = run
        with open(record, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=1, sort_keys=True)
            f.write("\n")


def main(argv):
    mapping = pack.load_mapping()
    if len(argv) == 2 and argv[0] in ("all", "first") and os.path.isdir(argv[1]):
        run = pack.read_run(argv[1])["run"]
        cloud = pack.cloud_of(mapping, run)
        if cloud is None:
            raise SystemExit(f"plant.py {argv[0]}: the run in {argv[1]} is of no cloud's workflow")
        if argv[0] == "all":
            print("\n".join(every(mapping, cloud, run)))
        else:
            print(pack.asked(mapping, cloud, run)[0]["control"])
        return 0
    if len(argv) != 2 or not os.path.isdir(argv[0]):
        sys.stderr.write(__doc__)
        return 2
    apply(mapping, argv[0], argv[1])
    print(f"== planted {argv[1]} in {argv[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
