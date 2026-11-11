#!/usr/bin/env python3
"""component.py [--check] - the mapping, held to what exists, and as an OSCAL component definition.

mapping/controls.yaml is refused when it names anything that is not there:

  - a control NIST's pinned catalog does not have, or one with no statement;
  - a control with no row in the flagship's docs/compliance.md, read from the
    release flagship.lock pins, or one resting on a planted pod its row there
    does not name;
  - a check no control names, or a control naming a check that is not defined;
  - a check with no kind, no cloud, a pattern that does not compile, or both
    a line and a plant, or neither;
  - a planted pod the flagship's release does not have, or one whose own
    "# expect:" line disagrees with the kind the mapping gives it;
  - a control on a cloud with no refusal among its checks there, or with
    nothing that had to succeed: such a control could never be satisfied,
    and one that could be satisfied by refusals alone proves nothing.

Then it writes oscal/component-definition.json with compliance-trestle's
models: the flagship as one component, one implemented requirement per
control, with what it leaves out. The file is never edited by hand; with
--check nothing is written, and a file that differs from what the mapping
gives is an error.
"""
import json
import os
import pathlib
import re
import sys
import tempfile
import uuid

from trestle.oscal import OSCAL_VERSION
from trestle.oscal.component import ComponentDefinition

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pack  # noqa: E402

ROOT = pack.ROOT
OUT = os.path.join(ROOT, "oscal", "component-definition.json")
FLAGSHIP = os.path.join(ROOT, ".cache", "flagship", "src")


def problems(mapping, smt, flagship=FLAGSHIP):
    bad = []
    clouds, checks = mapping["clouds"], mapping["checks"]
    page = pack.read_text(os.path.join(flagship, mapping["flagship"]["page"]))
    used = set()
    for name, spec in checks.items():
        if spec.get("kind") not in pack.KINDS:
            bad.append(f"check {name}: kind {spec.get('kind')!r} is not one of {', '.join(pack.KINDS)}")
        if not spec.get("clouds") or set(spec["clouds"]) - set(clouds):
            bad.append(f"check {name}: clouds {spec.get('clouds')} are not all clouds of the mapping")
        if ("line" in spec) == ("plant" in spec):
            bad.append(f"check {name}: it must name a line or a plant, and not both")
        need = spec.get("at_least", 1)
        for n in (need.values() if isinstance(need, dict) else [need]):
            if not isinstance(n, int) or n < 1:
                bad.append(f"check {name}: at_least {n!r} is not a count of lines")
        if isinstance(need, dict) and set(need) != set(spec.get("clouds", [])):
            bad.append(f"check {name}: at_least names {sorted(need)}, and the check is written on {spec.get('clouds')}")
        if not spec.get("says"):
            bad.append(f"check {name}: it does not say what it shows")
        if "line" in spec:
            try:
                re.compile(spec["line"])
            except re.error as e:
                bad.append(f"check {name}: its line is not a regular expression: {e}")
        if "plant" in spec:
            path = os.path.join(flagship, mapping["flagship"]["plants"], spec["plant"] + ".yaml")
            if not os.path.exists(path):
                bad.append(f"check {name}: the flagship's release has no planted pod {spec['plant']}")
            else:
                _, kind = pack.plant_line(spec["plant"], pack.read_text(path))
                if kind != spec.get("kind"):
                    bad.append(f"check {name}: the planted pod {spec['plant']} expects a {kind}, "
                               f"and the mapping calls it a {spec.get('kind')}")
        for cloud in spec.get("shown_failing", {}):
            if cloud not in spec.get("clouds", []):
                bad.append(f"check {name}: shown failing on {cloud}, where it is not written")
    seen = set()
    for c in mapping["controls"]:
        cid = c["control"]
        if cid in seen:
            bad.append(f"control {cid}: mapped twice")
        seen.add(cid)
        if not smt.get(cid):
            bad.append(f"control {cid}: NIST's catalog has no such control, or it has no statement")
        row = re.search(r"^\| " + re.escape(c["page_row"]) + r".*$", page, re.M)
        if not row:
            bad.append(f"control {cid}: {mapping['flagship']['page']} has no row \"{c['page_row']}\"")
        for g in c["checks"]:
            plant = checks.get(g, {}).get("plant")
            if row and plant and checks[g].get("kind") == "refusal" and f"`{plant}`" not in row.group(0):
                bad.append(f"control {cid}: its row in {mapping['flagship']['page']} does not name the planted pod "
                           f"{plant}, so the page does not rest this control on it")
        for field in ("name", "implementation", "not_covered"):
            if not str(c.get(field) or "").strip():
                bad.append(f"control {cid}: it has no {field}")
        missing = [g for g in c["checks"] if g not in checks]
        if missing:
            bad.append(f"control {cid}: names checks that are not defined: {', '.join(missing)}")
            continue
        used |= set(c["checks"])
        if not c.get("clouds") or set(c["clouds"]) - set(clouds):
            bad.append(f"control {cid}: clouds {c.get('clouds')} are not all clouds of the mapping")
            continue
        for cloud in c["clouds"]:
            kinds = {checks[g]["kind"] for g in c["checks"] if cloud in checks[g].get("clouds", [])}
            if "refusal" not in kinds:
                bad.append(f"control {cid} on {cloud}: no check there is a refusal, so no violation is ever shown it")
            if "control" not in kinds:
                bad.append(f"control {cid} on {cloud}: nothing there had to succeed beside the refusals")
    for name in sorted(set(checks) - used):
        bad.append(f"check {name}: no control names it")
    for name, cw in mapping.get("crosswalks", {}).items():
        if pack.pinned(cw.get("file"))[0] is None:
            bad.append(f"crosswalk {name}: catalogs.lock does not pin {cw.get('file')}")
            continue
        try:
            listed = pack.crosswalk(mapping, name)
        except (OSError, KeyError, ValueError) as e:
            bad.append(f"crosswalk {name}: {cw['file']} cannot be read: {e}")
            continue
        for c in mapping["controls"]:
            if c["control"] not in listed:
                bad.append(f"crosswalk {name}: it has no row for {c['control']}, so nothing can be said of what it relates")
    return bad


def definition(mapping, catalog_href):
    seed = pack.SEED

    def u(what):
        return str(uuid.uuid5(seed, f"component/{what}"))

    flagship = mapping["flagship"]
    requirements = []
    for c in mapping["controls"]:
        props = [pack.prop("page-row", c["page_row"])] + [pack.prop("cloud", cloud) for cloud in c["clouds"]]
        props += [pack.prop(f"related-{name}", element) for name in mapping.get("crosswalks", {})
                  for element in (pack.crosswalk(mapping, name).get(c["control"]) or ["none"])]
        props += [pack.prop(mapping["checks"][g]["kind"], g) for g in c["checks"]]
        requirements.append({"uuid": u(f"requirement/{c['control']}"), "control-id": c["control"],
                             "description": " ".join(c["implementation"].split()), "props": props,
                             "remarks": "What this leaves out: " + " ".join(c["not_covered"].split())})
    name = flagship["repository"].split("/")[1]
    return {"component-definition": {
        "uuid": u("definition"),
        "metadata": {"title": f"{name} on its scheduled cloud runs, mapped to {mapping['framework']['title']}",
                     "last-modified": mapping["last_modified"], "version": mapping["version"],
                     "oscal-version": OSCAL_VERSION,
                     "remarks": ("Made from mapping/controls.yaml by scripts/component.py. A control is here only "
                                 "where the flagship's own page has the row and a scheduled cloud run shows a "
                                 "violation its check refused. It is not a statement that a system meets a "
                                 "framework.")},
        "components": [{
            "uuid": u("component"), "type": "software", "title": name,
            "description": (f"{flagship['repository']}, as its scheduled runs make it on "
                            + ", ".join(spec["title"] for spec in mapping["clouds"].values())
                            + ": the cluster, the boundary around it, and what is inside."),
            "props": [pack.prop("repository", f"https://github.com/{flagship['repository']}"),
                      pack.prop("page", flagship["page"])]
                     + [pack.prop("workflow", spec["workflow"]) for spec in mapping["clouds"].values()],
            "control-implementations": [{
                "uuid": u("implementation"), "source": catalog_href,
                "description": (f"The rows of {flagship['page']} that a scheduled cloud run gives evidence for, "
                                "each with the lines of the run that carry it."),
                "implemented-requirements": requirements,
            }],
        }],
    }}


def main(argv):
    mapping = pack.load_mapping()
    smt, _, catalog_href = pack.catalog_facts(mapping)
    bad = problems(mapping, smt)
    if bad:
        print("the mapping names what is not there:\n" + "\n".join(f"  {b}" for b in bad), file=sys.stderr)
        return 1
    text = pack.dump(definition(mapping, catalog_href))
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(text)
    try:
        if ComponentDefinition.oscal_read(pathlib.Path(f.name)) is None:
            raise ValueError("trestle read nothing")
    except Exception as e:
        print(f"the component definition does not parse as OSCAL: {e}", file=sys.stderr)
        return 1
    finally:
        os.unlink(f.name)
    if "--check" in argv:
        held = pack.read_text(OUT) if os.path.exists(OUT) else None
        if held != text:
            print("oscal/component-definition.json is not what mapping/controls.yaml gives: run scripts/component.py",
                  file=sys.stderr)
            return 1
        print(f"the mapping names nothing that is not there, and oscal/component-definition.json is what it gives "
              f"({len(mapping['controls'])} controls, {len(mapping['checks'])} checks)")
        return 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"wrote oscal/component-definition.json: {len(mapping['controls'])} controls")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
