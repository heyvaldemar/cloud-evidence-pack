# Changelog

All notable changes to this project are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- AC-6 Least Privilege and IA-9 Service Identification and Authentication, on AWS, from the flagship's Vault checks (`tests/e2e/vault.sh`, its ADR 24). Twenty-four checks, each one line of a run. AC-6: Vault refuses a login by the agent's service account, by another service account beside the MCP server and by the MCP server's token for the Kubernetes API, an agent pod cannot reach Vault, and a delete with a valid credential is refused, beside six lines that had to hold. IA-9: the records service refuses no credential, a random key, the cluster's own token, a credential for another audience, one that lives an hour and an expired one, beside eight lines that had to hold. In the pack of the scheduled AWS run of 2026-11-12, 43199517532, both are satisfied, and 60 of its 121 lines are now named by the mapping. NIST's crosswalk relates A.5.15, A.8.2 and A.8.18 to AC-6 and nothing to IA-9.
- `since` in the mapping: the first scheduled run of a cloud whose results carried a control's lines. Every run from that one on is asked for the control, and a run that lost its lines leaves it not satisfied. An earlier run is not asked: its pack has no finding for the control and says so in the summary, in the assessment results and under `not_asked` in `verdict.json`. A static check requires a committed copy of every such first run, with the control satisfied in it ([ADR 6](docs/decisions/0006-a-control-is-asked-from-the-first-run-that-carried-it.md)).

### Changed

- The gate requires one finding for each control the run is asked for. A finding for a control the run is too early for fails the pack, as a missing one does from the first run on.
- Plants are listed for a run, not for a cloud: `python3 scripts/plant.py all DIR` takes a run's directory and prints the plants of the controls that run is asked for. `plant.py all <cloud>` is gone.
- The index names the mapping beside each pack's count, as in "6 of 6 controls satisfied, by mapping 1.0.1": a pack kept on the branch `packs` was judged by the mapping of the day it was built, and a later mapping may ask more of the same run.
- The mapping is 1.1.0. The pack of the AWS run of 2026-10-22 keeps its six findings and gains the note that AC-6 and IA-9 were not asked of it.

## [1.0.1] - 2026-11-13

### Added

- The scheduled AWS run of 2026-11-12, 43199517532, as a fifth committed copy (`tests/fixtures/runs/aws-43199517532`): 121 lines, and the first run that passed with the flagship's Vault checks, a GPU node, and the agent run a second time on a larger model.

### Changed

- A line a run writes more than once is a line each time: an observation of its own in the assessment results, the second marked `occurrence: 2`, and listed and counted so in the summary. Before, the same words were one observation, and for such a run the summary gave 5 lines where the finding beside it gave 7. Packs of runs that write no line twice are the same but for the mapping's version, which is 1.0.1.
- The gate verifies the flagship's signature on the run's record whenever it is given a pack. In 1.0.0 that was done only with `--signed`, and `python3 scripts/gate.py evidence` alone passed a pack whose record and run had been edited alike. `--signed` is still taken and changes nothing; `--unsigned` leaves cosign out, for the tests of the rules below the signature, and the gate's last line then says the signature was not asked for. The `forged-record` plant now also runs the gate with no flag and requires it to refuse the pack for the signature.
- `scripts/fetch.py` holds the record the branch's index leads to, to the run that was asked for. The index is not signed, so a record signed by the flagship must also be of that run, of the flagship's repository, and kept under `<cloud>/<run id>-<attempt>` as its own cloud, run and attempt give it; an index path of any other shape is not followed. In 1.0.0 a record the flagship had signed for one run was taken for whichever run the index named it for.
- In `scripts/pack.py` the field that says a Sigstore bundle lies beside the record is `has_bundle`, not `signed`: the builder only requires the bundle to be there, and cosign's verdict is `fetch.py`'s and the gate's.

### Fixed

- A check asked for one line where an AWS run with a GPU writes two, one each time it takes the agent through the evals, so a line lost one of those times hid behind the other. On run 43199517532, 3 of the 58 plants were not caught: `renamed:outside-email`, `renamed:control-email` and `renamed:gateway-every-request`. `written_together` in the mapping names the three checks, and each must have as many lines as the others ([ADR 5](docs/decisions/0005-a-line-written-twice-is-two-lines.md)). No pack of that run was kept or published before the fix.
- Run 43137012297, the release run of v1.0.0, is red in its last job: after the three packs had verified, the job took the repository's own source archive, which `release-assets.yml` signs as itself, for a fourth pack and failed on its identity. The signatures and the assets of v1.0.0 were not affected: they verify from an empty directory. The check is now a script, `scripts/release-verify.sh`: a pack is an archive named `<cloud>-<run id>` and nothing else, static check `release` runs it on one real pack of v1.0.0 in six cases, and five plants break it one way each.

## [1.0.0] - 2026-11-12

### Added

- A scheduled cloud run of heyvaldemar/kubernetes-air-gapped-ai-agent as an OSCAL evidence pack. `scripts/fetch.py` reads, with no token, what the flagship signed and kept on its branch `cloud-results` (its ADR 25): the record of the run, verified by cosign for one exact identity, the `e2e-results-<cloud>` artifact with the sha256 the record names, and the planted pods at the run's commit. `scripts/pack.py` refuses anything but a scheduled run on `main` that passed, with the signed record beside it and everything read being what that record says, then writes an assessment plan and assessment results with compliance-trestle's models: one observation per line of the run the mapping names, verbatim, and one finding per control with NIST's own statement id. The documents are a function of the run and the mapping alone.
- The mapping, `mapping/controls.yaml`: six controls of SP 800-53 Rev. 5.2.0, each a row of the flagship's `docs/compliance.md`. SC-7 and SC-7(5) on AWS, Google Cloud and Azure; AC-4, SI-7, SR-4 and SR-11 on AWS and Google Cloud. Each rests on a violation tried and refused in the run, beside something that had to succeed, and says what it leaves out. `scripts/component.py` holds it to NIST's catalog, the flagship's page at v1.9.0 and its planted pods, refuses a control resting on a planted pod its row of the page does not name, and writes `oscal/component-definition.json`.
- The gate, `scripts/gate.py`: it builds the documents again from the pack's own `run/` and fails if a byte differs, reads the findings with trestle's models, and fails on any control short of satisfied or any failed line. `--signed` has cosign verify the flagship's signature on the run's record, and `--live` asks GitHub for the run's record and the artifact's digest again.
- The plants, `scripts/plant.py` and `tests/e2e/plants.sh`: for every control on every cloud, its refusals gone, one failed, and everything beside them gone; every check renamed; a forged results file; findings edited to satisfied; a record and a run edited alike, which only the signature can tell; and ten runs that are not a scheduled run's own file, or not what the flagship signed. Each must be caught for its own reason on every committed run.
- Committed copies of real runs, each with the record the flagship signed, as its branch holds them: the scheduled runs 39744285464 (AWS), 42206932411 (Google Cloud), 41626192017 and 42809539539 (Azure), and the three runs by hand where the DNS check failed with the resolver's policy off, 39632816543, 40560466605 and 41007916564.
- Related criteria of ISO/IEC 27001:2022 beside each finding, from NIST's own crosswalk (OLIR informative reference 155, version 1.0.0), read from the spreadsheet NIST serves and pinned by sha256: what NIST relates to a control and to that control alone, and "none" where it relates nothing (SC-7(5), SI-7, SR-11). Never a finding. SOC 2 is not included: AICPA's mapping cannot be fetched and pinned by a build.
- The index, `scripts/index.py`: every scheduled run of each cloud as a pack, a run with no pack, or not built yet, and a cloud with no scheduled run in 10 days reported as missing, not as a failure.
- Static checks with one entry point, `scripts/validate.sh` (component, fixtures, images, trestle, gate, mutations, plants), each shown its violation by `tests/static/plant_violations.py`; and each rule of the builder, the gate and the index switched off in turn by `scripts/mutate.py`, which counts a test that only crashes as missed.
