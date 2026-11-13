#!/usr/bin/env python3
"""index.py RUNS_DIR PACKS_DIR OUT_DIR - every scheduled cloud run, and what became of it.

  RUNS_DIR/<cloud>.json    the scheduled runs of that cloud's workflow, as
                           `scripts/fetch.py list <cloud>` prints them
  PACKS_DIR/<cloud>/<run id>/verdict.json    a pack that passed the gate
  PACKS_DIR/<cloud>/<run id>/refused.txt     why a passed run gave no pack

Writes OUT_DIR/index.json and OUT_DIR/index.md. Three outcomes are kept
apart, because they are three different things to tell a reader:

  pack                the run passed, and its pack passed the gate
  run with no pack    the run failed, or it passed and its evidence was
                      refused: a failure of that week, listed with the run
  not built yet       the run passed and nothing has read it yet

and, for a cloud as a whole:

  missing             the cloud's workflow has no scheduled run in the last
                      STALE_DAYS days (10: a week and room for a late start),
                      or none at all. The leg is reported as missing since
                      the last run there was. It is not a failure, and the
                      other clouds' packs do not wait for it.

A run that exists and has no pack is never "missing": a leg that stopped
running and a leg whose evidence was refused must not look alike.

Exits 0 whatever the runs say, 2 when a list of runs cannot be read. Whether
a week failed is decided where packs are built, not here.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pack  # noqa: E402

STALE_DAYS = 10


def when(text):
    return datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))


def outcome(run, packs, cloud):
    """(what became of one scheduled run, the detail to print beside it)."""
    here = os.path.join(packs, cloud, str(run["id"]))
    if run.get("status") != "completed":
        return "still running", ""
    if run.get("conclusion") != "success":
        return "run with no pack", f"the run ended {run.get('conclusion')}"
    if os.path.exists(os.path.join(here, "verdict.json")):
        verdict = json.loads(pack.read_text(os.path.join(here, "verdict.json")))
        controls = verdict["controls"]
        ok = sum(c["state"] == "satisfied" for c in controls.values())
        # A pack is judged by the mapping of the day it was built, and a later mapping may ask more of the same run.
        return "pack", f"{ok} of {len(controls)} controls satisfied, by mapping {verdict['mapping_version']}"
    if os.path.exists(os.path.join(here, "refused.txt")):
        return "run with no pack", pack.read_text(os.path.join(here, "refused.txt")).strip()
    return "not built yet", ""


def leg(mapping, cloud, runs, packs, now):
    rows = []
    for run in sorted(runs, key=lambda r: r["created_at"], reverse=True):
        what, detail = outcome(run, packs, cloud)
        rows.append({"run": run["id"], "url": run["html_url"], "date": run["created_at"][:10],
                     "commit": run["head_sha"][:7], "outcome": what, "detail": detail})
    newest = rows[0]["date"] if rows else None
    age = (now - when(max(r["created_at"] for r in runs))).days if runs else None
    missing = age is None or age > STALE_DAYS
    in_a_row = 0
    for row in rows:
        if row["outcome"] in ("still running", "not built yet") and in_a_row == 0:
            continue  # a run nobody has judged yet neither adds to the streak nor ends it
        if row["outcome"] != "pack":
            break
        in_a_row += 1
    state = ("missing: no scheduled run of this workflow is on record" if newest is None else
             f"missing: no scheduled run since {newest}" if missing else f"running: last scheduled run {newest}")
    return {"title": mapping["clouds"][cloud]["title"], "workflow": mapping["clouds"][cloud]["workflow"],
            "state": state, "missing": missing, "packs_in_a_row": in_a_row, "runs": rows}


def main(argv):
    if len(argv) != 3:
        sys.stderr.write(__doc__)
        return 2
    runs_dir, packs, out = argv
    mapping = pack.load_mapping()
    now = when(os.environ["NOW"]) if os.environ.get("NOW") else datetime.datetime.now(datetime.timezone.utc)
    legs = {}
    for cloud in mapping["clouds"]:
        try:
            runs = json.loads(pack.read_text(os.path.join(runs_dir, cloud + ".json")))
            if not isinstance(runs, list):
                raise ValueError("not a list of runs")
        except (OSError, ValueError) as e:
            print(f"index: the scheduled runs of {cloud} cannot be read: {e}", file=sys.stderr)
            return 2
        legs[cloud] = leg(mapping, cloud, runs, packs, now)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"written_at": now.isoformat(timespec="seconds"), "stale_days": STALE_DAYS, "clouds": legs},
                  f, indent=1)
        f.write("\n")
    text = ["# Every scheduled cloud run, and what became of it", "",
            f"Written {now.strftime('%Y-%m-%d %H:%M')} UTC from the flagship's own run history. A cloud with no "
            f"scheduled run in the last {STALE_DAYS} days is reported as missing, not as a failure.", ""]
    for cloud, l in legs.items():
        text += [f"## {l['title']}: {l['state']}", "",
                 f"`{l['workflow']}`. Packs in a row, newest first: {l['packs_in_a_row']}.", ""]
        if l["runs"]:
            text += ["| Scheduled run | Date | Commit | What became of it | |", "|---|---|---|---|---|"]
            text += [f"| [{r['run']}]({r['url']}) | {r['date']} | `{r['commit']}` | {r['outcome']} | "
                     f"{r['detail'].replace('|', '/')} |" for r in l["runs"]]
            text.append("")
    with open(os.path.join(out, "index.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(text))
    for cloud, l in legs.items():
        print(f"== {cloud}: {l['state']}; {sum(r['outcome'] == 'pack' for r in l['runs'])} pack(s), "
              f"{sum(r['outcome'] == 'run with no pack' for r in l['runs'])} run(s) with no pack")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
