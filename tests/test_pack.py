"""The builder's and the gate's rules, each fed what breaks it.

Every test starts from a committed copy of a real scheduled run
(tests/fixtures/runs: the run's record and its artifact, byte for byte as
GitHub's API gave them) and changes one thing. Class Signature and class
Branch have cosign judge the committed records, and need it on the PATH
and the network for Sigstore's trust root. scripts/mutate.py switches
each rule off in a copy of the scripts (tests/plants.tsv) and requires the
test named there to fail, so SCRIPTS_DIR says which scripts are under test.

    python3 -m unittest discover -s tests

Needs NIST's catalog in .cache (scripts/catalogs.sh).
"""
import contextlib
import copy
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
import zipfile
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.environ.get("SCRIPTS_DIR") or os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)
import fetch  # noqa: E402
import gate  # noqa: E402
import pack  # noqa: E402
import plant  # noqa: E402

RUNS = os.path.join(ROOT, "tests", "fixtures", "runs")
AWS, GKE, AKS = "aws-39744285464", "gke-42206932411", "aks-42809539539"
MAPPING = pack.load_mapping(os.path.join(ROOT, "mapping", "controls.yaml"))


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pack-test-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def run_dir(self, name=AKS):
        out = tempfile.mkdtemp(prefix=name + "-", dir=self.tmp)
        shutil.copytree(os.path.join(RUNS, name), out, dirs_exist_ok=True)
        return out

    def read(self, path, mode="r"):
        with open(path, mode) as f:
            return f.read()

    def write(self, path, text):
        with open(path, "w") as f:
            f.write(text)

    def edit(self, directory, name, change):
        path = os.path.join(directory, name)
        doc = json.loads(self.read(path))
        change(doc)
        self.write(path, json.dumps(doc, indent=1, sort_keys=True))

    def reasons(self, directory):
        return pack.provenance(MAPPING, pack.read_run(directory))[1]

    def results(self, directory, change):
        """The run's results changed, and the artifact's record made to agree, as if the run had written them."""
        r = pack.read_run(directory)
        plant.rewrite_results(directory, r["artifact"], change, agree=True)
        self.write(os.path.join(directory, "artifact.json"), json.dumps(r["artifact"], indent=1, sort_keys=True))

    def verdict(self, directory, mapping=MAPPING):
        return json.loads(pack.render(mapping, directory)["verdict.json"])

    def states(self, directory, mapping=MAPPING):
        return {c: v["state"] for c, v in self.verdict(directory, mapping)["controls"].items()}

    def build(self, directory):
        out = tempfile.mkdtemp(prefix="out-", dir=self.tmp)
        p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "pack.py"), directory, out],
                           capture_output=True, text=True)
        return p.returncode, os.path.join(out, "evidence"), p.stdout + p.stderr

    def gate(self, evidence, *args, env=None):
        p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "gate.py"), evidence, *args],
                           capture_output=True, text=True, env=dict(os.environ, **(env or {})))
        return p.returncode, p.stdout + p.stderr


class Provenance(Case):
    """Whose file this is: every way a run or a file can be something else."""

    def test_the_real_scheduled_runs_are_taken(self):
        for name in sorted(os.listdir(RUNS)):
            self.assertEqual(self.reasons(os.path.join(RUNS, name)), [], name)

    def refused(self, change, words, name="run.json", fixture=AKS):
        d = self.run_dir(fixture)
        self.edit(d, name, change)
        if name == "run.json":
            # The signed record is made to say the same, as a record of such a run would: the rule on the run
            # has to catch it alone.
            self.edit(d, "record.json", lambda record: change(record["run"]))
        reasons = self.reasons(d)
        self.assertEqual(len(reasons), 1, reasons)
        self.assertIn(words, reasons[0])
        code, evidence, out = self.build(d)
        self.assertEqual(code, 2, out)
        self.assertFalse(os.path.exists(evidence), "a refused run left a pack behind")

    def test_a_run_started_by_hand(self):
        self.refused(lambda r: r.update(event="workflow_dispatch"), "not by the schedule")

    def test_a_run_on_another_branch(self):
        self.refused(lambda r: r.update(head_branch="gpu-capacity"), "not on main")

    def test_a_run_of_another_workflow(self):
        self.refused(lambda r: r.update(path=".github/workflows/e2e.yml"), "no cloud's workflow")

    def test_a_run_of_another_repository(self):
        self.refused(lambda r: r.update(repository="someone/else"), "not of heyvaldemar/")

    def test_a_run_from_a_fork(self):
        self.refused(lambda r: r.update(head_repository="someone/kubernetes-air-gapped-ai-agent"), "not of heyvaldemar/")

    def test_a_run_that_failed(self):
        self.refused(lambda r: r.update(conclusion="failure"), "not a run that passed")

    def test_a_run_still_going(self):
        # A run started again: the attempt before it passed, and this one has not ended.
        self.refused(lambda r: r.update(status="in_progress"), "not a run that passed")

    def test_an_artifact_of_another_run(self):
        self.refused(lambda a: a.update(run_id=a["run_id"] + 1), "the artifact is run", "artifact.json")

    def test_an_artifact_from_another_commit(self):
        self.refused(lambda a: a.update(head_sha="0" * 40), "the artifact is run", "artifact.json")

    def test_an_artifact_under_another_name(self):
        d = self.run_dir(GKE)
        os.rename(os.path.join(d, "e2e-results-gke.zip"), os.path.join(d, "evals-results.zip"))
        self.edit(d, "artifact.json", lambda a: a.update(name="evals-results"))
        reasons = self.reasons(d)
        self.assertEqual(len(reasons), 1, reasons)
        self.assertIn("not e2e-results-gke", reasons[0])

    def test_a_file_changed_by_one_byte(self):
        d = self.run_dir()
        with open(os.path.join(d, "e2e-results-aks.zip"), "ab") as f:
            f.write(b"x")
        reasons = self.reasons(d)
        self.assertEqual(len(reasons), 1, reasons)
        self.assertIn("it is not the run's file", reasons[0])
        self.assertEqual(self.build(d)[0], 2)

    def test_a_run_that_kept_no_artifact(self):
        d = self.run_dir()
        os.remove(os.path.join(d, "artifact.json"))
        reasons = self.reasons(d)
        self.assertEqual(len(reasons), 1, reasons)
        self.assertIn("kept no artifact", reasons[0])
        self.assertEqual(self.build(d)[0], 2)

    def test_a_record_with_no_file_beside_it(self):
        d = self.run_dir()
        os.remove(os.path.join(d, "e2e-results-aks.zip"))
        reasons = self.reasons(d)
        self.assertEqual(len(reasons), 1, reasons)
        self.assertIn("its file is not", reasons[0])

    def one_reason(self, d, words):
        reasons = self.reasons(d)
        self.assertEqual(len(reasons), 1, reasons)
        self.assertIn(words, reasons[0])
        self.assertEqual(self.build(d)[0], 2)

    def test_no_signature_beside_the_record(self):
        d = self.run_dir()
        os.remove(os.path.join(d, "record.json.sigstore.json"))
        self.one_reason(d, "no record signed by the flagship")

    def test_no_record_from_the_flagship(self):
        d = self.run_dir()
        os.remove(os.path.join(d, "record.json"))
        self.one_reason(d, "no record signed by the flagship")

    def test_a_run_record_that_is_not_the_signed_one(self):
        # run.json says the run ended a second later than the record the flagship signed says.
        d = self.run_dir()
        self.edit(d, "run.json", lambda r: r.update(updated_at="2026-11-10T12:01:45Z"))
        self.one_reason(d, "the run's record here is not the one in the record the flagship signed")

    def test_an_artifact_record_that_is_not_the_signed_one(self):
        # The file and its record here agree with each other, and not with what the flagship signed.
        d = self.run_dir()
        signed = self.read(os.path.join(d, "record.json"))
        self.results(d, lambda doc: doc["checks"].pop())
        self.write(os.path.join(d, "record.json"), signed)
        self.one_reason(d, "the artifact's record here is not the one in the record the flagship signed")

    def test_a_record_kept_by_another_workflow(self):
        d = self.run_dir()
        self.edit(d, "record.json", lambda r: r.update(kept_by=".github/workflows/aks.yml"))
        self.one_reason(d, "the record was kept by .github/workflows/aks.yml")

    def test_no_record_of_the_run(self):
        d = self.run_dir()
        os.remove(os.path.join(d, "run.json"))
        self.assertEqual(self.build(d)[0], 2)


class Results(Case):
    """The artifact itself: what is not one run's results is refused, never read as empty."""

    def archive(self, members):
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as z:
            for name, body in members.items():
                z.writestr(name, body)
        return out.getvalue()

    def refused(self, archive, words):
        with self.assertRaises(pack.Refused) as e:
            pack.results_of(archive)
        self.assertIn(words, str(e.exception))

    def test_not_an_archive(self):
        self.refused(b"not a zip", "not a zip archive")

    def test_no_results_inside(self):
        self.refused(self.archive({"evals-results.json": "{}"}), "0 files named e2e-results.json")

    def test_two_results_inside(self):
        good = json.dumps({"checks": [{"name": "a", "passed": True}]})
        self.refused(self.archive({"a/e2e-results.json": good, "b/e2e-results.json": good}), "2 files named")

    def test_results_that_are_not_json(self):
        self.refused(self.archive({"e2e-results.json": "PASS"}), "not JSON")

    def test_results_with_no_checks(self):
        self.refused(self.archive({"e2e-results.json": json.dumps({"checks": []})}), "no list of checks")

    def test_a_check_that_does_not_say_whether_it_passed(self):
        body = json.dumps({"checks": [{"name": "a pod opens no TCP to 1.1.1.1:443", "passed": "yes"}]})
        self.refused(self.archive({"e2e-results.json": body}), "no list of checks")

    def test_the_real_artifacts_are_read(self):
        lines = {AWS: 56, GKE: 63, AKS: 21}
        for name, count in lines.items():
            r = pack.read_run(os.path.join(RUNS, name))
            self.assertEqual(len(pack.results_of(r["archive"])[2]), count, name)


class Judge(Case):
    """What a run's lines say of each control."""

    def test_the_real_runs(self):
        want = {AWS: ["sc-7", "sc-7.5", "ac-4", "si-7", "sr-4", "sr-11"], AKS: ["sc-7", "sc-7.5"]}
        want[GKE] = want[AWS]
        for name, controls in want.items():
            v = self.verdict(os.path.join(RUNS, name))
            self.assertEqual({c: "satisfied" for c in controls}, {c: s["state"] for c, s in v["controls"].items()}, name)
            self.assertEqual(v["failed_lines"], [], name)

    def drop(self, pattern):
        def change(doc):
            before = len(doc["checks"])
            doc["checks"] = [c for c in doc["checks"] if pattern not in c["name"]]
            assert len(doc["checks"]) < before, f"no line holds {pattern!r}"
        return change

    def test_a_refusal_that_is_not_in_the_run(self):
        d = self.run_dir(AWS)
        self.results(d, self.drop("model-nobom: refused"))
        s = self.states(d)
        self.assertEqual(s["sr-4"], "not-satisfied")
        self.assertEqual(s["sr-11"], "satisfied")

    def test_a_violation_that_got_in(self):
        d = self.run_dir(AWS)

        def change(doc):
            next(c for c in doc["checks"] if c["name"].startswith("model-unsigned: refused"))["passed"] = False
        self.results(d, change)
        v = self.verdict(d)
        self.assertEqual(v["controls"]["sr-11"]["state"], "not-satisfied")
        self.assertIn("failed: model-unsigned", "; ".join(v["controls"]["sr-11"]["why"]))
        self.assertEqual(len(v["failed_lines"]), 1)

    def test_a_failed_line_no_control_rests_on(self):
        d = self.run_dir(AWS)

        def change(doc):
            next(c for c in doc["checks"] if c["name"].startswith("records deleted: 0"))["passed"] = False
        self.results(d, change)
        v = self.verdict(d)
        self.assertEqual(len(v["failed_lines"]), 1)
        self.assertTrue(all(c["state"] == "satisfied" for c in v["controls"].values()))

    def test_one_of_two_lines_gone(self):
        # GKE writes two names the resolver must refuse; one alone is not the run the mapping describes.
        d = self.run_dir(GKE)
        self.results(d, self.drop("a pod cannot resolve example.org"))
        v = self.verdict(d)
        self.assertEqual(v["controls"]["sc-7"]["state"], "not-satisfied")
        self.assertIn("1 of the run's lines match, and 2 must", "; ".join(v["controls"]["sc-7"]["why"]))

    def test_a_line_renamed_upstream(self):
        d = self.run_dir()

        def change(doc):
            c = next(c for c in doc["checks"] if c["name"] == "a pod cannot ask a public resolver directly (8.8.8.8)")
            c["name"] = "a pod cannot ask a public resolver (8.8.8.8)"
        self.results(d, change)
        self.assertEqual(self.states(d), {"sc-7": "not-satisfied", "sc-7.5": "not-satisfied"})

    def test_a_line_with_more_after_it_is_another_line(self):
        d = self.run_dir()

        def change(doc):
            c = next(c for c in doc["checks"] if c["name"].startswith("control: the node opens TCP to"))
            c["name"] += ", or so it seemed"
        self.results(d, change)
        self.assertEqual(self.states(d)["sc-7"], "not-satisfied")

    def test_a_refusal_without_the_plants_own_words(self):
        # The run refused the pod, but not with what the pod's own file expects at that commit.
        d = self.run_dir(AWS)
        path = os.path.join(d, "plants", "model-unsigned.yaml")
        self.write(path, self.read(path).replace("# expect: signed with the operator's key",
                                                 "# expect: carries a valid signature"))
        v = self.verdict(d)
        self.assertEqual(v["controls"]["sr-11"]["state"], "not-satisfied")
        self.assertEqual(v["controls"]["sr-4"]["state"], "satisfied")

    def test_a_plant_the_runs_commit_does_not_have(self):
        d = self.run_dir(AWS)
        os.remove(os.path.join(d, "plants", "model-nobom.yaml"))
        v = self.verdict(d)
        self.assertEqual(v["controls"]["sr-4"]["state"], "not-satisfied")
        self.assertIn("has no planted pod model-nobom", "; ".join(v["controls"]["sr-4"]["why"]))

    def test_a_plant_that_expects_the_opposite(self):
        # The control pod's file says "admitted": named as a refusal, it proves nothing.
        mapping = copy.deepcopy(MAPPING)
        mapping["checks"]["model-signed"]["kind"] = "refusal"
        v = self.verdict(os.path.join(RUNS, AWS), mapping)
        self.assertEqual(v["controls"]["sr-4"]["state"], "not-satisfied")
        self.assertIn("expects a control", "; ".join(v["controls"]["sr-4"]["why"]))

    def test_a_plant_that_says_nothing_of_what_it_expects(self):
        d = self.run_dir(AWS)
        path = os.path.join(d, "plants", "model-signed.yaml")
        self.write(path, self.read(path).replace("# expect: admitted\n", ""))
        self.assertEqual(self.states(d)["sr-4"], "not-satisfied")

    def test_a_control_with_no_refusal(self):
        mapping = copy.deepcopy(MAPPING)
        next(c for c in mapping["controls"] if c["control"] == "sr-4")["checks"] = ["model-signed"]
        v = self.verdict(os.path.join(RUNS, AWS), mapping)
        self.assertEqual(v["controls"]["sr-4"]["state"], "not-satisfied")
        self.assertIn("no violation", "; ".join(v["controls"]["sr-4"]["why"]))

    def test_a_control_with_refusals_alone(self):
        mapping = copy.deepcopy(MAPPING)
        next(c for c in mapping["controls"] if c["control"] == "sr-4")["checks"] = ["model-nobom"]
        v = self.verdict(os.path.join(RUNS, AWS), mapping)
        self.assertEqual(v["controls"]["sr-4"]["state"], "not-satisfied")
        self.assertIn("nothing that had to succeed", "; ".join(v["controls"]["sr-4"]["why"]))

    def test_a_control_is_judged_only_where_it_is_mapped(self):
        self.assertEqual(sorted(self.states(os.path.join(RUNS, AKS))), ["sc-7", "sc-7.5"])

    def test_a_check_is_looked_for_only_where_it_is_written(self):
        v = self.verdict(os.path.join(RUNS, AWS))
        self.assertNotIn("vendor-registry", v["checks"])
        self.assertNotIn("pod-other-door", v["checks"])


class Documents(Case):
    """The OSCAL documents: a function of the run and the mapping, and nothing else."""

    def test_built_twice_they_are_the_same_bytes(self):
        d = os.path.join(RUNS, GKE)
        self.assertEqual(pack.render(MAPPING, d), pack.render(MAPPING, d))

    def test_every_finding_names_the_catalogs_own_statement(self):
        files = pack.render(MAPPING, os.path.join(RUNS, AWS))
        findings = json.loads(files["assessment-results.json"])["assessment-results"]["results"][0]["findings"]
        self.assertEqual({f["target"]["target-id"] for f in findings},
                         {"sc-7_smt", "sc-7.5_smt", "ac-4_smt", "si-7_smt", "sr-4_smt", "sr-11_smt"})

    def test_every_observation_is_a_line_of_the_run(self):
        for name in (AWS, GKE, AKS):
            r = pack.read_run(os.path.join(RUNS, name))
            lines = {c["name"] for c in pack.results_of(r["archive"])[2]}
            files = pack.render(MAPPING, os.path.join(RUNS, name))
            result = json.loads(files["assessment-results.json"])["assessment-results"]["results"][0]
            observed = [o["description"] for o in result["observations"]]
            self.assertTrue(observed and set(observed) <= lines, name)
            self.assertEqual(len(observed), len(set(observed)), name)
            uuids = {o["uuid"] for o in result["observations"]}
            for f in result["findings"]:
                self.assertTrue({o["observation-uuid"] for o in f["related-observations"]} <= uuids)

    def test_related_criteria_are_the_crosswalks_and_that_controls_alone(self):
        # NIST relates A.8.12 to SC-7(10) and A.8.11 to AC-4(23): neither is SC-7's or AC-4's.
        want = {"sc-7": ["A.5.14", "A.8.16", "A.8.20", "A.8.22", "A.8.23"], "sc-7.5": [],
                "ac-4": ["A.5.14", "A.8.22", "A.8.23"], "si-7": [], "sr-4": ["A.5.21", "A.8.30"], "sr-11": []}
        files = pack.render(MAPPING, os.path.join(RUNS, AWS))
        verdict = json.loads(files["verdict.json"])
        self.assertEqual({c: v["related"]["iso-27001-2022"] for c, v in verdict["controls"].items()}, want)
        doc = json.loads(files["assessment-results.json"])["assessment-results"]
        for f in doc["results"][0]["findings"]:
            control = next(p["value"] for p in f["props"] if p["name"] == "control")
            named = [p["value"] for p in f["props"] if p["name"] == "related-iso-27001-2022"]
            self.assertEqual(named, want[control] or ["none"], control)
        hashes = [h["value"] for res in doc["back-matter"]["resources"] if res["title"].startswith("Crosswalk")
                  for l in res["rlinks"] for h in l.get("hashes", [])]
        self.assertEqual(hashes, ["e631de234a1fac057991773f015c221226940540f5602e1b70a3768eaff5cbd9"])

    def test_the_artifacts_hash_is_the_files(self):
        d = os.path.join(RUNS, AKS)
        r = pack.read_run(d)
        doc = json.loads(pack.render(MAPPING, d)["assessment-results.json"])["assessment-results"]
        def hashes(title):
            return [h["value"] for res in doc["back-matter"]["resources"] if title in res["title"]
                    for l in res["rlinks"] for h in l.get("hashes", [])]
        self.assertEqual(hashes("e2e-results-aks"), [pack.sha256(r["archive"])] * 3)
        self.assertEqual(hashes("signed record"), [r["record_sha256"]] * 2)
        self.assertEqual(r["record_sha256"], pack.sha256(self.read(os.path.join(d, "record.json"), "rb")))

    def test_a_pack_holds_the_run_it_was_built_from(self):
        code, evidence, out = self.build(os.path.join(RUNS, AWS))
        self.assertEqual(code, 0, out)
        for name in ("summary.md", "assessment-plan.json", "assessment-results.json", "verdict.json", "mapping.yaml",
                     "run/run.json", "run/artifact.json", "run/e2e-results-aws.zip", "run/plants/model-signed.yaml"):
            self.assertTrue(os.path.exists(os.path.join(evidence, name)), name)
        self.assertEqual(self.read(os.path.join(evidence, "run", "e2e-results-aws.zip"), "rb"),
                         self.read(os.path.join(RUNS, AWS, "e2e-results-aws.zip"), "rb"))


class Gate(Case):
    """The gate, on packs built from the real runs and then changed."""

    def pack(self, name=AKS, before=None):
        d = self.run_dir(name)
        if before:
            before(d)
        code, evidence, out = self.build(d)
        self.assertEqual(code, 0, out)
        return evidence

    def gate(self, evidence, *args, env=None):
        # The rules below the signature. Most of these packs carry a record changed on purpose, which cosign
        # would refuse before any of them was reached: class Signature has the gate as a reader runs it.
        return super().gate(evidence, "--unsigned", *args, env=env)

    def rewrite(self, evidence, name, old, new):
        path = os.path.join(evidence, name)
        text = self.read(path)
        self.assertIn(old, text)
        self.write(path, text.replace(old, new))

    def test_the_real_runs_pass(self):
        for name in (AWS, GKE, AKS):
            code, out = self.gate(self.pack(name))
            self.assertEqual(code, 0, out)

    def test_a_control_not_satisfied(self):
        evidence = self.pack(AWS, lambda d: plant.apply(MAPPING, d, "missing:sr-4"))
        code, out = self.gate(evidence)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL control sr-4: not-satisfied", out)
        self.assertNotIn("FAIL documents", out)

    def test_a_failed_line(self):
        def change(d):
            r = pack.read_run(d)

            def flip(doc):
                next(c for c in doc["checks"] if c["name"].startswith("records deleted"))["passed"] = False
            plant.rewrite_results(d, r["artifact"], flip, agree=True)
            self.write(os.path.join(d, "artifact.json"), json.dumps(r["artifact"]))
        code, out = self.gate(self.pack(AWS, change))
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL line records deleted", out)
        self.assertNotIn("FAIL control", out)

    def test_findings_edited_to_satisfied(self):
        evidence = self.pack(AWS, lambda d: plant.apply(MAPPING, d, "failed:sr-11"))
        plant.forge(evidence)
        self.assertEqual({s for states in gate.read(evidence).values() for s, _ in states}, {"satisfied"})
        _, differ = gate.rebuilt(MAPPING, evidence)
        self.assertEqual(differ, ["assessment-results.json"])
        code, out = self.gate(evidence)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL documents assessment-results.json", out)

    def test_a_summary_that_says_more(self):
        evidence = self.pack()
        self.rewrite(evidence, "summary.md", "2 of 2 mapped controls", "6 of 6 mapped controls")
        code, out = self.gate(evidence)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL documents summary.md", out)

    def test_a_pack_judged_by_another_mapping(self):
        evidence = self.pack()
        self.rewrite(evidence, "mapping.yaml", "version: 1.0.0", "version: 9.9.9")
        code, out = self.gate(evidence)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL documents mapping.yaml", out)

    def test_a_document_that_is_gone(self):
        evidence = self.pack()
        os.remove(os.path.join(evidence, "verdict.json"))
        self.assertEqual(gate.rebuilt(MAPPING, evidence)[1], ["verdict.json"])

    def test_a_control_with_no_finding(self):
        v = self.verdict(os.path.join(RUNS, AKS))
        failures = gate.judge(MAPPING, v, {"sc-7": [("satisfied", "")]}, [])
        self.assertEqual([(k, w) for k, w, _ in failures], [("control", "sc-7.5")])

    def test_a_control_with_two_findings(self):
        v = self.verdict(os.path.join(RUNS, AKS))
        found = {"sc-7": [("satisfied", ""), ("satisfied", "")], "sc-7.5": [("satisfied", "")]}
        self.assertEqual([(k, w) for k, w, _ in gate.judge(MAPPING, v, found, [])], [("control", "sc-7")])

    def test_a_finding_that_is_not_satisfied(self):
        v = self.verdict(os.path.join(RUNS, AKS))
        found = {"sc-7": [("not-satisfied", "why")], "sc-7.5": [("satisfied", "")]}
        self.assertEqual([(k, w) for k, w, _ in gate.judge(MAPPING, v, found, [])], [("control", "sc-7")])

    def test_a_finding_for_a_control_not_mapped_there(self):
        v = self.verdict(os.path.join(RUNS, AKS))
        found = {"sc-7": [("satisfied", "")], "sc-7.5": [("satisfied", "")], "sr-11": [("satisfied", "")]}
        self.assertEqual([(k, w) for k, w, _ in gate.judge(MAPPING, v, found, [])], [("control", "sr-11")])

    def test_a_document_trestle_cannot_read(self):
        evidence = self.pack()
        self.write(os.path.join(evidence, "assessment-results.json"), "{}")
        with self.assertRaises(gate.Unreadable):
            gate.read(evidence)
        self.assertEqual(self.gate(evidence)[0], 2)

    def test_a_plan_that_is_not_there(self):
        evidence = self.pack()
        os.remove(os.path.join(evidence, "assessment-plan.json"))
        with self.assertRaises(gate.Unreadable):
            gate.read(evidence)
        self.assertEqual(self.gate(evidence)[0], 2)

    def test_a_pack_whose_run_was_changed_afterwards(self):
        evidence = self.pack()
        plant.apply(MAPPING, os.path.join(evidence, "run"), "by-hand")
        code, out = self.gate(evidence)
        self.assertEqual(code, 2, out)
        self.assertIn("not by the schedule", out)

    def test_a_pack_with_no_run_inside(self):
        evidence = self.pack()
        shutil.rmtree(os.path.join(evidence, "run"))
        self.assertEqual(self.gate(evidence)[0], 2)

    def test_the_verdicts_are_kept_for_the_status_branch(self):
        results = os.path.join(self.tmp, "e2e-results.json")
        code, out = self.gate(self.pack(), env={"E2E_RESULTS": results})
        self.assertEqual(code, 0, out)
        doc = json.loads(self.read(results))
        self.assertEqual([c["state"] for c in doc["checks"]], ["PASS", "PASS", "PASS"])
        self.assertEqual(doc["measured"], ["controls satisfied: 2 of 2"])


class Signature(Case):
    """The flagship's signature on the record: cosign, one exact identity. Needs cosign and Sigstore's trust root."""

    def verify(self, d, identity=None):
        record = os.path.join(d, "record.json")
        why = fetch.verify(record, record + ".sigstore.json", identity or fetch.signer(MAPPING))
        if why and any(w in why for w in ("tuf refresh failed", "error getting live trusted root", "dial tcp",
                                          "i/o timeout", "cannot be run")):
            self.fail(f"cosign could not judge: {why}")
        return why

    def test_the_identity_is_one_string(self):
        self.assertEqual(fetch.signer(MAPPING), "https://github.com/heyvaldemar/kubernetes-air-gapped-ai-agent/"
                                                ".github/workflows/cloud-results.yml@refs/heads/main")

    def test_the_committed_records_are_the_flagships(self):
        fixtures = os.path.dirname(RUNS)
        for kind in ("runs", "violations"):
            for name in sorted(os.listdir(os.path.join(fixtures, kind))):
                self.assertIsNone(self.verify(os.path.join(fixtures, kind, name)), name)

    def test_another_identity_is_refused(self):
        # The same repository, on main, another workflow: a cloud job's own identity is not the signer's.
        why = self.verify(os.path.join(RUNS, AKS), fetch.signer(MAPPING).replace("cloud-results.yml", "aks.yml"))
        self.assertIsNotNone(why)

    def test_a_record_with_one_space_added_is_refused(self):
        d = self.run_dir()
        with open(os.path.join(d, "record.json"), "a") as f:
            f.write(" ")
        self.assertIsNotNone(self.verify(d))

    def forged(self):
        d = self.run_dir()
        plant.apply(MAPPING, d, "forged-record")
        self.assertEqual(self.reasons(d), [])
        code, evidence, out = self.build(d)
        self.assertEqual(code, 0, out)
        return evidence

    def test_the_gate_checks_the_signature(self):
        # Record and run edited alike: every rule that reads them agrees, and only the signature can tell.
        evidence = self.forged()
        # Given the pack and no flag, as a reader runs it, the gate refuses it.
        code, out = self.gate(evidence)
        self.assertEqual(code, 2, out)
        self.assertIn("signature on the run's record does not verify", out)
        # Only when told to leave cosign out does it pass, and then it says what it left out.
        code, out = self.gate(evidence, "--unsigned")
        self.assertEqual(code, 0, out)
        self.assertIn("signature on the record was NOT asked for (--unsigned)", out)
        self.assertNotIn("signature on the record verifies", out)

    def test_the_gate_takes_a_record_the_flagship_signed(self):
        code, evidence, out = self.build(os.path.join(RUNS, AKS))
        self.assertEqual(code, 0, out)
        code, out = self.gate(evidence)
        self.assertEqual(code, 0, out)
        self.assertIn("the flagship's signature on the record verifies", out)
        # What 1.0.0 asked for with a flag is still taken, and is the same thing.
        self.assertEqual(self.gate(evidence, "--signed")[1], out)
        # Asked for and left out at once is not an answer.
        self.assertEqual(self.gate(evidence, "--signed", "--unsigned")[0], 2)

    def test_a_forged_record_under_its_plant(self):
        self.assertTrue(gate.planted(MAPPING, self.forged(), "forged-record")[0])
        code, evidence, out = self.build(os.path.join(RUNS, AKS))
        caught, why = gate.planted(MAPPING, evidence, "forged-record")
        self.assertFalse(caught, why)
        self.assertIn("cosign verified", why)


class Branch(Case):
    """Reading a run from the flagship's branch. Its index.json is not signed, so the record it leads to must be
    the one that was asked for. The branch here is the committed runs, served where raw.githubusercontent.com
    would be; the records, their signatures, cosign and the rules are the real ones."""

    BASE = f"{fetch.RAW}/{MAPPING['flagship']['repository']}/{MAPPING['flagship']['results']}"
    RUN, PLACE = AKS.split("-")[1], "aks/" + AKS.split("-")[1] + "-1"

    def fetch(self, path, kept=AKS, record=None, verify=None):
        """fetch.py's run of RUN, the index keeping it under `path`, where the committed run `kept` is served."""
        asked = []

        def get(url, token=False, limit=fetch.MAX_ARTIFACT):
            asked.append(url)
            if url == f"{self.BASE}/index.json":
                return json.dumps([{"run": int(self.RUN), "attempt": 1, "path": path}]).encode()
            name = url.rsplit("/", 1)[1]
            if name == "record.json" and record is not None:
                return record
            return self.read(os.path.join(RUNS, kept, name), "rb")

        def no_plant(*_, **__):
            raise urllib.error.HTTPError("", 404, "no plant is served here", None, None)

        out = os.path.join(tempfile.mkdtemp(dir=self.tmp), "fetched")
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(fetch, "get", get))
            stack.enter_context(mock.patch.object(urllib.request, "urlopen", no_plant))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            if verify:
                stack.enter_context(mock.patch.object(fetch, "verify", verify))
            try:
                code, why = fetch.fetch_run(MAPPING, self.RUN, out), ""
            except SystemExit as e:
                code, why = None, str(e)
        if "is not signed as" in why and any(w in why for w in ("tuf refresh failed", "error getting live trusted root",
                                                                "dial tcp", "i/o timeout", "cannot be run")):
            self.fail(f"cosign could not judge: {why}")
        return code, why, out, asked

    def test_a_run_the_branch_keeps(self):
        code, why, out, _ = self.fetch(self.PLACE)
        self.assertEqual(code, 0, why)
        for name in ("record.json", "record.json.sigstore.json", "e2e-results-aks.zip"):
            self.assertEqual(self.read(os.path.join(out, name), "rb"), self.read(os.path.join(RUNS, AKS, name), "rb"))
        for name in ("run.json", "jobs.json", "artifact.json"):
            self.assertEqual(json.loads(self.read(os.path.join(out, name))),
                             json.loads(self.read(os.path.join(RUNS, AKS, name))), name)

    def test_an_index_that_leads_to_another_runs_record(self):
        # The plant: for the run asked for, the index names the place of another run. That record is the
        # flagship's own and cosign verifies it. It is not the record of the run that was asked for.
        code, why, out, _ = self.fetch("aks/41626192017-1", kept="aks-41626192017")
        self.assertIsNone(code, "the record of another run was taken for the run that was asked for")
        self.assertIn("is signed by the flagship, and is not that run's", why)
        self.assertIn("it is the record of run 41626192017", why)
        self.assertEqual(os.listdir(out), [])

    def test_a_record_kept_under_another_cloud(self):
        code, why, out, _ = self.fetch("gke/" + self.RUN + "-1")
        self.assertIsNone(code, "a record of Azure was taken from under gke/")
        self.assertIn(f"it is kept under gke/{self.RUN}-1, and its own place is {self.PLACE}", why)
        self.assertNotIn("it is the record of run", why)
        self.assertEqual(os.listdir(out), [])

    def test_a_record_kept_under_another_attempt(self):
        code, why, _, _ = self.fetch("aks/" + self.RUN + "-2")
        self.assertIsNone(code, "the record of attempt 1 was taken from the place of attempt 2")
        self.assertIn(f"its own place is {self.PLACE}", why)

    def test_a_record_of_another_repository(self):
        # No such record can carry the flagship's signature, so cosign is left out of this one: the rule alone.
        doc = json.loads(self.read(os.path.join(RUNS, AKS, "record.json")))
        doc["repository"] = "someone/else"
        code, why, _, _ = self.fetch(self.PLACE, record=json.dumps(doc).encode(), verify=lambda *_: None)
        self.assertIsNone(code, "a record of another repository was taken")
        self.assertIn("it is a record of someone/else", why)

    def test_an_index_path_that_leaves_the_branch(self):
        for path in ("../../../someone/else/main/" + self.PLACE, self.PLACE + "/../../gke/1-1",
                     "https://example.com/" + self.PLACE, self.PLACE + "?ref=", "AKS/" + self.RUN + "-1", None):
            code, why, _, asked = self.fetch(path)
            self.assertIsNone(code, path)
            self.assertIn("which is not <cloud>/<run id>-<attempt>", why)
            self.assertEqual(asked, [f"{self.BASE}/index.json"], f"{path} was followed")


class Plants(Case):
    """--plant: a plant counts as caught only for its own reason."""

    def pack(self, name, *applied):
        d = self.run_dir(name)
        for p in applied:
            plant.apply(MAPPING, d, p)
        code, evidence, out = self.build(d)
        self.assertEqual(code, 0, out)
        return evidence

    def test_a_plant_that_was_never_planted(self):
        caught, why = gate.planted(MAPPING, self.pack(AWS), "missing:sr-4")
        self.assertFalse(caught, why)
        self.assertEqual(self.gate(self.pack(AWS), "--plant", "missing:sr-4")[0], 1)

    def test_a_plant_caught(self):
        evidence = self.pack(AWS, "missing:sr-4")
        self.assertEqual(gate.planted(MAPPING, evidence, "missing:sr-4")[0], True)
        self.assertEqual(self.gate(evidence, "--plant", "missing:sr-4")[0], 0)

    def test_a_plant_that_broke_more_than_its_own(self):
        evidence = self.pack(AWS, "missing:sr-4", "missing:ac-4")
        caught, why = gate.planted(MAPPING, evidence, "missing:sr-4")
        self.assertFalse(caught, why)
        self.assertIn("ac-4", why)

    def test_a_plant_that_broke_less_than_it_must(self):
        # bundle-tampered holds SI-7 and SR-11; a pack where only SI-7 fell is not that plant caught.
        evidence = self.pack(AWS, "renamed:registry-exact")
        caught, why = gate.planted(MAPPING, evidence, "renamed:bundle-tampered")
        self.assertFalse(caught, why)

    def test_a_failed_plant_whose_line_was_not_counted(self):
        evidence = self.pack(AWS, "missing:sr-4")
        caught, why = gate.planted(MAPPING, evidence, "failed:sr-4")
        self.assertFalse(caught, why)
        self.assertIn("failed line was not counted", why)

    def test_edited_findings_under_a_plant_of_the_run(self):
        evidence = self.pack(AWS, "failed:sr-4")
        plant.forge(evidence)
        caught, why = gate.planted(MAPPING, evidence, "failed:sr-4")
        self.assertFalse(caught, why)
        self.assertEqual(gate.planted(MAPPING, evidence, "forged-findings")[0], True)

    def test_a_plant_whose_pack_was_also_edited(self):
        # The findings are the plant's, but the summary was changed: not a pack the run gives.
        evidence = self.pack(AWS, "missing:sr-4")
        path = os.path.join(evidence, "summary.md")
        self.write(path, self.read(path).replace("5 of 6 mapped controls", "6 of 6 mapped controls"))
        caught, why = gate.planted(MAPPING, evidence, "missing:sr-4")
        self.assertFalse(caught, why)
        self.assertIn("documents differ", why)

    def test_untouched_findings_are_not_forged_ones(self):
        self.assertFalse(gate.planted(MAPPING, self.pack(AWS, "failed:sr-4"), "forged-findings")[0])

    def test_a_run_refused_for_another_reason(self):
        evidence = self.pack(AKS)
        plant.apply(MAPPING, os.path.join(evidence, "run"), "branch")
        self.assertFalse(gate.planted(MAPPING, evidence, "by-hand")[0])
        self.assertTrue(gate.planted(MAPPING, evidence, "branch")[0])

    def test_a_run_refused_for_two_reasons(self):
        evidence = self.pack(AKS)
        plant.apply(MAPPING, os.path.join(evidence, "run"), "branch")
        plant.apply(MAPPING, os.path.join(evidence, "run"), "by-hand")
        self.assertFalse(gate.planted(MAPPING, evidence, "by-hand")[0])

    def test_a_run_taken_though_it_was_planted(self):
        caught, why = gate.planted(MAPPING, self.pack(AKS), "by-hand")
        self.assertFalse(caught, why)

    def test_every_control_has_its_three_plants_on_every_cloud(self):
        for cloud in MAPPING["clouds"]:
            names = plant.every(MAPPING, cloud)
            for c in MAPPING["controls"]:
                if cloud in c["clouds"]:
                    for kind in plant.CONTROL_PLANTS:
                        self.assertIn(f"{kind}:{c['control']}", names)
            for provenance in plant.PROVENANCE:
                self.assertIn(provenance, names)


if __name__ == "__main__":
    unittest.main()
