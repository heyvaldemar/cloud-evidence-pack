# Evidence pack: Google Cloud, scheduled run 43414580093

[Run 43414580093](https://github.com/heyvaldemar/kubernetes-air-gapped-ai-agent/actions/runs/43414580093) of `.github/workflows/gke.yml`, started by the schedule on 2026-11-13, on `main` at `bc583c1`: a private GKE cluster in a VPC made without its route to the internet.

8 of 8 mapped controls satisfied in this run. Its results hold 99 lines, 0 of them failed.

This shows what one scheduled run did. It does not say that any system meets a framework, and each control below says what it leaves out.

| Control | In this run | Violations tried and refused | Lines beside them that had to hold |
|---|---|---|---|
| SC-7 Boundary Protection | satisfied | 13 | 6 |
| SC-7(5) Deny by Default, Allow by Exception | satisfied | 13 | 5 |
| AC-4 Information Flow Enforcement | satisfied | 1 | 4 |
| SI-7 Software, Firmware, and Information Integrity | satisfied | 2 | 2 |
| SR-4 Provenance | satisfied | 1 | 1 |
| SR-11 Component Authenticity | satisfied | 6 | 2 |
| AC-6 Least Privilege | satisfied | 5 | 6 |
| IA-9 Service Identification and Authentication | satisfied | 7 | 8 |

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

- control: a pod starts from this run's registry, through restricted.googleapis.com, by digest (us-central1-docker.pkg.dev/valdemar-platform-validation/airgap-43414580093/docker.io/library/busybox@sha256:a7dbc319b1438115a207e11930dc4bb3e643dcb3ec0bdd694bb36cd8fad289ec)
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

- control: a pod starts from this run's registry, through restricted.googleapis.com, by digest (us-central1-docker.pkg.dev/valdemar-platform-validation/airgap-43414580093/docker.io/library/busybox@sha256:a7dbc319b1438115a207e11930dc4bb3e643dcb3ec0bdd694bb36cd8fad289ec)
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
- it holds exactly what the bundle carried (26 tags, by digest)

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
- volume-elsewhere: refused (only from us-central1-docker.pkg.dev/valdemar-platform-validation/airgap-43414580093/models)
- image-not-carried: refused (one the bundle carried)
- image-by-tag: refused (named by digest)
- a bundle changed by one byte is refused, and loads nothing

Beside it, what had to hold, so a refusal is not the environment refusing everything:

- model-signed: admitted
- every pod outside the node image's namespaces runs images the bundle carried (12 pods, 134 digests)

What this leaves out: Checked against a key, with no certificate and no transparency log. Part (b), reporting a counterfeit to anyone, is a process and nothing here does it. The images of the cloud's own node are exempt.

Related in ISO/IEC 27001:2022: nothing. This is NIST's own crosswalk from SP 800-53 Rev. 5 (OLIR informative reference 155, version 1.0.0, posted 2023-11-13), a relation between two documents and not a finding.

## AC-6 Least Privilege: satisfied

The violation tried in this run, and refused. Each line is the run's own, word for word:

- Vault refuses a login by the agent's service account, for Vault's audience (HTTP 403)
- Vault refuses a login by another service account in the MCP server's namespace (HTTP 403)
- Vault refuses a login by the MCP server's own token for the Kubernetes API (HTTP 403)
- an agent pod cannot connect to Vault
- a delete with a valid credential: 403, no role issues records:delete, and the record is still there

Beside it, what had to hold, so a refusal is not the environment refusing everything:

- control: Vault takes the MCP server's token for its audience
- control: an agent pod connects to the MCP server
- control: acting for Dana, the MCP server reads C1001 from the records service with Vault's credential
- Vault's credential: RS256, its issuer, audience records-api, scope records:read outbox:send, for mcp/mcp-server
- the credential lives 60 s, at most the records service's limit of 60 s
- Vault's audit names the service account of every credential it issued: 12, all to mcp/mcp-server

What this leaves out: The records credential alone. The agent's own two tokens, the Kubernetes API token refused at the gateway and the rights of the person the agent acts for are tried in the flagship's daily runs on kind, not in a cloud run; of the person's rights a cloud run holds the evals' count, which this mapping does not name. Quotas and token budgets at the gateway are per agent, not per person (the flagship's gap 1). Scope is by tool and customer, not by field.

Related in ISO/IEC 27001:2022: A.5.15, A.8.2, A.8.18. This is NIST's own crosswalk from SP 800-53 Rev. 5 (OLIR informative reference 155, version 1.0.0, posted 2023-11-13), a relation between two documents and not a finding.

## IA-9 Service Identification and Authentication: satisfied

The violation tried in this run, and refused. Each line is the run's own, word for word:

- no credential: 401
- a random key, the old kind of credential: 401
- the cluster's own token for the audience records-api: 401
- a credential for another audience, signed by Vault's own key: 401
- a credential that lives longer than 60 s, though Vault issued it: 401
- the first credential, once expired: 401
- Vault refuses a login by the MCP server's own token for the Kubernetes API (HTTP 403)

Beside it, what had to hold, so a refusal is not the environment refusing everything:

- control: the records service takes the credential for GET /records/C1001
- control: Vault takes the MCP server's token for its audience
- any service account gets a token for the audience records-api from the cluster: the agent's did
- plant: Vault issued a credential for the audience reports-api, signed by the records key
- plant: with Vault's TTL raised, it issued a credential for 3600 s
- the TTL put back: a new credential lives 60 s and is taken
- the records service logs who called: mcp/mcp-server
- the records service's log gives each reason: expired, lives longer than 60 s, no credential, no scope records:delete, not a JWT, signature not by Vault's key, wrong audience

What this leaves out: The records service and Vault alone. The gateway's check of the agent's token, and the MCP server's check of it with TokenReview, are tried in the flagship's daily runs on kind, not in a cloud run, and no check sends the MCP server a missing or wrong token. Services are identified; people are not (the flagship's gap 1).

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

The second answer is `5b8ce7e0776305f70272cafec764325fd98b0ae3961eab6ad479f571253b8a5b`, the value `record.json` gives as `artifact.sha256`. The record also says who started the run: `schedule`, on `main`, by `.github/workflows/gke.yml`, `success`.

Until GitHub drops the artifact on 2027-02-11, GitHub gives the same digest, to anyone:

```sh
curl -s https://api.github.com/repos/heyvaldemar/kubernetes-air-gapped-ai-agent/actions/artifacts/14034260067 | grep '"digest"'
```
