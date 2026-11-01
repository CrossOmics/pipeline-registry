# Gardener package candidate

Verified anonymously: the tag resolves to the supplied manifest digest, and the
manifest/config/provenance are digest verified by Gardener's existing OCI client.

- Reference: `ghcr.io/crossomics/gardener-pipelines:star-stringtie-standard-vs-opti2x-v5`
- Digest: `sha256:867a3a52434bbde458c931832420baf78cadd78fa3a5a679a7394ed9093e4a3b`
- Workflow: STAR/StringTie standard vs Opti2x, including index, alignment, assembly and comparison nodes.
- Bound public reads: `SRR315336`; reference assets: GENCODE human release 47.

Pending contributor confirmation: source GitHub repository and 40-hex commit,
and whether this is an independent workflow or an optimization of a registered
version. It is deliberately not assigned a synthetic source commit or parent.
No FASTQs, references, environment layers or container images were downloaded.
