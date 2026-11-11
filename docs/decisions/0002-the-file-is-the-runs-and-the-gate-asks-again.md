# 2. The file is the run's because GitHub says so, and the gate builds the documents again

- Status: accepted
- Date: 2026-11-11

## Context

A pack built from another repository's run is worth what the link between them is worth. Two things can be wrong without anyone lying on purpose: the file is not that run's, or the documents do not say what the file says. GitHub's API reports a sha256 for every artifact, to anyone, with no token: for artifact 13761493439 of run 42809539539 it says `95f61d15bf2d8f519e5528989f1e3fd6ba37b5d8dc22d2c3c942c834c6334826`, and the zip downloaded from the same API hashes to that. The run's own record says it was started by the schedule, on `main`, by `.github/workflows/aks.yml`, and that it passed.

## Decision

1. **A pack's source is a scheduled run on `main` that passed, and nothing else.** `scripts/pack.py` refuses a run of another repository or a fork, of a workflow that is no cloud's, started by anything but the schedule, on another branch, unfinished or failed; an artifact of another run or another commit; and a file whose sha256 is not the digest GitHub reports. A run started by hand is never a source, however green.
2. **The pack carries the file.** The artifact is inside, byte for byte, beside the run's record, and the assessment results name it in back-matter with its hash.
3. **The documents are a function of the run and the mapping.** No clock and no random id: every identifier is derived from the run, and every time is the run's.
4. **The gate does not trust a pack.** `scripts/gate.py` builds the documents again from the pack's own `run/` and fails if a byte differs, so a finding edited afterwards is caught though trestle still reads it. With `--live` it asks GitHub again for the record and the digest.
5. **Nothing is signed that the gate has not passed**, and the signature is keyless, as this repository's workflow at its ref.

## Consequences

- A reader checks the file against GitHub, not against the author: two commands, printed at the end of every pack's `summary.md`.
- GitHub keeps an artifact for 90 days. After that the digest cannot be asked, and what remains is the signature and its entry in Sigstore's log: this repository's workflow, at a named commit, built the pack while the artifact existed.
- The record and the digest are public; the artifact's zip is not served without a token. Whether this repository's own token may download it is settled by its first workflow run.

## Alternatives

- **Each cloud run signs its own results.** The strongest chain: a forged file fails a signature, and nothing expires. It changes the flagship's cloud workflows, so it is not made here.
- **A workflow in the flagship that signs each run's artifact after the run and keeps it on a branch.** The same strength with no change to the cloud workflows, and no token needed to read it. The next step if this repository's token cannot read the artifacts.
- **Trust the pack's findings.** Then the pack is a spreadsheet with a signature on it.

## How to explain this to a customer

Inside each pack is the file the cloud run itself uploaded. You can ask GitHub for that file's fingerprint and compare, and you can ask GitHub who started the run. The check that judges a pack does not read its conclusions: it works them out again from that file and compares.
