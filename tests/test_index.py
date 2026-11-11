"""The index's rules: a leg that stopped running, a run that failed, and a run whose evidence was refused are three things.

Each test starts from the record of a real scheduled run
(tests/fixtures/runs) and changes its date, its conclusion or what was built
from it. scripts/mutate.py switches each rule off in turn (tests/plants.tsv).
"""
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.environ.get("SCRIPTS_DIR") or os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)
import index  # noqa: E402
import pack  # noqa: E402

MAPPING = pack.load_mapping(os.path.join(ROOT, "mapping", "controls.yaml"))
RUN = json.loads(pack.read_text(os.path.join(ROOT, "tests", "fixtures", "runs", "aks-42809539539", "run.json")))
NOV_11 = datetime.datetime(2026, 11, 11, 15, 0, tzinfo=datetime.timezone.utc)


def run(day, number=0, **changes):
    return dict(RUN, id=RUN["id"] + number, created_at=f"2026-{day}T11:41:38Z", **changes)


class Leg(unittest.TestCase):
    def setUp(self):
        self.packs = tempfile.mkdtemp(prefix="index-test-")
        self.addCleanup(shutil.rmtree, self.packs, ignore_errors=True)

    def built(self, record, name="verdict.json", text=None):
        here = os.path.join(self.packs, "aks", str(record["id"]))
        os.makedirs(here, exist_ok=True)
        with open(os.path.join(here, name), "w") as f:
            f.write(text or json.dumps({"controls": {"sc-7": {"state": "satisfied"}, "sc-7.5": {"state": "satisfied"}}}))

    def leg(self, runs, now=NOV_11):
        return index.leg(MAPPING, "aks", runs, self.packs, now)

    def test_a_cloud_that_ran_this_week(self):
        r = run("11-10")
        self.built(r)
        l = self.leg([r])
        self.assertFalse(l["missing"])
        self.assertEqual(l["state"], "running: last scheduled run 2026-11-10")
        self.assertEqual((l["runs"][0]["outcome"], l["runs"][0]["detail"]), ("pack", "2 of 2 controls satisfied"))

    def test_a_cloud_with_no_run_lately_is_missing(self):
        r = run("11-10")
        self.built(r)
        l = self.leg([r], datetime.datetime(2026, 12, 5, tzinfo=datetime.timezone.utc))
        self.assertTrue(l["missing"])
        self.assertEqual(l["state"], "missing: no scheduled run since 2026-11-10")
        self.assertEqual(l["runs"][0]["outcome"], "pack")

    def test_a_week_and_a_late_start_is_not_missing(self):
        self.assertFalse(self.leg([run("11-10")], datetime.datetime(2026, 11, 19, 12, tzinfo=datetime.timezone.utc))["missing"])

    def test_a_cloud_that_never_ran(self):
        l = self.leg([])
        self.assertTrue(l["missing"])
        self.assertEqual(l["state"], "missing: no scheduled run of this workflow is on record")

    def test_a_failed_run_is_a_run_with_no_pack_and_not_a_missing_leg(self):
        l = self.leg([run("11-10", conclusion="failure")])
        self.assertFalse(l["missing"])
        self.assertEqual((l["runs"][0]["outcome"], l["runs"][0]["detail"]), ("run with no pack", "the run ended failure"))

    def test_a_passed_run_whose_evidence_was_refused(self):
        r = run("11-10")
        self.built(r, "refused.txt", "the run kept no artifact to read, or it has expired\n")
        l = self.leg([r])
        self.assertFalse(l["missing"])
        self.assertEqual(l["runs"][0]["outcome"], "run with no pack")
        self.assertIn("kept no artifact", l["runs"][0]["detail"])

    def test_a_failed_run_with_a_pack_beside_it_is_still_a_failed_run(self):
        r = run("11-10", conclusion="failure")
        self.built(r)
        self.assertEqual(self.leg([r])["runs"][0]["outcome"], "run with no pack")

    def test_a_passed_run_nobody_has_read(self):
        self.assertEqual(self.leg([run("11-10")])["runs"][0]["outcome"], "not built yet")

    def test_a_run_that_has_not_ended(self):
        self.assertEqual(self.leg([run("11-10", status="in_progress", conclusion=None)])["runs"][0]["outcome"],
                         "still running")

    def test_packs_in_a_row(self):
        a, b, c = run("11-10", 2), run("11-03", 1), run("10-27", 0, conclusion="failure")
        self.built(a)
        self.built(b)
        self.assertEqual(self.leg([c, a, b])["packs_in_a_row"], 2)
        self.assertEqual([r["date"] for r in self.leg([c, a, b])["runs"]], ["2026-11-10", "2026-11-03", "2026-10-27"])

    def test_a_failed_week_ends_the_row(self):
        a, b = run("11-10", 1, conclusion="failure"), run("11-03", 0)
        self.built(b)
        self.assertEqual(self.leg([a, b])["packs_in_a_row"], 0)

    def test_a_run_not_yet_read_neither_adds_nor_ends_the_row(self):
        a, b = run("11-10", 1), run("11-03", 0)
        self.built(b)
        self.assertEqual(self.leg([a, b])["packs_in_a_row"], 1)

    def test_a_list_of_runs_that_cannot_be_read(self):
        runs = tempfile.mkdtemp(prefix="index-runs-")
        self.addCleanup(shutil.rmtree, runs, ignore_errors=True)
        for cloud in MAPPING["clouds"]:
            with open(os.path.join(runs, cloud + ".json"), "w") as f:
                f.write("[]" if cloud != "gke" else '{"message": "Bad credentials"}')
        p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "index.py"), runs, self.packs, self.packs],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)

    def test_a_missing_leg_does_not_fail_the_index(self):
        runs = tempfile.mkdtemp(prefix="index-runs-")
        self.addCleanup(shutil.rmtree, runs, ignore_errors=True)
        for cloud in MAPPING["clouds"]:
            with open(os.path.join(runs, cloud + ".json"), "w") as f:
                f.write("[]")
        out = os.path.join(self.packs, "out")
        p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "index.py"), runs, self.packs, out],
                           capture_output=True, text=True, env=dict(os.environ, NOW="2026-12-05T00:00:00Z"))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        doc = json.loads(pack.read_text(os.path.join(out, "index.json")))
        self.assertTrue(all(l["missing"] for l in doc["clouds"].values()))
        self.assertIn("## Azure: missing: no scheduled run of this workflow is on record",
                      pack.read_text(os.path.join(out, "index.md")))


if __name__ == "__main__":
    unittest.main()
