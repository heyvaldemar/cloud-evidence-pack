# Evidence pack: Azure, scheduled run 41626192017

[Run 41626192017](https://github.com/heyvaldemar/kubernetes-air-gapped-ai-agent/actions/runs/41626192017) of `.github/workflows/aks.yml`, started by the schedule on 2026-11-03, on `main` at `27ba3c8`: a network isolated AKS cluster; the boundary alone, with no agent on it.

2 of 2 mapped controls satisfied in this run. Its results hold 21 lines, 0 of them failed.

This shows what one scheduled run did. It does not say that any system meets a framework, and each control below says what it leaves out.

| Control | In this run | Violations tried and refused | Lines beside them that had to hold |
|---|---|---|---|
| SC-7 Boundary Protection | satisfied | 14 | 6 |
| SC-7(5) Deny by Default, Allow by Exception | satisfied | 14 | 5 |

## SC-7 Boundary Protection: satisfied

The violation tried in this run, and refused. Each line is the run's own, word for word:

- a pod opens no TCP to 1.1.1.1:443
- a pod opens no TCP to 8.8.8.8:53
- a pod opens no TCP to 151.101.0.81:443
- the node opens no TCP to 1.1.1.1:443
- the node opens no TCP to 8.8.8.8:53
- the node opens no TCP to 151.101.0.81:443
- a pod cannot resolve example.com (the resolver policy refuses every name but the registry's and the network's own)
- a pod cannot resolve example.org (the resolver policy refuses every name but the registry's and the network's own)
- the node cannot resolve example.com (the resolver policy refuses every name but the registry's and the network's own)
- the node cannot resolve example.org (the resolver policy refuses every name but the registry's and the network's own)
- a pod cannot ask a public resolver directly (8.8.8.8)
- the node cannot ask a public resolver directly (8.8.8.8)
- a pod opens no TCP to mcr.microsoft.com (150.171.69.10:443), where AKS's own images are published
- the node opens no TCP to mcr.microsoft.com (150.171.69.10:443), where AKS's own images are published

Beside it, what had to hold, so a refusal is not the environment refusing everything:

- control: a pod starts from this run's registry, through its private endpoint, by digest (airgap41626192017.azurecr.io/docker.io/library/busybox@sha256:bdf57e528e45e4433820e045b29b4597825a1c9e38353532d90a01445013f82e)
- control: a pod resolves the cluster's own services
- control: a pod resolves airgap41626192017.azurecr.io to 10.42.17.5, its private endpoint, from the network's own zone
- control: the node resolves airgap41626192017.azurecr.io to 10.42.17.5, its private endpoint, from the network's own zone
- control: a pod opens TCP to airgap41626192017.azurecr.io on 443, through its private endpoint
- control: the node opens TCP to airgap41626192017.azurecr.io on 443, through its private endpoint

What this leaves out: Control, not monitoring: an attempt to leave is refused, and nothing this run reads records it. IPv6 is not tried. The attempts are a pod's and the node's; the cloud's own control plane, and the runner's address that the cluster's API answers, are outside what is tried.

Related in ISO/IEC 27001:2022: A.5.14, A.8.16, A.8.20, A.8.22, A.8.23. This is NIST's own crosswalk from SP 800-53 Rev. 5 (OLIR informative reference 155, version 1.0.0, posted 2023-11-13), a relation between two documents and not a finding.

## SC-7(5) Deny by Default, Allow by Exception: satisfied

The violation tried in this run, and refused. Each line is the run's own, word for word:

- a pod opens no TCP to 1.1.1.1:443
- a pod opens no TCP to 8.8.8.8:53
- a pod opens no TCP to 151.101.0.81:443
- the node opens no TCP to 1.1.1.1:443
- the node opens no TCP to 8.8.8.8:53
- the node opens no TCP to 151.101.0.81:443
- a pod cannot resolve example.com (the resolver policy refuses every name but the registry's and the network's own)
- a pod cannot resolve example.org (the resolver policy refuses every name but the registry's and the network's own)
- the node cannot resolve example.com (the resolver policy refuses every name but the registry's and the network's own)
- the node cannot resolve example.org (the resolver policy refuses every name but the registry's and the network's own)
- a pod cannot ask a public resolver directly (8.8.8.8)
- the node cannot ask a public resolver directly (8.8.8.8)
- a pod opens no TCP to mcr.microsoft.com (150.171.69.10:443), where AKS's own images are published
- the node opens no TCP to mcr.microsoft.com (150.171.69.10:443), where AKS's own images are published

Beside it, what had to hold, so a refusal is not the environment refusing everything:

- control: a pod starts from this run's registry, through its private endpoint, by digest (airgap41626192017.azurecr.io/docker.io/library/busybox@sha256:bdf57e528e45e4433820e045b29b4597825a1c9e38353532d90a01445013f82e)
- control: a pod resolves airgap41626192017.azurecr.io to 10.42.17.5, its private endpoint, from the network's own zone
- control: the node resolves airgap41626192017.azurecr.io to 10.42.17.5, its private endpoint, from the network's own zone
- control: a pod opens TCP to airgap41626192017.azurecr.io on 443, through its private endpoint
- control: the node opens TCP to airgap41626192017.azurecr.io on 443, through its private endpoint

What this leaves out: The run checks that the exceptions answer, not that they are the only ones: the cloud's other private endpoints the node needs to join are not listed here one by one. Reviewing the exceptions is a person's work.

Related in ISO/IEC 27001:2022: nothing. This is NIST's own crosswalk from SP 800-53 Rev. 5 (OLIR informative reference 155, version 1.0.0, posted 2023-11-13), a relation between two documents and not a finding.

## Not in this pack

Mapped on other clouds and not here, because this cloud's run does not write their lines: AC-4 Information Flow Enforcement, SI-7 Software, Firmware, and Information Integrity, SR-4 Provenance, SR-11 Component Authenticity.

## The day a check failed

A check that has never failed proves little. On this cloud, by hand, with the resolver's policy left off, these failed:

- `pod-dns-outside`: [run 41007916564](https://github.com/heyvaldemar/kubernetes-air-gapped-ai-agent/actions/runs/41007916564)
- `node-dns-outside`: [run 41007916564](https://github.com/heyvaldemar/kubernetes-air-gapped-ai-agent/actions/runs/41007916564)

## Is the file inside the run's?

The repository that ran the cloud says so, and signed it. Its workflow wrote down the run's facts and the sha256 of the results the run uploaded, and signed that record on its main. Both are in this pack, and cosign checks the signature for one exact identity:

```sh
cosign verify-blob evidence/run/record.json --bundle evidence/run/record.json.sigstore.json \
  --certificate-identity https://github.com/heyvaldemar/kubernetes-air-gapped-ai-agent/.github/workflows/cloud-results.yml@refs/heads/main \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
sha256sum evidence/run/e2e-results-aks.zip
```

The second answer is `d06d9995caa696645759db0b861ac76b34892268666c89c32684aa7cb88c275b`, the value `record.json` gives as `artifact.sha256`. The record also says who started the run: `schedule`, on `main`, by `.github/workflows/aks.yml`, `success`.

Until GitHub drops the artifact on 2027-02-01, GitHub gives the same digest, to anyone:

```sh
curl -s https://api.github.com/repos/heyvaldemar/kubernetes-air-gapped-ai-agent/actions/artifacts/13226642523 | grep '"digest"'
```
