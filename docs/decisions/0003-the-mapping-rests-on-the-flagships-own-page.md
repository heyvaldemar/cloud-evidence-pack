# 3. The mapping rests on the flagship's own page, and every control is shown a violation

- Status: accepted
- Date: 2026-11-11

## Context

The flagship already maps SP 800-53 by hand: `docs/compliance.md` has twelve rows, each with the check that shows it and what it leaves out. A second mapping made here on its own could say more than that page, or something else. kubernetes-oscal-evidence met this in its first week and wrote a record about it.

A check line that passes can pass for a bad reason: the probe was dead, the resolver was down, the registry was unreachable for everyone.

## Decision

A control is in `mapping/controls.yaml` only when three things are true:

1. the flagship's page has the row, read from the release `flagship.lock` pins;
2. the check that row names writes a line into the cloud run's results;
3. the run shows a violation that check refused, beside something that had to succeed.

Each check is typed: a refusal, a control that had to succeed, or a gate held to a number. A control with no refusal among its checks on a cloud, or with refusals alone, is refused by `scripts/component.py` and never satisfied by `scripts/pack.py`. A line is named to its end, and counted cloud by cloud. A planted pod's line must carry the words the pod's own file expects, at the run's commit.

That gives six controls from the runs that exist: SC-7 and SC-7(5) on three clouds; AC-4, SI-7, SR-4 and SR-11 on AWS and Google Cloud. AU-2 and CM-7 wait for a violation shown in a scheduled run; AC-6 and IA-9 for the Vault checks in one; SC-7(10), SC-8, AU-9 and RA-5 have nothing in a cloud run.

Another framework is a column of related criteria, never a finding, and only from the framework owner's or NIST's own crosswalk, fetched and pinned by sha256.

## Consequences

- The pack cannot say more than the page. When a run shows the page wrong, the page is corrected first.
- The flagship's page says CM-14 is not mapped, because the model is verified against a public key and not a certificate, and puts the signature plants under SR-11. kubernetes-oscal-evidence maps CM-14 and CM-7(5), and rests SR-11 on the carried-images policy alone. This repository follows the page. The two should agree, and which moves is not decided here.
- A line renamed upstream turns its control not satisfied until the mapping follows. That is the intended failure.
- The first full pass of the plants missed eight, all in the mapping: two patterns that ended in "anything", and two checks that asked for one line where two are written.

## Alternatives

- **Map every SP 800-53 control a check seems to fit.** More rows, each of them an opinion.
- **Patterns that match loosely, so a rename upstream does not break a pack.** Then a line can change its meaning and stay evidence.
- **SOC 2 and ISO/IEC 27001 as findings.** A run cannot show what an organisation's own assessors found, and nothing here says it does.

## How to explain this to a customer

The controls in a pack are the ones the reference's own page already lists, and only those a cloud run can show. For each, the pack names the attack the run tried and was refused, and the ordinary thing that had to work at the same moment, so a refusal is not just a broken network.
