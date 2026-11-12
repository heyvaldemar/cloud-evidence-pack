# 2. The file is the run's because the flagship signed it, and the gate builds the documents again

- Status: accepted
- Date: 2026-11-11

## Context

A pack built from another repository's run is worth what the link between them is worth. Two things can be wrong without anyone lying on purpose: the file is not that run's, or the documents do not say what the file says. GitHub's API reports a sha256 for every artifact, to anyone, with no token: for artifact 13761493439 of run 42809539539 it says `95f61d15bf2d8f519e5528989f1e3fd6ba37b5d8dc22d2c3c942c834c6334826`, and the zip downloaded from the same API hashes to that. The run's own record says it was started by the schedule, on `main`, by `.github/workflows/aks.yml`, and that it passed.

## Decision

1. **A pack's source is what the flagship signed.** Since its ADR 25 the flagship's workflow `cloud-results.yml` keeps every finished cloud run on a branch: a record of the run's facts with the sha256 of the results it uploaded, signed keyless on main. `scripts/fetch.py` reads the record, its Sigstore bundle and the file with no token, and takes them only when cosign verifies the record for one exact identity, that workflow at `refs/heads/main`, and the file has the sha256 the record names. The branch's `index.json` says where each run is kept, and nobody signed it. So a signed record is also held to the run that was asked for: it must be that run's, the flagship's, and kept under `<cloud>/<run id>-<attempt>` as the record itself gives them, and an index path of any other shape is not followed.
2. **Of those, only a scheduled run on `main` that passed.** `scripts/pack.py` refuses a run with no signed record beside it, a run or an artifact that is not what the record says, a run of another repository or a fork, of a workflow that is no cloud's, started by anything but the schedule, on another branch, unfinished or failed. A run started by hand is never a source, however green.
3. **The pack carries the record, the signature and the file**, and the assessment results name them in back-matter with their hashes.
4. **The documents are a function of the run and the mapping.** No clock and no random id: every identifier is derived from the run, and every time is the run's.
5. **The gate does not trust a pack.** `scripts/gate.py` builds the documents again from the pack's own `run/` and fails if a byte differs, so a finding edited afterwards is caught though trestle still reads it. It has cosign verify the record again, every time it is given a pack: a record and a run edited alike agree with every other rule, so a gate that left the signature to a flag would pass a forgery to anyone who forgot the flag. `--unsigned` leaves cosign out for the tests of the rules below the signature, and the gate's last line says so. With `--live` the gate also asks GitHub for the run's record and the artifact's digest.
6. **Nothing is signed that the gate has not passed**, and a pack's own signature is keyless, as this repository's workflow at its ref.

## What was measured, 2026-11-11

- GitHub answers an anonymous request for a run's record, for the list of a workflow's runs and for an artifact's record with its sha256. It answers 401 for the artifact's bytes.
- This repository's own workflow token may download them, though the artifact is another repository's: run 43112673693 built and signed packs for one GKE run and two AKS runs that way, before the flagship kept anything. A reader with no account cannot, and an artifact is gone after 90 days, so the token was never going to be enough.
- The flagship's branch held 43 records that day. All seven runs committed here as fixtures were read from it with no token, each record verified by cosign for the one identity; the same record is refused under the identity of `aks.yml`, and with one space added.

## Consequences

- A reader checks a pack with two commands and no account, and the check does not expire with GitHub's artifact.
- The record is signed after the run, by another workflow of the same repository, from GitHub's record of the run. The cloud job does not sign its own results.
- The index can still leave a run out, or name an older attempt of a run. The first gives no pack. The second is refused by `--live`, which asks GitHub for the run's attempt, and every pack built from a run read now is judged with it.
- A run the flagship's branch holds no record of gets no pack. On 2026-11-11 that was one run by hand, 43101489006, whose artifact held a scratch file the flagship's rule refuses.
- Sigstore's trust root is fetched to verify a signature, so reading a run and the gate need the network. A fetch that fails is tried again; a signature that does not verify is not.

## Alternatives

- **Read the artifact through GitHub's API and compare it with GitHub's digest.** This is what the first version did, and it worked. It rests on an account, on the 90 days, and on this repository's word afterwards.
- **Each cloud job signs its own results.** The strongest chain. It changes three workflows that create billed resources, and it is the flagship's to decide.
- **A token stored here to read the artifacts.** A long-lived secret in a repository whose point is that it holds none.
- **Trust the pack's findings.** Then the pack is a spreadsheet with a signature on it.

## How to explain this to a customer

Inside each pack is the file the cloud run itself uploaded, and a short record of that run signed by the repository that ran it. You can check that signature yourself with a free tool, and the file's fingerprint against the record. The check that judges a pack does not read its conclusions: it works them out again from that file and compares.
