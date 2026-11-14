# Security policy

## Supported versions

| Version | Supported |
|---|---|
| The latest release | yes |
| `main` | yes |
| Older releases | no |

## Reporting a vulnerability

Report privately through GitHub: [**Security → Report a vulnerability**](https://github.com/heyvaldemar/cloud-evidence-pack/security/advisories/new) on this repository. Email to connect@valdemar.ai also works. The process is described at [heyvaldemar.com/security](https://heyvaldemar.com/security/).

You can expect an acknowledgment within 7 days. There is no bounty program; valid, responsibly disclosed reports are credited in the changelog. Please do not open public issues for security reports.

## What this repository is

A reference, not a hosted service. It builds evidence from another repository's scheduled cloud runs (heyvaldemar/kubernetes-air-gapped-ai-agent), and a vulnerability report here is most likely about the evidence itself: a way to make the gate pass while a control's lines are missing or failed, a way to build a pack from a run that was not a scheduled run on `main`, a signed document that does not say what the run's file says, or a verification step in the README that accepts something it should refuse. A weakness in the flagship's boundary or policies belongs to that repository's security policy.

The files under `tests/fixtures` are copies of real runs' public artifacts. The plants in `scripts/plant.py` break copies of them on purpose.

## Supply chain

- The flagship's page of controls is read from its signed release only after cosign and slsa-verifier verify it (`flagship.lock`).
- NIST's catalog, the command-line tools and compliance-trestle are pinned by sha256 (`catalogs.lock`, `tools.lock`, `requirements.lock`).
- A run is taken only with the record the flagship's workflow signed, verified by cosign for one exact identity, and its artifact only when its sha256 is the one that record names.
- Actions are pinned by commit SHA and moved by Dependabot.

## Credentials

None stored. Runs are read from the flagship's public branch with no token, and this repository's signatures are keyless, from the workflow's own OIDC identity.
