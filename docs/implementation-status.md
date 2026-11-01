# Community registry implementation status

Implementation branch: `codex/community-registry`, pushed with explicit owner
authorization. Draft [PR #1](https://github.com/CrossOmics/pipeline-registry/pull/1)
targets `main`. Repository settings and Pages deployment remain unchanged.

Tasks 1–11 are implemented. Task 12 has 25 real Original pipeline files,
verified release commits and DOI evidence, STAR upstream release history, and
BWA-mem2 under its evidenced BWA 0.7.17 baseline. The latest BWA release remains
a separate Original version. See `seed-evidence.json` for sources.

The real Gardener package supplied by the contributor has been fetched with
Gardener's existing OCI client: its tag resolves to the supplied manifest digest,
and config/provenance digests verify. It remains a candidate until its source
GitHub repository, 40-character commit and version parent are confirmed. No
synthetic source revision, baseline or benchmark result has been inserted. A real
second-level optimization and successful authenticated application submission PR
remain acceptance items. Native Gardener Import Only, save/reload and description
persistence passed in an isolated development window. See `package-candidate.md`.

## Final review and verification

A fresh reviewer found five Important issues. All were reproduced before fixes:
22 focused regression cases failed, then all passed after the fixes; the complete
suite is 99 passing tests. The fixes reject non-finite metric numbers and invalid
JSON output, isolate malformed API responses to their pipeline, correct unsupported
seed lineage, stop deployment when metrics cannot be fetched, and bind collected
activity to the normalized primary repository. Existing metrics without this
identity are unavailable until recollected.

Formatting, generated schema consistency, all 13 registry rules and index/page
builds passed locally. The final live collection succeeded for 25/25 pipelines,
with no stale entries, at `2026-11-01T02:49:14Z`. The generated index has 20 ranked
pipelines and 5 explicitly excluded entries. Gardener's strict `RegistryIndex`
model accepts the full index, its SHA-256 matches the companion file, and both
canonical YAML goldens match Gardener byte for byte. The local browser smoke check
confirmed the real rankings, last GitHub update, all three citation-year columns
including YTD, exclusions and method explanation. The GitHub Actions PR workflow also passed against the actual `main` base: 99
tests and all 25 pipeline files, on commit `cddb15955268635e7a5b2f0ab4722b56449081ed`
([run 41323950223](https://github.com/CrossOmics/pipeline-registry/actions/runs/41323950223)).
Pages configuration, branch protection and live publication remain pending.

## Decisions and costs

- Resolve the moved RAPIDS repository to `scverse/rapids-singlecell`. Cost if
  wrong: the contributor may prefer an older named release.
- Replace the plan's latest-Original/latest-optimization pairing with evidenced
  version ancestry. BWA-mem2 names BWA 0.7.17 as its baseline; RAPIDS only declares
  Scanpy compatibility (`>=1.10.0`), so its candidate edge is deferred. Cost:
  one fewer seeded optimization until its exact baseline is confirmed.
- Keep the user package unregistered pending source and parent confirmation.
  Cost: the package and second-level lineage acceptance items remain incomplete.
- Keep publication and remote protection pending explicit authorization. Cost:
  live workflow and production behavior have not yet been proven.
- Use live API collection and official repository/DOI metadata as evidence, not
  a guarantee of future source availability or exhaustive scientific provenance.
  Cost: source outages and additional attribution corrections remain possible.
- Verify the shared index contract and native Electron import/save locally;
  authenticated application PR submission remains a rollout check. Cost: the
  remaining remote integration can still reveal runtime issues.
- Retain the specified 100-release and 10,000-citation caps. Cost: very large
  repositories/papers may have truncated counts.

Deferred minor: malformed YAML field/container shapes can make append-only (`--base`)
validation emit a traceback instead of the existing R1 diagnostics. The check still
fails, so invalid entries cannot pass CI.

## Publication scope awaiting approval

The owner authorized pushing the feature branch and creating a draft PR to run CI.
That step is complete; `main` still has only the initial README. Merge/publication
was not authorized. After approval, publication includes merging this PR into
`main`, pushing the verified metric snapshot to a new `data` branch,
enabling GitHub Pages from Actions, running collection and verifying the live
index hash/ranking, and requiring the `validate` check plus one approving review
on `main`. Check the current remote before pushing; preserve any intervening work.

The contact email variable is optional and remains unset until the owner supplies
an address. The optional Semantic Scholar key also remains unset; if wanted, the
owner enters it directly with `gh secret set`. No credentials are stored here.
The pending package is excluded from this initial publication scope.

## Prepared local artifacts

- Verified metric snapshot: local branch `codex/community-registry-data`, commit
  `8b4f9268201ad4763240bc200b021ccf9e7ac125`, with `metrics/latest.json` and dated history.
- Generated Pages artifacts are in ignored `dist/`; the public URLs in the README
  are intended destinations and are not claimed to be deployed.
- All repository credentials used for read-only collection stayed in process
  memory. No token or optional API key is part of either branch.

## BioCode Commons destination

The ranking page, landing page and README now link to
[BioCode Commons](https://github.com/BioCode-Commons), where the team will share
new versions of pipelines needing maintenance, starting with STAR and MAFFT.
This adds a destination link rather than registering unverified version ancestry.
The generated ranking link was checked in a local browser; all 99 registry tests
pass. This content change has not been deployed.

## Authorized draft PR — 2026-11-01

Draft PR #1 is open and its validation workflow passed. This proves branch push,
PR creation and GitHub CI, not Community Register submission through Gardener.
No merge, `data` branch push, Pages activation or protection change was made.
