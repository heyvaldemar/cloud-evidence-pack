#!/usr/bin/env python3
"""pack.py RUN_DIR OUT_DIR - one scheduled cloud run of the flagship, as OSCAL evidence.

RUN_DIR is what scripts/fetch.py wrote: the record of the run the flagship
signed and kept, the run's artifact, and the planted pods at the run's
commit. The pack is written to OUT_DIR/evidence:

  summary.md               the table to read first
  assessment-results.json  one observation per line of the run the mapping
                           names, verbatim; one finding per mapped control
  assessment-plan.json     what was to be looked at, and by which lines
  verdict.json             the same, for a program
  mapping.yaml             the mapping it was judged by
  run/                     RUN_DIR itself: the artifact inside is the run's

Three steps, in this order:

1. Whose file this is. Beside the run there must be the record the
   flagship's own workflow signed, with its signature, and what is read of
   the run and of its artifact must be exactly what that record says. The
   run must be the flagship's, by a cloud's own workflow, started by the
   schedule, on the flagship's branch, complete and passed; the artifact
   must be that run's, and the file's sha256 must be the one the signed
   record names. Anything else is refused: exit 2, and nothing is written.
   A run started by hand is never a pack's source. The signature itself is
   verified by scripts/fetch.py when the run is read and by scripts/gate.py
   on the pack: here the bundle is only required to be there (has_bundle).
2. What the run did. Each check the mapping names for this cloud is looked
   for in the run's e2e-results.json, by the whole line. A planted pod's
   line must carry the words its own file expects, read at the run's commit.
3. What that says of each control. A control is "satisfied" only when every
   check it names is in the run and passed, at least one of them is a
   refusal (a violation tried and turned away in this run) and at least one
   is a control that had to succeed. Anything else is "not-satisfied", and
   the finding says why. A line the mapping names and the run lacks is never
   skipped.

The documents are a function of RUN_DIR and the mapping and nothing else: no
clock, no random id. scripts/gate.py builds them again from the pack's own
run/ and fails if a byte differs, so a finding cannot be edited afterwards.

Every document is read back by compliance-trestle's models before it is
kept. Exits 0 when a pack is written, whatever its findings say (judging is
the gate's work), and 2 when the run is refused or cannot be read: no
evidence is a failure, never a pass.
"""
import collections
import hashlib
import html
import io
import json
import os
import pathlib
import re
import shutil
import sys
import uuid
import zipfile

from ruamel.yaml import YAML
from trestle.oscal import OSCAL_VERSION
from trestle.oscal.assessment_plan import AssessmentPlan
from trestle.oscal.assessment_results import AssessmentResults

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUR_NS = "https://github.com/heyvaldemar/cloud-evidence-pack/ns"
SEED = uuid.UUID("5d0c7a3e-91b4-4f6a-a2c8-3e7b1f9d6c20")
INSIDE = "registry.boundary.internal:5000"  # the registry's name in a plant's "# expect:" line
MAX_RESULTS = 5 * 1024 * 1024
KINDS = ("refusal", "control", "gate")


class Refused(Exception):
    """The run, or its file, is not something a pack may be built from."""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def load_mapping(path=None):
    path = path or os.environ.get("MAPPING") or os.path.join(ROOT, "mapping", "controls.yaml")
    return YAML(typ="safe").load(read_text(path))


def read_json(path, what):
    try:
        return json.loads(read_text(path))
    except (OSError, ValueError) as e:
        raise Refused(f"{what} cannot be read: {e}")


def read_run(run_dir):
    """What fetch.py kept of one run. The artifact and its record are None when the run kept none."""
    r = {"run": read_json(os.path.join(run_dir, "run.json"), "the run's record"),
         "jobs": [], "artifact": None, "archive": None, "plants": {}, "record": None, "record_sha256": None,
         # Only that a bundle is there. Whether it verifies is cosign's to say: scripts/fetch.py asks when the
         # run is read, and scripts/gate.py asks again on the pack.
         "has_bundle": os.path.exists(os.path.join(run_dir, "record.json.sigstore.json"))}
    if os.path.exists(os.path.join(run_dir, "record.json")):
        r["record"] = read_json(os.path.join(run_dir, "record.json"), "the record the flagship signed")
        with open(os.path.join(run_dir, "record.json"), "rb") as f:
            r["record_sha256"] = sha256(f.read())
    if os.path.exists(os.path.join(run_dir, "jobs.json")):
        r["jobs"] = read_json(os.path.join(run_dir, "jobs.json"), "the run's jobs")
    if os.path.exists(os.path.join(run_dir, "artifact.json")):
        r["artifact"] = read_json(os.path.join(run_dir, "artifact.json"), "the artifact's record")
        try:
            with open(os.path.join(run_dir, f"{r['artifact'].get('name')}.zip"), "rb") as f:
                r["archive"] = f.read()
        except OSError:
            r["archive"] = None
    plants = os.path.join(run_dir, "plants")
    for name in sorted(os.listdir(plants)) if os.path.isdir(plants) else []:
        if name.endswith(".yaml"):
            r["plants"][name[:-5]] = read_text(os.path.join(plants, name))
    return r


def cloud_of(mapping, run):
    return next((c for c, spec in mapping["clouds"].items() if spec["workflow"] == run.get("path")), None)


def provenance(mapping, r):
    """(cloud, reasons): why this is not a scheduled run's own file; no reasons when it is."""
    flagship, run, reasons = mapping["flagship"], r["run"], []
    cloud = cloud_of(mapping, run)
    record = r.get("record")
    if record is None or not r.get("has_bundle"):
        reasons.append("no record signed by the flagship is beside the run: the record or its signature is missing")
        record = None
    else:
        if record.get("repository") != flagship["repository"] or record.get("kept_by") != flagship["signer"]:
            reasons.append(f"the record was kept by {record.get('kept_by')} of {record.get('repository')}, "
                           f"not by {flagship['signer']} of {flagship['repository']}")
        if record.get("run") != run:
            reasons.append("the run's record here is not the one in the record the flagship signed")
    if run.get("repository") != flagship["repository"] or run.get("head_repository") != flagship["repository"]:
        reasons.append(f"a run of {run.get('repository')} from {run.get('head_repository')}, "
                       f"not of {flagship['repository']}")
    if cloud is None:
        reasons.append(f"a run of {run.get('path')}, which is no cloud's workflow")
    if run.get("event") != "schedule":
        reasons.append(f"started by {run.get('event')}, not by the schedule")
    if run.get("head_branch") != flagship["branch"]:
        reasons.append(f"a run on {run.get('head_branch')}, not on {flagship['branch']}")
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        reasons.append(f"the run is {run.get('status')} with conclusion {run.get('conclusion')}, not a run that passed")
    artifact, archive = r["artifact"], r["archive"]
    if artifact is None:
        reasons.append("the run kept no artifact to read, or it has expired")
        return cloud, reasons
    if archive is None:
        reasons.append("the run kept no artifact to read: its record is here and its file is not")
        return cloud, reasons
    if cloud is not None and artifact.get("name") != mapping["clouds"][cloud]["artifact"]:
        reasons.append(f"the artifact is {artifact.get('name')}, not {mapping['clouds'][cloud]['artifact']}")
    if artifact.get("run_id") != run.get("id") or artifact.get("head_sha") != run.get("head_sha"):
        reasons.append(f"the artifact is run {artifact.get('run_id')}'s at {str(artifact.get('head_sha'))[:7]}, "
                       f"not run {run.get('id')}'s")
    kept = (record or {}).get("artifact") or {}
    if record is not None and ("sha256:" + str(kept.get("sha256")) != artifact.get("digest")
                               or kept.get("id") != artifact.get("id")):
        reasons.append("the artifact's record here is not the one in the record the flagship signed")
    if artifact.get("digest") != "sha256:" + sha256(archive):
        reasons.append(f"the file's sha256 is {sha256(archive)}, and the signed record names {artifact.get('digest')} "
                       "for the artifact: it is not the run's file")
    return cloud, reasons


def results_of(archive):
    """(member, sha256, checks, measured) from the one e2e-results.json the artifact holds."""
    try:
        z = zipfile.ZipFile(io.BytesIO(archive))
    except zipfile.BadZipFile:
        raise Refused("the artifact is not a zip archive")
    members = [n for n in z.namelist() if n.rsplit("/", 1)[-1] == "e2e-results.json"]
    if len(members) != 1:
        raise Refused(f"the artifact holds {len(members)} files named e2e-results.json; there must be one")
    if z.getinfo(members[0]).file_size > MAX_RESULTS:
        raise Refused("the artifact's e2e-results.json is larger than this reads")
    body = z.read(members[0])
    try:
        doc = json.loads(body)
    except ValueError as e:
        raise Refused(f"the artifact's e2e-results.json is not JSON: {e}")
    checks = doc.get("checks") if isinstance(doc, dict) else None
    if not isinstance(checks, list) or not checks or not all(
            isinstance(c, dict) and isinstance(c.get("name"), str) and isinstance(c.get("passed"), bool)
            for c in checks):
        raise Refused("the artifact's e2e-results.json has no list of checks, each a name and whether it passed")
    return members[0], sha256(body), checks, [m for m in doc.get("measured") or [] if isinstance(m, str)]


def turns(lines):
    """Each line with its turn among the same words. A run can write one line more than once, once each time it
    does the same thing, and each is a line of the run."""
    seen, out = collections.Counter(), []
    for line in lines:
        out.append((line, seen[line]))
        seen[line] += 1
    return out


def plant_line(name, text):
    """(pattern, kind) for the line the flagship's e2e writes when a planted pod did what its file expects."""
    m = re.search(r"^# expect: (.+)$", text, re.M)
    if not m:
        return None, None
    expect = m.group(1).strip()
    if expect == "admitted":
        return re.compile(re.escape(f"{name}: admitted")), "control"
    words = re.escape(expect).replace(re.escape(INSIDE), r"\S+")
    return re.compile(re.escape(f"{name}: refused (") + words + re.escape(")")), "refusal"


def needed(spec, cloud):
    """How many of the run's lines a check must match on one cloud."""
    need = spec.get("at_least", 1)
    return need.get(cloud, 1) if isinstance(need, dict) else need


def match(spec, checks, plants, cloud):
    """(lines, why): the run's lines one check of the mapping names, and why it does not hold (None when it does)."""
    if "plant" in spec:
        text = plants.get(spec["plant"])
        if text is None:
            return [], f"the run's commit has no planted pod {spec['plant']}"
        pattern, kind = plant_line(spec["plant"], text)
        if pattern is None:
            return [], f"the planted pod {spec['plant']} does not say what it expects"
        if kind != spec["kind"]:
            return [], f"the planted pod {spec['plant']} expects a {kind}, and the mapping calls it a {spec['kind']}"
    else:
        pattern = re.compile(spec["line"])
    lines = [c for c in checks if pattern.fullmatch(c["name"])]
    need = needed(spec, cloud)
    if len(lines) < need:
        return lines, f"{len(lines)} of the run's lines match, and {need} must"
    failed = [c["name"] for c in lines if c["passed"] is not True]
    if failed:
        return lines, "failed: " + "; ".join(failed)
    return lines, None


def judge(mapping, cloud, checks, plants):
    """Every check the mapping names for this cloud, against the run's lines, and each control's state."""
    held = {}
    for name, spec in mapping["checks"].items():
        if cloud in spec["clouds"]:
            lines, why = match(spec, checks, plants, cloud)
            held[name] = {"kind": spec["kind"], "ok": why is None, "why": why, "lines": [c["name"] for c in lines]}
    # Lines the flagship writes side by side: as many of one as of the others, however many times the run wrote them.
    for group in mapping.get("written_together", []):
        mine = [g for g in group if g in held]
        most = max((len(held[g]["lines"]) for g in mine), default=0)
        for g in mine:
            n = len(held[g]["lines"])
            if held[g]["ok"] and n < most:
                beside = next(o for o in mine if len(held[o]["lines"]) == most)
                held[g].update(ok=False, why=f"{n} of the run's lines match, and {most} match {beside}, "
                                             f"which the run writes beside it each time")
    controls = {}
    for c in mapping["controls"]:
        if cloud not in c["clouds"]:
            continue
        mine = [g for g in c["checks"] if g in held]
        reasons = [f"{g}: {held[g]['why']}" for g in mine if not held[g]["ok"]]
        if not any(held[g]["kind"] == "refusal" for g in mine):
            reasons.append("the mapping names no violation this cloud's run refuses")
        if not any(held[g]["kind"] == "control" for g in mine):
            reasons.append("the mapping names nothing that had to succeed beside the refusals")
        controls[c["control"]] = {"state": "not-satisfied" if reasons else "satisfied", "why": reasons,
                                  "checks": {k: [g for g in mine if held[g]["kind"] == k] for k in KINDS}}
    return {"checks": held, "controls": controls,
            "lines": len(checks), "failed_lines": [c["name"] for c in checks if c["passed"] is not True]}


# --- the OSCAL documents ---------------------------------------------------

_CATALOGS = {}
_CROSSWALKS = {}


def pinned(name):
    """(address, sha256) of one file catalogs.lock pins."""
    for line in read_text(os.path.join(ROOT, "catalogs.lock")).splitlines():
        if line.strip() and not line.startswith("#") and line.split()[0] == name:
            return line.split()[1], line.split()[2]
    return None, None


def crosswalk(mapping, name):
    """{control id: [elements]} from one pinned crosswalk: what its publisher relates to each control, and to
    that control alone. An enhancement's row is its own, never its base control's."""
    if name in _CROSSWALKS:
        return _CROSSWALKS[name]
    z = zipfile.ZipFile(os.path.join(ROOT, ".cache", "catalogs", mapping["crosswalks"][name]["file"]))
    strings = [html.unescape(re.sub(r"<[^>]+>", "", s))
               for s in re.findall(r"<si>(.*?)</si>", z.read("xl/sharedStrings.xml").decode("utf-8"), flags=re.S)]
    out = {}
    for sheet in sorted(n for n in z.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)):
        for row in re.findall(r"<row [^>]*>(.*?)</row>", z.read(sheet).decode("utf-8"), flags=re.S):
            cells = {}
            for column, attrs, body in re.findall(r'<c r="([A-Z]+)\d+"([^>]*?)(?:/>|>(.*?)</c>)', row, flags=re.S):
                value = re.search(r"<v>(.*?)</v>", body or "", flags=re.S)
                if value:
                    cells[column] = strings[int(value.group(1))] if 't="s"' in attrs else value.group(1)
            focal = re.fullmatch(r"([A-Z]{2})-(\d+)(?:\((\d+)\))?", cells.get("A", "").strip())
            if not focal:
                continue
            control = f"{focal.group(1).lower()}-{int(focal.group(2))}" + (f".{int(focal.group(3))}" if focal.group(3) else "")
            element = cells.get("D", "").strip()
            if re.fullmatch(r"\d+\.\d{5,}", element):  # a clause number the spreadsheet kept as a float: 4.0999999999999996
                element = repr(round(float(element), 2))
            out.setdefault(control, [])
            if element and element not in out[control]:
                out[control].append(element)
    _CROSSWALKS[name] = out
    return out


def catalog_facts(mapping):
    """({control id: statement id}, {control id: title}, the catalog's pinned address) from NIST's catalog."""
    name = mapping["framework"]["catalog"]
    if name in _CATALOGS:
        return _CATALOGS[name]
    href = next((l.split()[1] for l in read_text(os.path.join(ROOT, "catalogs.lock")).splitlines()
                 if l.strip() and not l.startswith("#") and l.split()[0] == name), None)
    cat = json.loads(read_text(os.path.join(ROOT, ".cache", "catalogs", name)))["catalog"]
    smt, titles = {}, {}

    def walk(controls):
        for c in controls or []:
            smt[c["id"]] = next((p["id"] for p in c.get("parts", []) if p.get("name") == "statement"), None)
            titles[c["id"]] = c["title"]
            walk(c.get("controls"))

    for g in cat.get("groups") or []:
        walk(g.get("controls"))
    _CATALOGS[name] = (smt, titles, href)
    return _CATALOGS[name]


def prop(name, value):
    return {"name": name, "ns": OUR_NS, "value": " ".join(str(value).split())}


def stamp(when):
    return when.replace("Z", "+00:00")


def documents(mapping, cloud, r, verdict, facts):
    """(assessment plan, assessment results) as plain dicts, from the run and the mapping alone."""
    smt, titles, catalog_href = facts
    run, artifact, flagship, spec = r["run"], r["artifact"], mapping["flagship"], mapping["clouds"][cloud]
    base = f"{cloud}/{run['id']}/{run.get('run_attempt')}"

    def u(what):
        return str(uuid.uuid5(SEED, f"{base}/{what}"))

    when = stamp(run["updated_at"])
    controls = [c for c in mapping["controls"] if cloud in c["clouds"]]
    digest = artifact["digest"].split(":", 1)[1]
    blob = f"https://github.com/{flagship['repository']}/blob/{run['head_sha']}"
    selection = {"control-selections": [{"include-controls": [{"control-id": c["control"]} for c in controls]}]}
    title = f"{flagship['repository'].split('/')[1]} on {spec['title']}, scheduled run {run['id']}"
    signed_as = f"https://github.com/{flagship['repository']}/{flagship['signer']}@refs/heads/{flagship['branch']}"
    kept_at = artifact.get("kept", "").rsplit("/", 1)[0]
    props = [prop("run", run["html_url"]), prop("cloud", cloud), prop("commit", run["head_sha"]),
             prop("event", run["event"]), prop("workflow", run["path"]), prop("artifact-id", artifact["id"]),
             prop("artifact-sha256", digest), prop("record-sha256", r["record_sha256"]),
             prop("record-signed-as", signed_as), prop("mapping-version", mapping["version"])]
    resources = {
        "run": {"uuid": u("resource/run"), "title": f"Run {run['id']} of {run['path']}",
                "description": f"The scheduled run this pack was built from: {spec['where']}.",
                "rlinks": [{"href": run["html_url"]}]},
        "artifact": {"uuid": u("resource/artifact"), "title": f"{artifact['name']}, artifact {artifact['id']}",
                     "description": ("The run's own results, as the flagship kept them on its branch "
                                     f"{flagship['results']}. The same bytes are in this pack as "
                                     f"run/{artifact['name']}.zip, and their sha256 is the one the signed record "
                                     "names. GitHub reports the same sha256 for the artifact until it expires on "
                                     f"{artifact['expires_at'][:10]}."),
                     "rlinks": [{"href": artifact.get("kept") or artifact["url"], "media-type": "application/zip",
                                 "hashes": [{"algorithm": "SHA-256", "value": digest}]},
                                {"href": artifact["url"], "media-type": "application/zip",
                                 "hashes": [{"algorithm": "SHA-256", "value": digest}]},
                                {"href": f"run/{artifact['name']}.zip", "media-type": "application/zip",
                                 "hashes": [{"algorithm": "SHA-256", "value": digest}]}]},
        "record": {"uuid": u("resource/record"), "title": f"The flagship's signed record of run {run['id']}",
                   "description": (f"What the flagship's workflow {flagship['signer']} wrote down about the run and "
                                   "signed keyless on its main: the run's facts and the sha256 of its results. It is "
                                   "in this pack as run/record.json with its Sigstore bundle, and cosign verifies "
                                   f"it for the identity {signed_as}."),
                   "rlinks": [{"href": f"{kept_at}/record.json" if kept_at else "run/record.json",
                               "media-type": "application/json",
                               "hashes": [{"algorithm": "SHA-256", "value": r["record_sha256"]}]},
                              {"href": "run/record.json", "media-type": "application/json",
                               "hashes": [{"algorithm": "SHA-256", "value": r["record_sha256"]}]},
                              {"href": "run/record.json.sigstore.json", "media-type": "application/json"}]},
        "page": {"uuid": u("resource/page"), "title": f"{flagship['page']} at the run's commit",
                 "description": ("The flagship is a reference architecture and has no system security plan. Its own "
                                 "page of controls, at the commit the run was made from, stands where a plan would: "
                                 "every control in this pack is a row of it."),
                 "rlinks": [{"href": f"{blob}/{flagship['page']}"}, {"href": f"{blob}/{spec['decision']}"}]},
        "catalog": {"uuid": u("resource/catalog"), "title": mapping["framework"]["title"],
                    "description": "NIST's own OSCAL catalog, pinned by commit and sha256 in catalogs.lock.",
                    "rlinks": [{"href": catalog_href, "media-type": "application/oscal+json"}]},
    }
    related = []
    for name, cw in mapping.get("crosswalks", {}).items():
        href, digest_of = pinned(cw["file"])
        related.append({"uuid": u(f"resource/crosswalk/{name}"), "title": f"Crosswalk to {cw['title']}",
                        "description": (f"{cw['by']}. The findings name what it relates to each control, as props "
                                        f"\"related-{name}\". It relates two documents: it is not a finding, and it "
                                        "says nothing about a system."),
                        "rlinks": [{"href": href, "hashes": [{"algorithm": "SHA-256", "value": digest_of}]},
                                   {"href": cw["page"]}]})
    used = [g for g in verdict["checks"] if any(g in c["checks"] for c in controls)]
    plan = {"assessment-plan": {
        "uuid": u("plan"),
        "metadata": {"title": f"What a scheduled run is read for: {title}", "last-modified": when,
                     "version": mapping["version"], "oscal-version": OSCAL_VERSION, "props": props},
        "import-ssp": {"href": f"#{resources['page']['uuid']}",
                       "remarks": resources["page"]["description"]},
        "local-definitions": {"activities": [{
            "uuid": u(f"activity/{g}"), "title": g, "description": mapping["checks"][g]["says"],
            "props": [{"name": "method", "value": "TEST"}, prop("kind", mapping["checks"][g]["kind"])]
                     + ([prop("plant", mapping["checks"][g]["plant"])] if "plant" in mapping["checks"][g]
                        else [prop("line", mapping["checks"][g]["line"])]),
            "related-controls": {"control-selections": [{"include-controls": [
                {"control-id": c["control"]} for c in controls if g in c["checks"]]}]},
        } for g in used]},
        "reviewed-controls": selection,
        "back-matter": {"resources": [resources["page"], resources["catalog"]]},
    }}

    observations, by_line = [], {}
    for g in used:
        gspec = mapping["checks"][g]
        for line, again in turns(verdict["checks"][g]["lines"]):
            key = (line, again)
            if key in by_line:
                by_line[key]["props"].append(prop("check", g))
                continue
            passed = line not in verdict["failed_lines"]
            evidence = [{"href": f"#{resources['artifact']['uuid']}",
                         "description": "The line is in the run's e2e-results.json, inside this artifact."}]
            if "plant" in gspec:
                evidence.append({"href": f"{blob}/{flagship['plants']}/{gspec['plant']}.yaml",
                                 "description": "The planted pod, as the flagship had it at the run's commit."})
            # The second time a run wrote the same words is an observation of its own, and says which it is.
            by_line[key] = {"uuid": u(f"line/{line}" if not again else f"line/{line}/{again + 1}"),
                            "title": f"{gspec['kind']}: {g}", "description": line, "methods": ["TEST"],
                            "props": [prop("passed", "true" if passed else "false"), prop("kind", gspec["kind"]),
                                      prop("check", g)] + ([prop("occurrence", again + 1)] if again else []),
                            "relevant-evidence": evidence, "collected": stamp(artifact["created_at"]),
                            "remarks": gspec["says"]}
            observations.append(by_line[key])

    findings = []
    for c in controls:
        v = verdict["controls"][c["control"]]
        lines = list(dict.fromkeys(o for g in c["checks"] if g in verdict["checks"]
                                   for o in turns(verdict["checks"][g]["lines"])))
        refused = list(dict.fromkeys(o for g in v["checks"]["refusal"] for o in turns(verdict["checks"][g]["lines"])))
        findings.append({
            "uuid": u(f"finding/{c['control']}"), "title": f"{c['name']}: {v['state']}",
            "description": ("; ".join(v["why"]) if v["why"] else
                            f"Every line the mapping names for it is in the run and passed: {len(refused)} "
                            f"refusal(s) of a violation tried in this run, beside "
                            f"{len(lines) - len(refused)} line(s) that had to hold."),
            "props": [prop("control", c["control"]), prop("cloud", cloud), prop("page-row", c["page_row"]),
                      prop("catalog-title", titles[c["control"]]), prop("judged-by", "scripts/pack.py")]
                     + [prop(f"related-{name}", element) for name, elements in v.get("related", {}).items()
                        for element in (elements or ["none"])],
            "target": {"type": "statement-id", "target-id": smt[c["control"]],
                       "status": {"state": v["state"], "reason": "pass" if v["state"] == "satisfied" else "fail"}},
            "related-observations": [{"observation-uuid": by_line[o]["uuid"]} for o in lines],
            "remarks": "What this leaves out: " + " ".join(c["not_covered"].split()),
        })

    results = {"assessment-results": {
        "uuid": u("results"),
        "metadata": {"title": f"Evidence from one scheduled cloud run: {title}", "last-modified": when,
                     "version": mapping["version"], "oscal-version": OSCAL_VERSION, "props": props,
                     "remarks": ("Every observation is a line of the run's own e2e-results.json, verbatim, and "
                                 "every finding is derived from those lines by scripts/pack.py. It shows what one "
                                 "scheduled run did. It does not say that any system meets a framework.")},
        "import-ap": {"href": "assessment-plan.json"},
        "results": [{
            "uuid": u("result"), "title": title,
            "description": (f"{spec['where'].capitalize()}, made, tried from inside and destroyed by run "
                            f"{run['id']} of {run['path']} at {run['head_sha'][:7]}. {verdict['lines']} lines in "
                            f"its results, {len(observations)} of them named by the mapping."),
            "start": stamp(run["run_started_at"]), "end": when,
            "reviewed-controls": selection, "observations": observations, "findings": findings,
        }],
        "back-matter": {"resources": [resources["run"], resources["record"], resources["artifact"],
                                      resources["page"], resources["catalog"]] + related},
    }}
    return plan, results


def summary(mapping, cloud, r, verdict):
    run, artifact, spec = r["run"], r["artifact"], mapping["clouds"][cloud]
    controls = [c for c in mapping["controls"] if cloud in c["clouds"]]
    ok = sum(verdict["controls"][c["control"]]["state"] == "satisfied" for c in controls)
    digest = artifact["digest"].split(":", 1)[1]

    def lines_of(c, kinds):
        out = [o for k in kinds for g in verdict["controls"][c["control"]]["checks"][k]
               for o in turns(verdict["checks"][g]["lines"])]
        return [line for line, _ in dict.fromkeys(out)]

    text = [
        f"# Evidence pack: {spec['title']}, scheduled run {run['id']}", "",
        f"[Run {run['id']}]({run['html_url']}) of `{run['path']}`, started by the schedule on "
        f"{run['run_started_at'][:10]}, on `{run['head_branch']}` at `{run['head_sha'][:7]}`: {spec['where']}.", "",
        f"{ok} of {len(controls)} mapped controls satisfied in this run. Its results hold {verdict['lines']} lines, "
        f"{len(verdict['failed_lines'])} of them failed.", "",
        "This shows what one scheduled run did. It does not say that any system meets a framework, and each "
        "control below says what it leaves out.", "",
        "| Control | In this run | Violations tried and refused | Lines beside them that had to hold |",
        "|---|---|---|---|",
    ]
    for c in controls:
        v = verdict["controls"][c["control"]]
        text.append(f"| {c['name']} | {v['state']} | {len(lines_of(c, ['refusal']))} | "
                    f"{len(lines_of(c, ['control', 'gate']))} |")
    for c in controls:
        v = verdict["controls"][c["control"]]
        text += ["", f"## {c['name']}: {v['state']}", ""]
        if v["why"]:
            text += ["Not satisfied, because:", ""] + [f"- {w}" for w in v["why"]] + [""]
        text += ["The violation tried in this run, and refused. Each line is the run's own, word for word:", ""]
        text += [f"- {l}" for l in lines_of(c, ["refusal"])] or ["- none"]
        text += ["", "Beside it, what had to hold, so a refusal is not the environment refusing everything:", ""]
        text += [f"- {l}" for l in lines_of(c, ["control", "gate"])] or ["- none"]
        text += ["", f"What this leaves out: {' '.join(c['not_covered'].split())}"]
        for name, elements in v.get("related", {}).items():
            cw = mapping["crosswalks"][name]
            text += ["", (f"Related in {cw['title']}: {', '.join(elements)}." if elements else
                          f"Related in {cw['title']}: nothing.")
                     + f" This is {cw['by']}, a relation between two documents and not a finding."]
    away = [c["name"] for c in mapping["controls"] if cloud not in c["clouds"]]
    if away:
        text += ["", "## Not in this pack", "",
                 f"Mapped on other clouds and not here, because this cloud's run does not write their lines: "
                 f"{', '.join(away)}."]
    shown = [(g, s["shown_failing"][cloud]) for g, s in mapping["checks"].items()
             if cloud in s.get("shown_failing", {}) and g in verdict["checks"]]
    if shown:
        repo = mapping["flagship"]["repository"]
        text += ["", "## The day a check failed", "",
                 "A check that has never failed proves little. On this cloud, by hand, with the resolver's policy "
                 "left off, these failed:", ""]
        text += [f"- `{g}`: [run {s['run']}](https://github.com/{repo}/actions/runs/{s['run']})" for g, s in shown]
    flagship = mapping["flagship"]
    text += ["", "## Is the file inside the run's?", "",
             "The repository that ran the cloud says so, and signed it. Its workflow wrote down the run's facts and "
             "the sha256 of the results the run uploaded, and signed that record on its main. Both are in this pack, "
             "and cosign checks the signature for one exact identity:", "",
             "```sh",
             "cosign verify-blob evidence/run/record.json --bundle evidence/run/record.json.sigstore.json \\",
             f"  --certificate-identity https://github.com/{flagship['repository']}/{flagship['signer']}"
             f"@refs/heads/{flagship['branch']} \\",
             "  --certificate-oidc-issuer https://token.actions.githubusercontent.com",
             f"sha256sum evidence/run/{artifact['name']}.zip", "```", "",
             f"The second answer is `{digest}`, the value `record.json` gives as `artifact.sha256`. The record also "
             f"says who started the run: `{run['event']}`, on `{run['head_branch']}`, by `{run['path']}`, "
             f"`{run['conclusion']}`.", "",
             f"Until GitHub drops the artifact on {artifact['expires_at'][:10]}, GitHub gives the same digest, to "
             "anyone:", "",
             "```sh",
             f"curl -s https://api.github.com/repos/{flagship['repository']}/actions/artifacts/{artifact['id']} "
             "| grep '\"digest\"'", "```", ""]
    return "\n".join(text)


def dump(doc):
    return json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def render(mapping, run_dir):
    """{file name: text} for one run: the documents a pack holds beside run/. Raises Refused."""
    r = read_run(run_dir)
    cloud, reasons = provenance(mapping, r)
    if reasons:
        raise Refused("; ".join(reasons))
    member, member_sha, checks, measured = results_of(r["archive"])
    verdict = judge(mapping, cloud, checks, r["plants"])
    for control, v in verdict["controls"].items():
        v["related"] = {name: crosswalk(mapping, name).get(control, []) for name in mapping.get("crosswalks", {})}
    verdict = {"cloud": cloud, "run": r["run"], "artifact": r["artifact"],
               "results_file": {"member": member, "sha256": member_sha},
               "mapping_version": mapping["version"], **verdict, "measured": measured}
    plan, results = documents(mapping, cloud, r, verdict, catalog_facts(mapping))
    return {"assessment-plan.json": dump(plan), "assessment-results.json": dump(results),
            "verdict.json": dump(verdict), "summary.md": summary(mapping, cloud, r, verdict)}


def main(argv):
    if len(argv) != 2:
        sys.stderr.write(__doc__)
        return 2
    run_dir, out = os.path.abspath(argv[0]), os.path.join(os.path.abspath(argv[1]), "evidence")
    mapping_path = os.environ.get("MAPPING") or os.path.join(ROOT, "mapping", "controls.yaml")
    mapping = load_mapping(mapping_path)
    try:
        files = render(mapping, run_dir)
    except Refused as e:
        print(f"pack: refused: {e}", file=sys.stderr)
        return 2
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    for name, text in files.items():
        with open(os.path.join(out, name), "w", encoding="utf-8") as f:
            f.write(text)
    shutil.copyfile(mapping_path, os.path.join(out, "mapping.yaml"))
    shutil.copytree(run_dir, os.path.join(out, "run"))
    try:
        read = (AssessmentPlan.oscal_read(pathlib.Path(out) / "assessment-plan.json"),
                AssessmentResults.oscal_read(pathlib.Path(out) / "assessment-results.json"))
    except Exception as e:  # a document trestle cannot read is no evidence
        read = (None, e)
    if None in read:
        print(f"pack: the documents do not parse as OSCAL: {read[1]}", file=sys.stderr)
        shutil.rmtree(out, ignore_errors=True)
        return 2
    verdict = json.loads(files["verdict.json"])
    ok = sum(v["state"] == "satisfied" for v in verdict["controls"].values())
    print(f"== pack written for {verdict['cloud']} run {verdict['run']['id']}: {ok} of {len(verdict['controls'])} "
          f"controls satisfied, {verdict['lines']} lines, {len(verdict['failed_lines'])} failed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
