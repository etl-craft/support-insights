# Project starting point

These files preserve the package demo’s Support Insights content before S7.O.
They are source material for S8, not the finished S8 deployment. The connector
currently names a local SQLite Engine DB and DuckDB warehouse. S8 replaces the
client ingestion, configuration and deployment with the three-source project.

`migrations/` preserves the original metadata and optional reference stewardship.
`config/` is reserved for the CSV exports authored during S8. No CI or deployment
runs these files yet. Legacy SQL under `../reference/legacy-sql/` is reference
material only and must never be executed as project migrations.
