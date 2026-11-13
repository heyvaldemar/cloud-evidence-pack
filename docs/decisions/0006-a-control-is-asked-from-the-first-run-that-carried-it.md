# 6. A control is asked of a run from the first scheduled run that carried its lines

- Status: accepted
- Date: 2026-11-13

## Context

Until now every control was mapped on a cloud from the first run read there. A run of that cloud either had the control's lines or was missing them, and a missing line left the control not satisfied ([decision 3](0003-the-mapping-rests-on-the-flagships-own-page.md)).

The flagship grows. Its Vault checks, `tests/e2e/vault.sh`, came into its AWS and Google Cloud workflows in November 2026: who may get the records credential, what it allows, and what the records service refuses as a caller's identity. They are what the AC-6 and IA-9 rows of its `docs/compliance.md` rest on in a cloud run. The scheduled AWS run of 2026-11-12, [43199517532](https://github.com/heyvaldemar/kubernetes-air-gapped-ai-agent/actions/runs/43199517532), is the first scheduled cloud run that passed with them: 35 lines of its 121.

The scheduled AWS run of 2026-10-22 has none of those lines. Nothing was lost from it: the flagship had no Vault then. Mapped the old way, a pack of that run would say AC-6 and IA-9 are not satisfied, and the gate would refuse a pack of a run in which nothing failed.

The opposite mistake is worse. If a control were asked only where its lines are found, a later run that lost every one of them would read as a run too early to be asked, and the loss would pass in silence.

## Decision

1. **A control may name its first run.** `since` in `mapping/controls.yaml` gives, cloud by cloud, the id of the first scheduled run whose results carried the control's lines. A control without it is asked of every run of its clouds, as before.
2. **Every run from that one on is asked.** The comparison is of run ids, which GitHub gives out as runs start and which the flagship's signed record carries. A run at or after the first is judged as any control is: a line it lacks leaves the control not satisfied.
3. **An earlier run is not asked, and its pack says so.** It has no finding for the control and none of the control's lines is looked for in it. The summary and the assessment results name the control as not asked of that run and name the first run, and `verdict.json` lists it under `not_asked`. The gate requires exactly the findings the run is asked for: one for a control the run is too early for fails it, as a missing one does later.
4. **The first run is a committed copy.** A static check requires `tests/fixtures/runs/<cloud>-<run id>` for every `since`, with the control satisfied in it. A `since` cannot name a run nobody can check, and it cannot be moved to a run that did not carry the lines.
5. **AC-6 and IA-9 are mapped on AWS, since run 43199517532.** Twenty-four checks, each one line of that run: for AC-6 five refusals beside six lines that had to hold, for IA-9 seven beside eight. The two share one refused login and the login that had to work.

## Consequences

- The pack of AWS run 43199517532 has eight findings, and the pack of the run of 2026-10-22 has six and says two were not asked of it. Both pass the gate.
- A scheduled AWS run after 2026-11-12 with the Vault lines gone is not satisfied for both controls. The plants show it: on the committed copy of 43199517532 every refusal of each control is taken away in turn, then everything beside them, then each line is renamed.
- Plants are listed for a run, not for a cloud: a run gets the plants of the controls it is asked for. `python3 scripts/plant.py all DIR` takes the run's directory.
- A pack kept on the branch `packs` was judged by the mapping of the day it was built. The pack of 43199517532 built on 2026-11-13 by mapping 1.0.1 has six findings, and one built by mapping 1.1.0 has eight. The index now names the mapping beside each pack's count.
- Google Cloud's workflow runs the same script. AC-6 and IA-9 are named there, with their own `since`, once a scheduled run there has passed with the lines. Until then a Google Cloud pack has six findings and lists the two under controls mapped on other clouds.
- The mapping is 1.1.0.

## Google Cloud, later the same day

The scheduled Google Cloud run of 2026-11-13, [43414580093](https://github.com/heyvaldemar/kubernetes-air-gapped-ai-agent/actions/runs/43414580093), passed with the Vault lines: 36 of its 99, none of them in the run of 2026-11-06. Mapping 1.2.0 names AC-6 and IA-9 on Google Cloud, with that run as their `since` there. The rule did not change: the same twenty-four checks, a committed copy of the run with both controls satisfied in it, and every plant run on it before a pack of it was released.

The second cloud brought out one thing the rule already said and no test had asked: a cloud's first run is its own. AWS had the lines a day before Google Cloud did. A Google Cloud run started between the two is too early for Google Cloud, whatever AWS carried by then, and a mutation that takes the earliest first run of any cloud for every cloud's is now caught by a test.

## Alternatives

- **Ask every AWS run for the two.** The run of 2026-10-22 would be a failure of something the flagship did not do yet. A leg that is missing is reported as missing ([decision 4](0004-a-leg-that-is-missing-is-reported-as-missing.md)), and a control a run is too early for is the same kind of thing.
- **Ask a run only when it has the lines.** No date and no id to maintain, and a run that lost all of them would be taken for an early one. This is the mistake the rule exists to prevent.
- **A date instead of a run.** A date says the same and points at nothing. A run id is in the signed record, and the run it names is here to be checked.
- **Read the flagship's workflow at the run's commit, and ask when it calls the script.** Closest to the truth, and it needs a second file fetched for every run and trust in how a workflow file is read. One id in the mapping, held to a committed run, is less to get wrong.

## How to explain this to a customer

A control is checked in every run from the day the system first did the thing, and the pack of an older run says "not asked" instead of "failed". From that day on there is no way back: a run that stops showing it is a run where the control is not satisfied.
