# Changelog

All notable changes to this project are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- A scheduled cloud run of heyvaldemar/kubernetes-air-gapped-ai-agent as an OSCAL evidence pack. `scripts/fetch.py` reads the run's record, its `e2e-results-<cloud>` artifact with the sha256 GitHub reports for it, and the planted pods at the run's commit. `scripts/pack.py` refuses anything but a scheduled run on `main` that passed and whose file has that digest, then writes an assessment plan and assessment results with compliance-trestle's models: one observation per line of the run the mapping names, verbatim, and one finding per control with NIST's own statement id. The documents are a function of the run and the mapping alone.
- The mapping, `mapping/controls.yaml`: six controls of SP 800-53 Rev. 5.2.0, each a row of the flagship's `docs/compliance.md`. SC-7 and SC-7(5) on AWS, Google Cloud and Azure; AC-4, SI-7, SR-4 and SR-11 on AWS and Google Cloud. Each rests on a violation tried and refused in the run, beside something that had to succeed, and says what it leaves out. `scripts/component.py` holds it to NIST's catalog, the flagship's page at v1.9.0 and its planted pods, and writes `oscal/component-definition.json`.
- The gate, `scripts/gate.py`: it builds the documents again from the pack's own `run/` and fails if a byte differs, reads the findings with trestle's models, and fails on any control short of satisfied or any failed line. `--live` asks GitHub for the run's record and the artifact's digest again.
- The plants, `scripts/plant.py` and `tests/e2e/plants.sh`: for every control on every cloud, its refusals gone, one failed, and everything beside them gone; every check renamed; a forged results file; findings edited to satisfied; and seven runs that are not a scheduled run's own file. Each must be caught for its own reason on every committed run.
- Committed copies of real runs, as the API gave them: the scheduled runs 39744285464 (AWS), 42206932411 (Google Cloud), 41626192017 and 42809539539 (Azure), and the three runs by hand where the DNS check failed with the resolver's policy off, 39632816543, 40560466605 and 41007916564.
- The index, `scripts/index.py`: every scheduled run of each cloud as a pack, a run with no pack, or not built yet, and a cloud with no scheduled run in 10 days reported as missing, not as a failure.
- Static checks with one entry point, `scripts/validate.sh` (component, fixtures, images, trestle, gate, mutations, plants), each shown its violation by `tests/static/plant_violations.py`; and each rule of the builder, the gate and the index switched off in turn by `scripts/mutate.py`, which counts a test that only crashes as missed.
