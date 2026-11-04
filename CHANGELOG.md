# Changelog

## [Unreleased]

- Add SI_SETUP, original reference seeds and SI_REFERENCE, plus Alpha, Beta and Gamma
  ingestion through normalized ODS, with independent source-row checks.
- Add bounded `--rejectable` generation. Negative durations pass source parsing and are
  rejected by business rules; incomplete records remain eligible for ODS.
- Read declared source secrets through the package task-secret API and controller/API FILE
  provider. Pin the merged package fixes through #325.
- Persist Kafka logs under the exact image data-volume mount. Disable implicit topic creation
  and require four partitions at bootstrap. An existing recreated topic with stale offsets
  requires an explicit, audited offset reset; never adopt its positions silently.
