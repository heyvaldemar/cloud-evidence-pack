#!/usr/bin/env python3
"""fetch.py - one cloud run of the flagship, read from what the flagship itself signed and kept.

  fetch.py run RUN_ID OUT_DIR    one run, from the flagship's branch
                                 `cloud-results`: the record its workflow
                                 signed, the signature, the run's results
                                 artifact, and the planted pods at the run's
                                 commit
  fetch.py list CLOUD            the scheduled runs of that cloud's workflow
                                 on the flagship's branch, newest first, as
                                 JSON on stdout, from GitHub's API
  fetch.py kept                  the ids of the runs the flagship's branch
                                 holds a record of, one a line

Since its ADR 25 the flagship keeps every finished cloud run on a branch:
`<cloud>/<run id>-<attempt>/record.json`, the record's Sigstore bundle, and
the artifact the run uploaded, whose sha256 the record names. The record is
signed keyless by the flagship's workflow, on its main. `run` reads those
three files with no token, and before it writes anything it requires:

  - cosign to verify the record against its bundle for one exact identity,
    the flagship's `.github/workflows/cloud-results.yml` at `refs/heads/main`,
    issued by GitHub Actions. No pattern: one string;
  - the artifact's sha256 to be the one the signed record names.

Then it writes, for scripts/pack.py:

  OUT_DIR/record.json, record.json.sigstore.json   as the flagship kept them
  OUT_DIR/run.json        the run's record, exactly as in the signed record
  OUT_DIR/jobs.json       its jobs
  OUT_DIR/artifact.json   the artifact's record, its digest the signed one
  OUT_DIR/<artifact>.zip  the artifact, byte for byte
  OUT_DIR/plants/*.yaml   the planted pods the mapping names, at the run's commit

Whether that run may carry a pack (a scheduled run on main that passed) is
scripts/pack.py's to decide. A run the branch holds no record of, or one
that uploaded nothing, leaves nothing here, and pack.py refuses it.

Nothing here needs a token. `list` sends one to api.github.com when
GITHUB_TOKEN or GH_TOKEN is set, for the rate limit alone.
"""
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

from ruamel.yaml import YAML

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"
ISSUER = "https://token.actions.githubusercontent.com"
MAX_ARTIFACT = 5 * 1024 * 1024  # what the flagship keeps at most
RUN_FIELDS = ("id", "name", "path", "event", "status", "conclusion", "head_branch", "head_sha", "run_attempt",
              "run_number", "created_at", "run_started_at", "updated_at", "html_url")


def get(url, token=False, limit=MAX_ARTIFACT):
    req = urllib.request.Request(url, headers={"User-Agent": "cloud-evidence-pack"})
    secret = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token and secret:
        req.add_header("Authorization", "Bearer " + secret)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read(limit + 1)
    except urllib.error.HTTPError as e:
        # The status and the address, never the body: an auth error can echo a token.
        raise SystemExit(f"fetch: {url.split('?')[0]} answered {e.code}")
    except urllib.error.URLError as e:
        raise SystemExit(f"fetch: {url.split('?')[0]}: {e.reason}")


def signer(mapping):
    """The one identity a record must be signed as."""
    f = mapping["flagship"]
    return f"https://github.com/{f['repository']}/{f['signer']}@refs/heads/{f['branch']}"


def verify(record, bundle, identity):
    """Why cosign does not verify the record for that identity; None when it does."""
    out = ""
    for attempt in (1, 2, 3):
        try:
            p = subprocess.run(["cosign", "verify-blob", record, "--bundle", bundle, "--certificate-identity", identity,
                                "--certificate-oidc-issuer", ISSUER], capture_output=True, text=True)
        except OSError as e:
            return f"cosign cannot be run: {e}"
        if p.returncode == 0:
            return None
        out = (p.stderr.strip().splitlines() or ["cosign said nothing"])[-1]
        # Sigstore's trust root is fetched each time: that, and only that, is tried again.
        if not any(w in out for w in ("tuf refresh failed", "error getting live trusted root", "dial tcp", "i/o timeout")):
            break
        time.sleep(attempt * 5)
    return out


def write(path, doc):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, sort_keys=True)
        f.write("\n")


def fetch_run(mapping, run_id, out):
    flagship = mapping["flagship"]
    repo, base = flagship["repository"], f"{RAW}/{flagship['repository']}/{flagship['results']}"
    kept = [r for r in json.loads(get(f"{base}/index.json")) if str(r.get("run")) == str(run_id)]
    if not kept:
        print(f"fetch: the flagship's branch {flagship['results']} holds no record of run {run_id}: nothing read",
              file=sys.stderr)
        return 1
    entry = max(kept, key=lambda r: r.get("attempt") or 1)
    raw_record = get(f"{base}/{entry['path']}/record.json")
    raw_bundle = get(f"{base}/{entry['path']}/record.json.sigstore.json")
    os.makedirs(out, exist_ok=True)
    for name, body in (("record.json", raw_record), ("record.json.sigstore.json", raw_bundle)):
        with open(os.path.join(out, name), "wb") as f:
            f.write(body)
    why = verify(os.path.join(out, "record.json"), os.path.join(out, "record.json.sigstore.json"), signer(mapping))
    if why:
        for name in ("record.json", "record.json.sigstore.json"):
            os.remove(os.path.join(out, name))
        raise SystemExit(f"fetch: the record of run {run_id} is not signed as {signer(mapping)}: {why}")
    record = json.loads(raw_record)
    run, artifact = record["run"], record.get("artifact")
    write(os.path.join(out, "run.json"), run)
    write(os.path.join(out, "jobs.json"), record.get("jobs") or [])
    cloud = next((c for c, spec in mapping["clouds"].items() if spec["workflow"] == run.get("path")), None)
    if artifact is None or cloud is None:
        print(f"fetch: run {run_id} ({run.get('event')}, {run.get('conclusion')}), signed, kept with no results: "
              f"{record.get('no_artifact', 'not a cloud workflow of the mapping')}")
        return 0
    archive = get(f"{base}/{entry['path']}/{artifact['file']}")
    if len(archive) > MAX_ARTIFACT or hashlib.sha256(archive).hexdigest() != artifact["sha256"]:
        raise SystemExit(f"fetch: {artifact['file']} of run {run_id} is not the file the signed record names "
                         f"(sha256 {artifact['sha256']})")
    with open(os.path.join(out, artifact["name"] + ".zip"), "wb") as f:
        f.write(archive)
    write(os.path.join(out, "artifact.json"), {
        "id": artifact["id"], "name": artifact["name"], "size_in_bytes": artifact["size_in_bytes"],
        "digest": "sha256:" + artifact["sha256"], "created_at": artifact["created_at"],
        "expires_at": artifact["expires_at"], "run_id": run["id"], "head_sha": run["head_sha"],
        "url": f"{API}/repos/{repo}/actions/artifacts/{artifact['id']}",
        "kept": f"{base}/{entry['path']}/{artifact['file']}"})
    plants = sorted({spec["plant"] for spec in mapping["checks"].values()
                     if "plant" in spec and cloud in spec["clouds"]})
    os.makedirs(os.path.join(out, "plants"), exist_ok=True)
    held = 0
    for plant in plants:
        url = f"{RAW}/{repo}/{run['head_sha']}/{flagship['plants']}/{plant}.yaml"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "cloud-evidence-pack"}),
                                        timeout=60) as r:
                body = r.read(1024 * 1024)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue  # the run's commit has no such plant: pack.py says so
            raise SystemExit(f"fetch: the plant {plant} at {run['head_sha'][:7]} answered {e.code}")
        with open(os.path.join(out, "plants", plant + ".yaml"), "wb") as f:
            f.write(body)
        held += 1
    print(f"fetch: run {run_id} ({cloud}, {run['event']}, {run['conclusion']}), signed by the flagship's workflow; "
          f"{artifact['name']} of {len(archive)} bytes, the sha256 the record names; "
          f"{held} of {len(plants)} plants at {run['head_sha'][:7]}")
    return 0


def list_runs(mapping, cloud):
    flagship = mapping["flagship"]
    workflow = os.path.basename(mapping["clouds"][cloud]["workflow"])
    runs = json.loads(get(f"{API}/repos/{flagship['repository']}/actions/workflows/{workflow}/runs"
                          f"?event=schedule&branch={flagship['branch']}&per_page=50", token=True,
                          limit=50 * 1024 * 1024))["workflow_runs"]
    out = []
    for run in runs:
        kept = {k: run.get(k) for k in RUN_FIELDS}
        kept["repository"] = (run.get("repository") or {}).get("full_name")
        kept["head_repository"] = (run.get("head_repository") or {}).get("full_name")
        out.append(kept)
    json.dump(out, sys.stdout, indent=1, sort_keys=True)
    sys.stdout.write("\n")
    return 0


def main(argv):
    with open(os.environ.get("MAPPING", os.path.join(ROOT, "mapping", "controls.yaml")), encoding="utf-8") as f:
        mapping = YAML(typ="safe").load(f.read())
    if len(argv) == 3 and argv[0] == "run" and argv[1].isascii() and argv[1].isdigit():
        return fetch_run(mapping, argv[1], argv[2])
    if len(argv) == 2 and argv[0] == "list" and argv[1] in mapping["clouds"]:
        return list_runs(mapping, argv[1])
    if argv == ["kept"]:
        flagship = mapping["flagship"]
        index = json.loads(get(f"{RAW}/{flagship['repository']}/{flagship['results']}/index.json"))
        print("\n".join(sorted({str(r["run"]) for r in index})))
        return 0
    sys.stderr.write(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
