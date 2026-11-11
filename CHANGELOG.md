# Changelog

## [Unreleased]

- Dex browser sign-in uses the public PKCE client and `/ui/signin/callback`, alongside the
  existing CLI device callback. Bootstrap configures a persistent state-signing secret through
  the existing secret source, a public UI URL, and shared Dex/UI ingress; Google keeps its
  existing Dex callback. Local test credentials stay in ignored mode-0600 storage.

- Add `SI_VIEWS` with the two `CREATE_VIEW` tasks: the customer support fact view over
  `dm.customer_support_fact` (active versions, ODS and SI_DM provenance kept apart, steward and upload,
  last committed window and freshness, rejected keys excluded) and the data metrics view over the audit
  tables cloned into `aud_mirror`; enable `Cloning` (`Scope: AUD`).
- Add the configuration CI: `validate.yml` (pull requests, no secrets, a local DuckDB warehouse via
  `ci/validate.sh`) and `deploy.yml` (push to `main`, self-hosted runner, reviewed `production`
  environment, one developer token), with `ci/PACKAGE_COMMIT` as the single package pin for both.
- Add all four upload-only steward pipelines with typed file validation, receipt provenance,
  per-row uploader attribution and detached reference-history refresh.
- Add nightly explicit Iceberg maintenance and the documented pause/hold/drain protocol.
- Fence SI_DM on the business steward writer; extend independent expectations with uploaded
  business/reference corrections and exact row-level provenance.
- Store local USER credentials in ignored .env.demo-users (0600), excluded from build contexts.

- Pin package #326 to stop and fail task processes after interrupted START reports.
- Add independent six-hour SI_DM bounded timestamp windows, flattened SCD2 facts and
  lookup-change expansion. Defer joined values at or beyond the admitted high bound.
- Add deterministic half-open window fixtures and independent active-fact row checks.

- Add SI_SETUP, original reference seeds and SI_REFERENCE, plus Alpha, Beta and Gamma
  ingestion through normalized ODS, with independent source-row checks.
- Add bounded `--rejectable` generation. Negative durations pass source parsing and are
  rejected by business rules; incomplete records remain eligible for ODS.
- Read declared source secrets through the package task-secret API and controller/API FILE
  provider. Pin the merged package fixes through #325.
- Persist Kafka logs under the exact image data-volume mount. Disable implicit topic creation
  and require four partitions at bootstrap. An existing recreated topic with stale offsets
  requires an explicit, audited offset reset; never adopt its positions silently.
