#!/usr/bin/env python3
"""fetch.py - what GitHub holds about the flagship's cloud runs, read and kept as it is.

  fetch.py run RUN_ID OUT_DIR    one run: its record, its jobs, the artifact
                                 the mapping names for its workflow, and the
                                 planted pods at the run's commit
  fetch.py list CLOUD            the scheduled runs of that cloud's workflow
                                 on the flagship's branch, newest first, as
                                 JSON on stdout

Nothing is judged here. `run` writes what it was given, whatever it says:

  OUT_DIR/run.json        the run's record, the fields the pack reads
  OUT_DIR/jobs.json       its jobs, with their conclusions
  OUT_DIR/artifact.json   the artifact's record, with the sha256 GitHub reports
  OUT_DIR/<artifact>.zip  the artifact, byte for byte as the API gave it
  OUT_DIR/plants/*.yaml   the planted pods the mapping names, at the run's commit

scripts/pack.py decides whether that is a scheduled run on main and whether
the file is the run's. A run that kept no artifact, or whose artifact has
expired, leaves no artifact.json and no zip, and pack.py refuses it.

The token is read from GITHUB_TOKEN or GH_TOKEN and sent only to
api.github.com. An artifact's download is a redirect to a signed address: it
is followed without the token, and the address is never printed.
"""
import json
import os
import sys
import urllib.error
import urllib.request

from ruamel.yaml import YAML

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.github.com"
MAX_ARTIFACT = 50 * 1024 * 1024  # the largest so far is 13 KB

RUN_FIELDS = ("id", "name", "path", "event", "status", "conclusion", "head_branch", "head_sha",
              "run_attempt", "run_number", "created_at", "run_started_at", "updated_at", "html_url")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def token():
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""


def request(path, accept="application/vnd.github+json"):
    req = urllib.request.Request(API + path, headers={"Accept": accept, "X-GitHub-Api-Version": "2022-11-28",
                                                      "User-Agent": "cloud-evidence-pack"})
    if token():
        req.add_header("Authorization", "Bearer " + token())
    return req


def get(path, accept="application/vnd.github+json"):
    try:
        with urllib.request.urlopen(request(path, accept), timeout=60) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        # The status and the path, never the body: an auth error can echo a token.
        raise SystemExit(f"fetch: GitHub answered {e.code} for {path}")
    except urllib.error.URLError as e:
        raise SystemExit(f"fetch: {path}: {e.reason}")


def get_json(path):
    return json.loads(get(path))


def download(path):
    """An artifact's bytes: the API redirects to a signed address, read without the token."""
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(request(path), timeout=60) as r:
            return r.read(MAX_ARTIFACT + 1)
    except urllib.error.HTTPError as e:
        if e.code not in (301, 302, 303, 307, 308) or not e.headers.get("Location"):
            raise SystemExit(f"fetch: GitHub answered {e.code} for {path}")
        signed = e.headers["Location"]
    try:
        with urllib.request.urlopen(urllib.request.Request(signed, headers={"User-Agent": "cloud-evidence-pack"}),
                                    timeout=120) as r:
            return r.read(MAX_ARTIFACT + 1)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"fetch: the artifact's download answered {e.code}")
    except urllib.error.URLError as e:
        raise SystemExit(f"fetch: the artifact's download failed: {e.reason}")


def run_record(run):
    out = {k: run.get(k) for k in RUN_FIELDS}
    out["repository"] = (run.get("repository") or {}).get("full_name")
    out["head_repository"] = (run.get("head_repository") or {}).get("full_name")
    return out


def write(path, doc):
    with open(path, "w") as f:
        json.dump(doc, f, indent=1, sort_keys=True)
        f.write("\n")


def fetch_run(mapping, run_id, out):
    repo = mapping["flagship"]["repository"]
    os.makedirs(out, exist_ok=True)
    run = run_record(get_json(f"/repos/{repo}/actions/runs/{run_id}"))
    write(os.path.join(out, "run.json"), run)
    jobs = get_json(f"/repos/{repo}/actions/runs/{run_id}/jobs?per_page=100")["jobs"]
    write(os.path.join(out, "jobs.json"), [{k: j.get(k) for k in ("name", "conclusion", "started_at", "completed_at")}
                                           for j in jobs])
    cloud = next((c for c, spec in mapping["clouds"].items() if spec["workflow"] == run["path"]), None)
    if cloud is None:
        print(f"fetch: run {run_id} is a run of {run['path']}, which is no cloud's workflow: no artifact read")
        return
    name = mapping["clouds"][cloud]["artifact"]
    artifacts = get_json(f"/repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100")["artifacts"]
    kept = [a for a in artifacts if a["name"] == name and not a.get("expired")]
    if len(kept) != 1:
        print(f"fetch: run {run_id} holds {len(kept)} artifacts named {name} that have not expired: none read")
        return
    a = kept[0]
    if a["size_in_bytes"] > MAX_ARTIFACT:
        raise SystemExit(f"fetch: {name} of run {run_id} is {a['size_in_bytes']} bytes, more than this reads")
    archive = download(f"/repos/{repo}/actions/artifacts/{a['id']}/zip")
    if len(archive) > MAX_ARTIFACT:
        raise SystemExit(f"fetch: {name} of run {run_id} is larger than GitHub said")
    with open(os.path.join(out, name + ".zip"), "wb") as f:
        f.write(archive)
    write(os.path.join(out, "artifact.json"), {
        "id": a["id"], "name": a["name"], "size_in_bytes": a["size_in_bytes"], "digest": a.get("digest"),
        "created_at": a["created_at"], "expires_at": a["expires_at"],
        "run_id": (a.get("workflow_run") or {}).get("id"), "head_sha": (a.get("workflow_run") or {}).get("head_sha"),
        "url": f"{API}/repos/{repo}/actions/artifacts/{a['id']}"})
    plants = sorted({spec["plant"] for spec in mapping["checks"].values()
                     if "plant" in spec and cloud in spec["clouds"]})
    os.makedirs(os.path.join(out, "plants"), exist_ok=True)
    held = 0
    for plant in plants:
        path = f"/repos/{repo}/contents/{mapping['flagship']['plants']}/{plant}.yaml?ref={run['head_sha']}"
        try:
            with urllib.request.urlopen(request(path, "application/vnd.github.raw"), timeout=60) as r:
                body = r.read(1024 * 1024)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue  # the run's commit has no such plant: pack.py says so
            raise SystemExit(f"fetch: GitHub answered {e.code} for the plant {plant}")
        with open(os.path.join(out, "plants", plant + ".yaml"), "wb") as f:
            f.write(body)
        held += 1
    print(f"fetch: run {run_id} ({cloud}, {run['event']}, {run['conclusion']}), {name} of {len(archive)} bytes, "
          f"{held} of {len(plants)} plants at {run['head_sha'][:7]}")


def list_runs(mapping, cloud):
    repo, flagship = mapping["flagship"]["repository"], mapping["flagship"]
    workflow = os.path.basename(mapping["clouds"][cloud]["workflow"])
    runs = get_json(f"/repos/{repo}/actions/workflows/{workflow}/runs"
                    f"?event=schedule&branch={flagship['branch']}&per_page=50")["workflow_runs"]
    json.dump([run_record(r) for r in runs], sys.stdout, indent=1, sort_keys=True)
    sys.stdout.write("\n")


def main(argv):
    with open(os.environ.get("MAPPING", os.path.join(ROOT, "mapping", "controls.yaml")), encoding="utf-8") as f:
        mapping = YAML(typ="safe").load(f.read())
    if len(argv) == 3 and argv[0] == "run" and argv[1].isdigit():
        fetch_run(mapping, argv[1], argv[2])
    elif len(argv) == 2 and argv[0] == "list" and argv[1] in mapping["clouds"]:
        list_runs(mapping, argv[1])
    else:
        sys.stderr.write(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
