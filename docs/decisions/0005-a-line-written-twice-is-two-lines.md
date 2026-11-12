# 5. A line a run writes twice is two lines, and lines written together are counted together

- Status: accepted
- Date: 2026-11-12

## Context

The mapping counts lines. Each check says how many of a run's lines must match it, cloud by cloud, so a line that is lost or renamed upstream is noticed even when another still matches ([decision 3](0003-the-mapping-rests-on-the-flagships-own-page.md)).

The scheduled AWS run of 2026-11-12, [43199517532](https://github.com/heyvaldemar/kubernetes-air-gapped-ai-agent/actions/runs/43199517532), is the first that passed since the flagship put a GPU node and a larger model into its AWS workflow. With a GPU, that workflow takes the agent through `scripts/evals.sh` twice, and the evals write three of AC-4's lines each time: no email delivered outside the domain, the harness's own email arrived, every model request went through the gateway. Two of the three are the same words both times.

The pack of that run passed the gate, and 3 of the 58 plants for AWS were not caught on it: `renamed:outside-email`, `renamed:control-email` and `renamed:gateway-every-request`. Each renames one line. The check asked for one, and the line of the other time through the evals still matched.

The same run showed a second thing. The builder told lines apart by their words, so a line written twice was one observation. The summary listed it once and counted 5 lines beside AC-4's refusal, and the finding next to it counted 7.

A fixed number does not fit. With no GPU the same workflow writes the three lines once. So did the AWS run of 2026-10-22, from before the larger model, and so does Google Cloud's. Nothing is missing from those runs.

## Decision

1. **Lines written together are counted together.** `written_together` in `mapping/controls.yaml` names checks whose lines the flagship writes side by side, once each time it does the same thing in a run. Each must have as many lines as the others. A check with fewer is not satisfied, and the reason names the check that has more. How many times is the run's own affair.
2. **A line is a line each time the run wrote it.** The builder keeps every occurrence: an observation of its own in the assessment results, the second marked `occurrence: 2`, a line of its own in the summary, and one count in every place. Observations of lines written once keep the UUIDs they had.
3. **That run is a committed copy**, `tests/fixtures/runs/aws-43199517532`, so every plant is run on a run that writes lines twice.

## Consequences

- A line lost one of the two times leaves AC-4 not satisfied, with the reason. On run 43199517532 the plants are 58 of 58.
- A run that drops a whole pass through the evals, all three lines at once, is satisfied on the pass that is left. That is what an AWS run with no GPU is. The summary lists every line a control rests on, so a reader sees one pass or two.
- The rule covers the checks it names. Another check the flagship starts writing more than once is found the way this one was: a plant missed on a committed run.
- The mapping is 1.0.1. A pack built with 1.0.0 is checked with the source of its own release: the gate builds the documents again and fails a pack whose mapping is not the one in the source it runs from ([decision 2](0002-the-file-is-the-runs-and-the-gate-asks-again.md)).

## Alternatives

- **Ask for two lines on AWS.** One number in `at_least`, and an AWS run with no GPU would be refused though nothing is missing from it. So would the run of 2026-10-22.
- **Have the plant rename every line that matches.** All 58 would be caught and the gate would be no better. The plant would stop showing that one lost line is noticed.
- **Keep one observation for the same words.** Fewer observations, and a pack that says less than the run's own file: 121 lines there, two of them folded away here.

## How to explain this to a customer

When a run does a thing twice, the evidence has to be there twice. If a line is missing the second time, the first does not cover for it, and the pack says the control is not satisfied. A pack also lists a line as many times as the run wrote it, so the counts you read are the counts in the run's own file.
