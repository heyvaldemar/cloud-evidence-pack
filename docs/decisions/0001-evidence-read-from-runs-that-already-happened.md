# 1. Evidence read from the cloud runs that already happened, in a repository of its own

- Status: accepted
- Date: 2026-11-11

## Context

[kubernetes-oscal-evidence](https://github.com/heyvaldemar/kubernetes-oscal-evidence) turns the flagship's admission policies into signed OSCAL assessment results, on kind, and its README says what that leaves out: the flagship's boundary is not reproduced there. The flagship itself runs on AWS, Google Cloud and Azure on a schedule, and each run uploads what it checked: `e2e-results-<cloud>`, kept 90 days. On 2026-11-11 that was 56 lines for the last scheduled AWS run that passed (39744285464), 63 for Google Cloud (42206932411) and 21 for Azure (42809539539), which makes the boundary alone.

No cloud run keeps a report from Kyverno. Making the flagship report on a cloud would mean the three settings kubernetes-oscal-evidence needed on kind, which changes what the flagship installs on the clouds it is proven on.

## Decision

A repository of its own. It reads the record and the artifact of scheduled runs that already happened, and builds one pack per run from the run's own check lines, with compliance-trestle's models. It has no cluster and no cloud account, and it starts no workflow in the flagship, ever.

It is not a leg of kubernetes-oscal-evidence, for four reasons:

1. That repository's claim, its `AGENTS.md` and its first decision record are about one run on kind, of admission policies, mapped only onto rows of the published control-to-test matrix. The matrix has no row a network boundary control lands on.
2. The chain of evidence is another one. There the run that signs is the run that made the evidence. Here the evidence is another repository's run, and what must be shown is whose file it is.
3. A red week on a cloud must not sit beside that repository's own record. AWS had no GPU capacity on 2026-11-05 and its scheduled run failed.
4. A pack appears for each scheduled cloud run that passes, whether or not the code moved. There a release is the code and the evidence of a run on the tag.

## Consequences

- The evidence is from clusters the flagship's schedule made and destroyed on three clouds, and it is thinner than the kind evidence in one way: no policy engine's report, no C2P verdict. The README says so and points at kubernetes-oscal-evidence for that half.
- One more repository to keep under the fleet's standard, which has no kind for a repository with no cluster.
- Two repositories now map the same policies. Record 3 says which page both must agree with.

## Alternatives

- **A leg inside kubernetes-oscal-evidence.** No new repository, and one place for OSCAL. It rewrites that repository's claim and puts two evidence chains, two gates and two cadences behind one name.
- **Inside the flagship, from a `workflow_run` trigger.** Closest to the source, and the signature would be the flagship's own. It adds compliance-trestle, NIST's catalog and a second evidence workflow to a repository with 24 decision records and three cloud legs, and a fault in the builder would show red on the flagship's main.
- **Collect PolicyReports on the clouds and run C2P.** A second opinion from OSCAL Compass, at the price of changing what the flagship installs there. Worth its own decision later.

## How to explain this to a customer

Every week a scheduled run builds the reference on each of three real cloud accounts, tries it from inside and destroys it. Which weeks passed is what the index shows. This repository takes the record of each of those runs straight from GitHub and turns it into a standard document. It runs nothing in a cloud itself: it reads what already happened.
