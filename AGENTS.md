# Working on this repository as an agent

Most of the code here is written by an AI agent, and the decisions and the verification are the maintainer's. This file is what the agent is held to. A reviewer can hold it to the same rules.

## What this repository claims

Only what a named scheduled run of the flagship shows. Every number in the README comes from one run's own artifact and links to the run. A control is called satisfied in one run, by the rule written in `scripts/pack.py`. Nothing here says that a system meets a framework, holds an attestation or has been reviewed by an assessor, because nothing here could show it, and the README says what a pack does not prove.

## The runs are read, never started

No cloud workflow is dispatched from here and no cloud resource is made, for any reason. A pack's source is a scheduled run on the flagship's `main` that passed. A run started by hand is not one, however green, and the builder refuses it.

## The mapping

A control goes into `mapping/controls.yaml` only when the flagship's `docs/compliance.md` has the row, the check that row names writes a line into the cloud run's results, and the run shows a violation that check refused beside something that had to succeed. Each control says what it leaves out. A line is named to its end: a pattern that ends in "anything" is a pattern a renamed line still matches. `scripts/component.py` refuses a mapping that names a control, a row, a check or a planted pod that does not exist, and `oscal/component-definition.json` is never edited by hand.

## A check is trusted only after it has failed

A new or changed rule in the builder, the gate or the index ships with a test that feeds it what breaks it, and a line in `tests/plants.tsv` that switches the rule off; `scripts/mutate.py` must report it caught, by an assertion and not by a crash. A new or changed static check in `scripts/validate.sh` ships with a line in `tests/static/plants.tsv`, and `tests/static/plant_violations.py` must report it caught. A new control or check in the mapping gets its plants from `scripts/plant.py` with no further work, and `tests/e2e/plants.sh` must catch every one on every committed run.

## The fixtures are real

`tests/fixtures/runs` and `tests/fixtures/violations` hold runs as `scripts/fetch.py` wrote them: the record, and the artifact byte for byte, whose sha256 is the digest GitHub reported. A fixture is never edited; a test changes a copy. A new fixture is fetched, not written.

## Pins

The flagship's page by release and archive sha256, verified with cosign and slsa-verifier. NIST's catalog by commit and sha256. Tools by version and sha256 for each platform. compliance-trestle and its dependencies by hash. Moving any of them is a commit that says what changed and why, after the workflow passes on it.

## Secrets

None are stored and none are needed beyond the workflow's own token. A download address GitHub signs is followed and never printed.
