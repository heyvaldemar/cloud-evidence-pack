# 4. A leg that is missing is reported as missing

- Status: accepted
- Date: 2026-11-11

## Context

Three clouds, three schedules, three accounts with their own budgets. A scheduled run can fail: two of AWS's three did, on 2026-10-29 and 2026-11-05. And a schedule can stop: the Azure credit ends on 2026-11-29, and whether that leg goes on is the maintainer's decision. A reader has to be able to tell a week that failed from a cloud that is no longer run, and neither may look like a pass.

## Decision

`scripts/index.py` lists every scheduled run of each cloud's workflow and keeps three outcomes apart:

- **pack**: the run passed and its pack passed the gate;
- **run with no pack**: the run failed, or it passed and its evidence was refused. A failure of that week, listed with the run;
- **missing**, for a cloud as a whole: no scheduled run in the last 10 days, a week and room for a late start, or none at all. The leg is reported as missing since its last run.

A missing leg fails nothing, and the other clouds' packs are built and signed as usual. A run that exists and has no pack is never reported as missing. `scripts/packs.sh` exits 1 only when a run that passed could not be made into a pack.

One pack per run, never one for all clouds. The count of packs in a row is kept per cloud, and a cloud's packs are called weekly only after two scheduled packs in a row.

## Consequences

- If Azure stops, the index says "missing: no scheduled run since" and the date, and AWS and Google Cloud go on.
- A failed week stays on the page: a failed run gets no pack, and the index links it.
- The index needs the clock, so it is not part of a pack. A pack is the same bytes whenever it is built.

## Alternatives

- **One pack for all three clouds.** One file to sign, and a missing or red leg makes the whole pack late or empty.
- **Fail when a cloud has no recent run.** It would turn a decision about an account into a red check on every other cloud.
- **Say nothing of a cloud with no run.** Then a leg that stopped looks like a leg that never was.

## How to explain this to a customer

For each cloud you see every scheduled run and what became of it. A week that failed is listed as failed. A cloud we stopped running is listed as stopped, with the date. Neither is dressed up as a pass.
