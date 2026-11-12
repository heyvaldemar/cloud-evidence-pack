# Evidence pack: Google Cloud, scheduled run 42206932411

[Run 42206932411](https://github.com/heyvaldemar/kubernetes-air-gapped-ai-agent/actions/runs/42206932411) of `.github/workflows/gke.yml`, started by the schedule on 2026-11-06, on `main` at `473fa4a`: a private GKE cluster in a VPC made without its route to the internet.

6 of 6 mapped controls satisfied in this run. Its results hold 63 lines, 0 of them failed.

This shows what one scheduled run did. It does not say that any system meets a framework, and each control below says what it leaves out.

| Control | In this run | Violations tried and refused | Lines beside them that had to hold |
|---|---|---|---|
| SC-7 Boundary Protection | satisfied | 13 | 6 |
| SC-7(5) Deny by Default, Allow by Exception | satisfied | 13 | 5 |
| AC-4 Information Flow Enforcement | satisfied | 1 | 4 |
| SI-7 Software, Firmware, and Information Integrity | satisfied | 2 | 2 |
| SR-4 Provenance | satisfied | 1 | 1 |
| SR-11 Component Authenticity | satisfied | 6 | 2 |

## SC-7 Boundary Protection: satisfied

The violation tried in this run, and refused. Each line is the run's own, word for word:

- a pod opens no TCP to 1.1.1.1:443
- a pod opens no TCP to 8.8.8.8:53
- a pod opens no TCP to 151.101.0.81:443
- the node opens no TCP to 1.1.1.1:443
- the node opens no TCP to 8.8.8.8:53
- the node opens no TCP to 151.101.0.81:443
- a pod cannot resolve example.com (the response policy refuses names outside Google's APIs)
- a pod cannot resolve example.org (the response policy refuses names outside Google's APIs)
- the node cannot resolve example.com (the response policy refuses names outside Google's APIs)
- the node cannot resolve example.org (the response policy refuses names outside Google's APIs)
- a pod cannot ask a public resolver directly (8.8.8.8)
- the node cannot ask a public resolver directly (8.8.8.8)
- a pod opens no TCP to private.googleapis.com (199.36.153.8:443), Google's other front door

Beside it, what had to hold, so a refusal is not the environment refusing everything:

- control: a pod starts from this run's registry, through restricted.googleapis.com, by digest (us-central1-docker.pkg.dev/valdemar-platform-validation/airgap-42206932411/docker.io/library/busybox@sha256:bdf57e528e45e4433820e045b29b4597825a1c9e38353532d90a01445013f82e)
- control: a pod resolves the cluster's own services
- control: a pod resolves us-central1-docker.pkg.dev to 199.36.153.4 199.36.153.5 199.36.153.6 199.36.153.7, restricted.googleapis.com, from the network's own zone
- control: the node resolves us-central1-docker.pkg.dev to 199.36.153.4 199.36.153.5 199.36.153.6 199.36.153.7, restricted.googleapis.com, from the network's own zone
- control: a pod opens TCP to us-central1-docker.pkg.dev on 443, through restricted.googleapis.com
- control: the node opens TCP to us-central1-docker.pkg.dev on 443, through restricted.googleapis.com

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
- a pod cannot resolve example.com (the response policy refuses names outside Google's APIs)
- a pod cannot resolve example.org (the response policy refuses names outside Google's APIs)
- the node cannot resolve example.com (the response policy refuses names outside Google's APIs)
- the node cannot resolve example.org (the response policy refuses names outside Google's APIs)
- a pod cannot ask a public resolver directly (8.8.8.8)
- the node cannot ask a public resolver directly (8.8.8.8)
- a pod opens no TCP to private.googleapis.com (199.36.153.8:443), Google's other front door

Beside it, what had to hold, so a refusal is not the environment refusing everything:

- control: a pod starts from this run's registry, through restricted.googleapis.com, by digest (us-central1-docker.pkg.dev/valdemar-platform-validation/airgap-42206932411/docker.io/library/busybox@sha256:bdf57e528e45e4433820e045b29b4597825a1c9e38353532d90a01445013f82e)
- control: a pod resolves us-central1-docker.pkg.dev to 199.36.153.4 199.36.153.5 199.36.153.6 199.36.153.7, restricted.googleapis.com, from the network's own zone
- control: the node resolves us-central1-docker.pkg.dev to 199.36.153.4 199.36.153.5 199.36.153.6 199.36.153.7, restricted.googleapis.com, from the network's own zone
- control: a pod opens TCP to us-central1-docker.pkg.dev on 443, through restricted.googleapis.com
- control: the node opens TCP to us-central1-docker.pkg.dev on 443, through restricted.googleapis.com

What this leaves out: The run checks that the exceptions answer, not that they are the only ones: the cloud's other private endpoints the node needs to join are not listed here one by one. Reviewing the exceptions is a person's work.

Related in ISO/IEC 27001:2022: nothing. This is NIST's own crosswalk from SP 800-53 Rev. 5 (OLIR informative reference 155, version 1.0.0, posted 2023-11-13), a relation between two documents and not a finding.

## AC-4 Information Flow Enforcement: satisfied

The violation tried in this run, and refused. Each line is the run's own, word for word:

- with the gateway's pod killed, the model server still cannot be reached around it

Beside it, what had to hold, so a refusal is not the environment refusing everything:

- control: the gateway answers for granite-4.0-1b (200)
- the harness's control email arrived through the MCP server: yes (control)
- emails delivered outside acme.example: 0 (gate: 0)
- every model request went through the gateway: 206 asked by the agent, 206 answered by the gateway

What this leaves out: The schema holds a domain, not a person: emails to colleagues nobody named are counted, not refused, and nothing reads what a body carries. In a run where the model never writes an outside address, the email gate shows the outcome and not a refusal; the refusal this control rests on here is the way around the gateway.

Related in ISO/IEC 27001:2022: A.5.14, A.8.22, A.8.23. This is NIST's own crosswalk from SP 800-53 Rev. 5 (OLIR informative reference 155, version 1.0.0, posted 2023-11-13), a relation between two documents and not a finding.

## SI-7 Software, Firmware, and Information Integrity: satisfied

The violation tried in this run, and refused. Each line is the run's own, word for word:

- a bundle changed by one byte is refused, and loads nothing
- model-by-tag: refused (by digest)

Beside it, what had to hold, so a refusal is not the environment refusing everything:

- the registry inside held nothing when the bundle was loaded
- it holds exactly what the bundle carried (25 tags, by digest)

What this leaves out: Checked on the way in. Nothing re-verifies what the registry stores between runs, and the cloud's node image arrives outside the bundle.

Related in ISO/IEC 27001:2022: nothing. This is NIST's own crosswalk from SP 800-53 Rev. 5 (OLIR informative reference 155, version 1.0.0, posted 2023-11-13), a relation between two documents and not a finding.

## SR-4 Provenance: satisfied

The violation tried in this run, and refused. Each line is the run's own, word for word:

- model-nobom: refused (model weights carry an AI-BOM signed with the operator's key)

Beside it, what had to hold, so a refusal is not the environment refusing everything:

- model-signed: admitted

What this leaves out: Admission checks that the record is there and signed, not that it is true of the source. Where the training data came from is not recorded. Container images get no provenance check here.

Related in ISO/IEC 27001:2022: A.5.21, A.8.30. This is NIST's own crosswalk from SP 800-53 Rev. 5 (OLIR informative reference 155, version 1.0.0, posted 2023-11-13), a relation between two documents and not a finding.

## SR-11 Component Authenticity: satisfied

The violation tried in this run, and refused. Each line is the run's own, word for word:

- model-unsigned: refused (signed with the operator's key)
- model-stranger: refused (signed with the operator's key)
- volume-elsewhere: refused (only from us-central1-docker.pkg.dev/valdemar-platform-validation/airgap-42206932411/models)
- image-not-carried: refused (one the bundle carried)
- image-by-tag: refused (named by digest)
- a bundle changed by one byte is refused, and loads nothing

Beside it, what had to hold, so a refusal is not the environment refusing everything:

- model-signed: admitted
- every pod outside the node image's namespaces runs images the bundle carried (11 pods, 130 digests)

What this leaves out: Checked against a key, with no certificate and no transparency log. Part (b), reporting a counterfeit to anyone, is a process and nothing here does it. The images of the cloud's own node are exempt.

Related in ISO/IEC 27001:2022: nothing. This is NIST's own crosswalk from SP 800-53 Rev. 5 (OLIR informative reference 155, version 1.0.0, posted 2023-11-13), a relation between two documents and not a finding.

## The day a check failed

A check that has never failed proves little. On this cloud, by hand, with the resolver's policy left off, these failed:

- `pod-dns-outside`: [run 40560466605](https://github.com/heyvaldemar/kubernetes-air-gapped-ai-agent/actions/runs/40560466605)
- `node-dns-outside`: [run 40560466605](https://github.com/heyvaldemar/kubernetes-air-gapped-ai-agent/actions/runs/40560466605)

## Is the file inside the run's?

The repository that ran the cloud says so, and signed it. Its workflow wrote down the run's facts and the sha256 of the results the run uploaded, and signed that record on its main. Both are in this pack, and cosign checks the signature for one exact identity:

```sh
cosign verify-blob evidence/run/record.json --bundle evidence/run/record.json.sigstore.json \
  --certificate-identity https://github.com/heyvaldemar/kubernetes-air-gapped-ai-agent/.github/workflows/cloud-results.yml@refs/heads/main \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
sha256sum evidence/run/e2e-results-gke.zip
```

The second answer is `3b531633dc710600e05c33dc373d2b65a5f514ec623abf7f002fd66b4900eb21`, the value `record.json` gives as `artifact.sha256`. The record also says who started the run: `schedule`, on `main`, by `.github/workflows/gke.yml`, `success`.

Until GitHub drops the artifact on 2027-02-04, GitHub gives the same digest, to anyone:

```sh
curl -s https://api.github.com/repos/heyvaldemar/kubernetes-air-gapped-ai-agent/actions/artifacts/13499425310 | grep '"digest"'
```
