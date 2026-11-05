# Changelog

## [Unreleased]

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
