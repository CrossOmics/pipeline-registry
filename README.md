# CrossOmics community pipeline registry

Each file in `pipelines/` describes one original pipeline — a tool such as STAR (`kind: tool`) or an
end-to-end workflow such as nf-core/rnaseq (`kind: workflow`) — and every registered version of it:
its upstream releases (`kind: original`) and the community optimizations built on them
(`kind: optimization`). Gardener reads the published `index.json`
(https://crossomics.github.io/pipeline-registry/index.json); the weekly risk ranking is at
https://crossomics.github.io/pipeline-registry/ranking/.

## Adding a pipeline or a version

The easiest way is Gardener's Community › Register tab: it fills in the form, checks it, and opens
the pull request for you with your GitHub account. To do it by hand:

1. Add `pipelines/cp_<name>.yaml` for a new original, or append a version to the end of an existing
   file's `versions`. Copy the shape of an existing file; `schema/pipeline.schema.json` lists every field.
2. Version ids (`cv_...`) are unique across the registry. `parent` names a version **in the same file**;
   exactly one version per file has `parent: null`, and it is an `original`. An original builds only on
   an original; an optimization can build on either.
3. An optimization needs `improvement` (what changed), and may add `test_dataset`
   (`accession` or `url`, plus `description`) and `improvement_effect` (`summary`, `metrics`).
4. Merged entries are permanent. Never delete a version or change its `repo`, `commit`, `parent` or `kind`;
   set `withdrawn: true` instead. To rename a pipeline, reduce the old file to
   `{schema_version: 1, id: <old>, moved_to: <new>}` and move its versions, ids unchanged.
5. Files are kept in one canonical layout (fixed key order, no comments). Format and check locally:

   ```bash
   uv sync
   uv run python -m registry_tools fmt
   uv run pytest -q
   uv run python -m registry_tools validate
   ```

Adding a vocabulary value: edit `schema/vocab.yaml`, run `uv run python -m registry_tools gen-schema`,
commit both.

## Automation

- `validate.yml` (pull requests): rules R1-R13, including the append-only rule against the base branch.
- `build.yml` (push to main): builds `index.json` and the ranking page with the last collected metrics
  and deploys Pages.
- `collect.yml` (Mondays 03:00 UTC, or by hand): collects GitHub activity and citations
  (OpenAlex, then Semantic Scholar), commits them to the `data` branch, rebuilds and deploys.
