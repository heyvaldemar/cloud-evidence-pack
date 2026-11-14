# Working on this repository as an agent

Most of the code here is written by an AI agent, and the decisions and the verification are the maintainer's. This file is what the agent is held to. A reviewer can hold it to the same rules.

## What this repository claims

Only what a named scheduled run of the flagship shows. Every number in the README comes from one run's own artifact and links to the run. A control is called satisfied in one run, by the rule written in `scripts/pack.py`. Nothing here says that a system meets a framework, holds an attestation or has been reviewed by an assessor, because nothing here could show it, and the README says what a pack does not prove.

## The runs are read, never started

No cloud workflow is dispatched from here and no cloud resource is made, for any reason. A pack's source is a scheduled run on the flagship's `main` that passed. A run started by hand is not one, however green, and the builder refuses it.

## The mapping

A control goes into `mapping/controls.yaml` only when the flagship's `docs/compliance.md` has the row, the check that row names writes a line into the cloud run's results, and the run shows a violation that check refused beside something that had to succeed. A planted pod counts for a control only when that row of the page names it. Each control says what it leaves out. A line is named to its end: a pattern that ends in "anything" is a pattern a renamed line still matches. `scripts/component.py` refuses a mapping that names a control, a row, a check or a planted pod that does not exist, and `oscal/component-definition.json` is never edited by hand.

## A check is trusted only after it has failed

A new or changed rule in the builder, the gate or the index ships with a test that feeds it what breaks it, and a line in `tests/plants.tsv` that switches the rule off; `scripts/mutate.py` must report it caught, by an assertion and not by a crash. A new or changed static check in `scripts/validate.sh` ships with a line in `tests/static/plants.tsv`, and `tests/static/plant_violations.py` must report it caught. A new control or check in the mapping gets its plants from `scripts/plant.py` with no further work, and `tests/e2e/plants.sh` must catch every one on every committed run.

## The fixtures are real

`tests/fixtures/runs` and `tests/fixtures/violations` hold runs as `scripts/fetch.py` wrote them: the record the flagship signed with its Sigstore bundle, and the artifact byte for byte, whose sha256 the record names. A fixture is never edited; a test changes a copy. A new fixture is fetched, not written.

## A new run, and a cloud added to a control

Every plant is run on a run before a pack of it is kept or released: `python3 scripts/plant.py all DIR` lists them, and `tests/e2e/plants.sh` must catch each. The gate passing is not that. The pack of AWS run 43199517532 passed the gate, and three plants were missed on it ([decision 5](docs/decisions/0005-a-line-written-twice-is-two-lines.md)).

A control with `since` is asked of a cloud's runs from the run it names for that cloud, and of none before ([decision 6](docs/decisions/0006-a-control-is-asked-from-the-first-run-that-carried-it.md)). A cloud's first run is its own, never the earliest of any cloud. Adding a cloud to such a control is one change:

- the run, fetched with `scripts/fetch.py run RUN_ID DIR` and committed under `tests/fixtures/runs`;
- the cloud on the control and on each of its checks, with its own `since`;
- the tests of `since`, of the gate and of the plants, looping over that cloud;
- the lines of `tests/plants.tsv` and `tests/static/plants.tsv` that anchor on the old text, moved to the new. A line whose text is gone fails the check; it is never skipped.

## Numbers

Every count in the README, the changelog and a release's notes is copied from the output of one named run, and the text links to it: a cloud run for its lines, a `Pack` run on `main` for the tests, the rules switched off and the plants. A run's lines are counted as recorded results, not as distinct names, since with a GPU the flagship writes some of them twice. When a count is given in parts, each part says what wrote it.

## Releases

A tag is never moved and a release is never rebuilt. A mistake is a new patch release. The tag goes on a commit of `main` whose `Pack` run passed. On the tag, `pack.yml` builds the packs, signs them, gives them provenance, attaches them and verifies them again, and `release-assets.yml` signs the source archive. When both have passed, `scripts/stranger.sh TAG` is run with an empty environment and an empty home, and the release is spoken of only after it ends with every check as expected. A pack kept on the branch `packs` is never rebuilt: each names the mapping that built it.

## Order of work

The whole CI path passes from a clean clone before a push to `main`: a file that only `.cache` had has cost a run. Scripts, the mapping and the tests are not edited while `validate.sh`, `plants.sh` or `plant_violations.py` run in the same tree, since bash reads a script as it runs it. Pushes to `main` queue behind each other, about half an hour each. The daily run is set for 16:23 UTC, and GitHub may start it hours later. `main` takes no force-push and cannot be deleted, and nothing here needs either.

## Pins

The flagship's page by release and archive sha256, verified with cosign and slsa-verifier. NIST's catalog by commit and sha256. Tools by version and sha256 for each platform. compliance-trestle and its dependencies by hash. Moving any of them is a commit that says what changed and why, after the workflow passes on it.

## Secrets

None are stored and none are needed: a run is read from the flagship's public branch with no token, and the workflow's own token is sent to GitHub's API for the rate limit alone.
